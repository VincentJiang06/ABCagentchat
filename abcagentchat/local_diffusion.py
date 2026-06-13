"""Local DiffusionGemma backend — a drop-in replacement for DeepSeekClient.

DiffusionGemma is a block-diffusion model with no server support yet; it only
runs through the dedicated `llama-diffusion-cli`. There is therefore no
concurrency: one CLI process generates one canvas at a time. ABC's role rounds
are *snapshot-fair* (every role in a round reads the same pre-round context and
never sees a peer's same-round answer), so running the four roles serially
instead of in a thread pool produces the SAME deliberation — we just lose the
wall-clock overlap, which a single local model could not exploit anyway.

This client mirrors DeepSeekClient: `.chat(messages, ...) -> ChatResult` and
`.request_meta(...) -> dict`. Each call renders the Gemma chat template (pure
Python, no extra deps), runs one `llama-diffusion-cli -no-cnv` generation, and
parses the visible answer out of the `<|channel>thought ... <channel|>` wrapper.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any

from .api import ChatResult

# --- environment / defaults -------------------------------------------------
DEFAULT_BIN = "/Users/vince/playground/llama.cpp/build/bin/llama-diffusion-cli"
DEFAULT_MODEL = "/Users/vince/playground/DiffusionGemma/diffusiongemma-26B-A4B-it-Q4_K_M.gguf"

THOUGHT_BLOCK_RE = re.compile(r"<\|channel>thought\s*(.*?)<channel\|>", re.S)
TOTAL_RE = re.compile(r"total time:\s*([\d.]+)ms.*?\((\d+) steps over (\d+) blocks", re.S)
THROUGHPUT_RE = re.compile(r"throughput:\s*([\d.]+) tok/s")
# "needs the whole [prompt | canvas] in one ubatch; set -ub and -c >= N + 256 = M"
UBATCH_RE = re.compile(r"in one ubatch.*?=\s*(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)", re.S)
CANVAS_LENGTH = 256


def _round256(x: int) -> int:
    return ((max(0, x) + 255) // 256) * 256


CJK_RE = re.compile(r"[㐀-鿿豈-﫿぀-ヿ]")
WORD_RE = re.compile(r"[A-Za-z0-9]+")


def estimate_tokens(text: str) -> int:
    """Cheap token estimate good enough for ABC's metrics/audit reporting."""
    if not text:
        return 0
    cjk = len(CJK_RE.findall(text))
    words = len(WORD_RE.findall(text))
    other = max(len(text) - cjk - sum(len(w) for w in WORD_RE.findall(text)), 0)
    return cjk + words + other // 4


def strip_thinking(text: str) -> tuple[str, str]:
    """Return (visible_answer, thinking). Thinking is the CoT channel content."""
    thinking = "\n".join(m.strip() for m in THOUGHT_BLOCK_RE.findall(text)).strip()
    visible = THOUGHT_BLOCK_RE.sub("", text)
    visible = visible.replace("<|channel>thought", "").replace("<channel|>", "")
    return visible.strip(), thinking


def render_chat(messages: list[dict[str, str]], *, thinking: bool, bos: str = "") -> str:
    """Render messages into the DiffusionGemma prompt string (plain-text path).

    Mirrors the model's embedded chat template for the no-tools/no-image case.
    `bos=""` lets llama.cpp add BOS itself (validated to produce coherent output).
    When thinking is off, an empty thought channel is primed so the answer leads.
    """
    out: list[str] = [bos]
    msgs = list(messages)
    sys_msg = msgs[0] if msgs and msgs[0].get("role") in ("system", "developer") else None
    if thinking or sys_msg is not None:
        out.append("<|turn>system\n")
        if thinking:
            out.append("<|think|>\n")
        if sys_msg is not None:
            out.append(str(sys_msg.get("content", "")).strip())
            msgs = msgs[1:]
        out.append("<turn|>\n")
    for msg in msgs:
        role = "model" if msg.get("role") == "assistant" else str(msg.get("role"))
        content = str(msg.get("content", ""))
        if role == "model":
            content, _ = strip_thinking(content)
        out.append(f"<|turn>{role}\n")
        out.append(content.strip())
        out.append("<turn|>\n")
    out.append("<|turn>model\n")
    if not thinking:
        out.append("<|channel>thought\n<channel|>")
    return "".join(out)


@dataclass(frozen=True)
class LocalSettings:
    model_label: str          # for transcript/request_meta
    thinking_enabled: bool
    max_tokens: int           # logical ceiling (mapped to -n, capped by max_n)
    max_n: int                # hard cap on -n (bounds time + GPU batch memory)
    temperature: float = 0.2
    timeout: int = 1800

    def _as_model_settings(self):
        """A ModelSettings view so config.{coordinator,role}_settings stays valid."""
        from .api import ModelSettings
        return ModelSettings(
            model=self.model_label,
            base_url="local",
            max_tokens=self.max_tokens,
            thinking_enabled=self.thinking_enabled,
            reasoning_effort=None,
            temperature=self.temperature,
            timeout=self.timeout,
        )


class LocalDiffusionClient:
    """Single-process local backend. Interface-compatible with DeepSeekClient."""

    def __init__(self, settings: LocalSettings) -> None:
        self.settings = settings
        self.bin = os.environ.get("DG_BIN", DEFAULT_BIN)
        self.model = os.environ.get("DG_MODEL", DEFAULT_MODEL)
        self.ngl = os.environ.get("DG_NGL", "99")
        # Resource controls (low-memory defaults): single-threaded, quantized KV
        # cache, and a per-call ubatch sized to the prompt. The diffusion model
        # needs the whole [prompt | one canvas] in ONE ubatch, and that ubatch is
        # the big GPU compute buffer — so we size it tightly and cap it. A huge
        # fixed ubatch (e.g. 32768) segfaults / blows memory; ~8192 is the cap.
        self.threads = os.environ.get("DG_THREADS", "1")
        self.kv_type = os.environ.get("DG_KV_TYPE", "q8_0")
        # MEASURED memory ceiling. ubatch is the SOLE driver of peak GPU memory
        # (n_predict barely matters; -c is respected). Measured on 48 GB M4 Pro:
        #   ubatch 4096 -> ~23 GB,  6144 -> ~26 GB,  8192 -> ~27 GB (+ ~14 GB of
        # other apps -> ~41 GB total -> swap). So cap ubatch at 4096 to keep the
        # model footprint ~23 GB (<30 GB) with a robust no-swap margin. Prompts
        # are truncated to fit this ubatch (see _fit_messages).
        self.ctx_max = int(os.environ.get("DG_CTX", "6144"))
        self.ubatch_max = int(os.environ.get("DG_UBATCH_MAX", "4096"))
        self.margin = int(os.environ.get("DG_UBATCH_MARGIN", "512"))
        self.eb_tmax = os.environ.get("DG_EB_TMAX")  # optional sampler override
        self.eb_tmin = os.environ.get("DG_EB_TMIN")

    # -- DeepSeekClient-compatible surface -----------------------------------
    def request_meta(
        self, *, max_tokens: int | None = None, temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        return {
            "model": self.settings.model_label,
            "backend": "local-diffusiongemma",
            "thinking": {"type": "enabled" if self.settings.thinking_enabled else "disabled"},
            "max_tokens": max_tokens or self.settings.max_tokens,
            "n_predict": self._n_predict(max_tokens),
            "threads": self.threads,
            "kv_type": self.kv_type,
            "ubatch_max": self.ubatch_max,
        }

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int | None = None,
        temperature: float | None = None, reasoning_effort: str | None = None,
    ) -> ChatResult:
        n_predict = self._n_predict(max_tokens)
        # Trim oldest turns so prompt + one canvas fits the ubatch cap (keeps the
        # system prompt + the most recent turns + the current question; the
        # coordinator's compact carries the long-term memory across what is dropped).
        prompt_budget = self.ubatch_max - CANVAS_LENGTH - self.margin
        msgs, trimmed = self._fit_messages(messages, prompt_budget)
        prompt = render_chat(msgs, thinking=self.settings.thinking_enabled)

        n_in = estimate_tokens(prompt)
        ub = max(2048, min(_round256(n_in + CANVAS_LENGTH + self.margin), self.ubatch_max))
        ctx = max(ub, min(_round256(n_in + n_predict + self.margin), self.ctx_max))

        start = time.perf_counter()
        proc = self._run(prompt, ubatch=ub, ctx=ctx, n_predict=n_predict)
        raw_out = proc.stdout or ""
        # If the prompt was under-estimated and still overflowed the ubatch, retry
        # once — but NEVER above ubatch_max (that would blow the memory ceiling).
        # _fit_messages truncates prompts to fit, so this should be rare.
        if UBATCH_RE.search(proc.stderr or ""):
            need = int(UBATCH_RE.search(proc.stderr).group(3))
            ub = min(_round256(need + self.margin), self.ubatch_max)
            ctx = max(ub, min(_round256(n_in + n_predict + self.margin), self.ctx_max))
            proc = self._run(prompt, ubatch=ub, ctx=ctx, n_predict=n_predict)
            raw_out = proc.stdout or ""
        elapsed = time.perf_counter() - start

        if "OutOfMemory" in (proc.stderr or ""):
            raise RuntimeError("local diffusion GPU OOM — lower DG_UBATCH_MAX or max_n")
        body = TOTAL_RE.split(raw_out)[0]
        answer, thinking = strip_thinking(body)
        if not answer:
            tail = (proc.stderr or "")[-400:]
            raise RuntimeError(f"local diffusion produced no answer (exit={proc.returncode}); stderr tail: {tail}")

        prompt_tokens = estimate_tokens(prompt)
        reasoning_tokens = estimate_tokens(thinking)
        completion_tokens = estimate_tokens(answer) + reasoning_tokens
        tp = THROUGHPUT_RE.search(raw_out)
        tot = TOTAL_RE.search(raw_out)
        return ChatResult(
            content=answer,
            elapsed_seconds=elapsed,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            raw={
                "backend": "local-diffusiongemma",
                "n_predict": n_predict,
                "ubatch": ub,
                "ctx": ctx,
                "prompt_trimmed": trimmed,
                "throughput_tok_s": float(tp.group(1)) if tp else None,
                "steps": int(tot.group(2)) if tot else None,
                "blocks": int(tot.group(3)) if tot else None,
                "thinking": thinking,
            },
        )

    # -- internals -----------------------------------------------------------
    def _run(self, prompt: str, *, ubatch: int, ctx: int, n_predict: int):
        cmd = [
            self.bin, "-m", self.model, "-ngl", self.ngl, "-no-cnv", "--no-escape",
            "-t", self.threads, "-c", str(ctx), "-b", str(ubatch), "-ub", str(ubatch),
            "-n", str(n_predict), "--diffusion-eb", "auto",
        ]
        if self.kv_type and self.kv_type != "f16":
            cmd += ["-ctk", self.kv_type, "-ctv", self.kv_type]
        if self.eb_tmax:
            cmd += ["--diffusion-eb-t-max", self.eb_tmax]
        if self.eb_tmin:
            cmd += ["--diffusion-eb-t-min", self.eb_tmin]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as fh:
            fh.write(prompt)
            prompt_path = fh.name
        cmd += ["-f", prompt_path]
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                timeout=self.settings.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"local diffusion timed out after {self.settings.timeout}s") from exc
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass

    def _fit_messages(self, messages: list[dict[str, str]], budget_tokens: int):
        """Shrink messages so the rendered prompt fits budget_tokens.

        Step 1 — drop oldest middle turns (keep system + final/current message).
        Step 2 — if still over (e.g. the coordinator's single huge prompt, which
        cannot be turn-trimmed), truncate the largest message's content head+tail.
        This GUARANTEES the prompt fits the ubatch, so peak GPU memory stays bounded
        regardless of how large the upstream context is. Returns (messages, trimmed?).
        """
        def size(ms: list[dict[str, str]]) -> int:
            return estimate_tokens(render_chat(ms, thinking=self.settings.thinking_enabled))

        if size(messages) <= budget_tokens:
            return list(messages), False
        has_sys = bool(messages) and messages[0].get("role") in ("system", "developer")
        head = list(messages[:1]) if has_sys else []
        body = list(messages[1:]) if has_sys else list(messages)
        # 1. drop oldest middle turns, never the current (last) message
        while len(body) > 1 and size(head + body) > budget_tokens:
            body.pop(0)
        msgs = head + body
        # 2. still over -> truncate the largest message's content (keep head + tail)
        for _ in range(16):
            if size(msgs) <= budget_tokens:
                break
            over = size(msgs) - budget_tokens
            idx = max(range(len(msgs)), key=lambda i: len(str(msgs[i].get("content", ""))))
            content = str(msgs[idx].get("content", ""))
            cut = min(len(content) - 200, int(over * 1.2) + 256)
            if cut <= 0:
                break
            keep = len(content) - cut
            hh = keep // 2
            msgs[idx] = {
                **msgs[idx],
                "content": content[:hh] + "\n\n…[上下文过长，已截断以控制本地显存]…\n\n" + content[-(keep - hh):],
            }
        return msgs, True

    def _n_predict(self, max_tokens: int | None) -> int:
        want = max_tokens or self.settings.max_tokens
        return max(256, min(want, self.settings.max_n))
