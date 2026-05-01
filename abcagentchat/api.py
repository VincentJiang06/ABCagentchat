from __future__ import annotations

import json
import http.client
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelSettings:
    model: str
    base_url: str
    max_tokens: int
    thinking_enabled: bool = True
    reasoning_effort: str | None = "max"
    temperature: float = 0.2
    timeout: int = 600


@dataclass(frozen=True)
class ChatResult:
    content: str
    elapsed_seconds: float
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int
    raw: dict[str, Any]
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0

    @property
    def visible_answer_tokens_estimate(self) -> int:
        return max(self.completion_tokens - self.reasoning_tokens, 0)


def normalize_reasoning_effort(value: str) -> str:
    aliases = {
        "short": "high",
        "normal": "high",
        "long": "high",
        "extra_long": "max",
        "extra-long": "max",
        "extra long": "max",
        "xhigh": "max",
        "low": "high",
        "medium": "high",
    }
    normalized = aliases.get(value.strip().lower(), value.strip().lower())
    allowed = {"high", "max"}
    if normalized not in allowed:
        raise ValueError(f"Unsupported reasoning_effort={value!r}; expected one of {sorted(allowed)}")
    return normalized


class DeepSeekClient:
    def __init__(self, api_key: str, settings: ModelSettings) -> None:
        self.api_key = api_key
        self.settings = settings

    def build_payload(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "thinking": {"type": "enabled" if self.settings.thinking_enabled else "disabled"},
            "max_tokens": max_tokens or self.settings.max_tokens,
            "temperature": self.settings.temperature if temperature is None else temperature,
        }
        effort = reasoning_effort if reasoning_effort is not None else self.settings.reasoning_effort
        if self.settings.thinking_enabled and effort:
            payload["reasoning_effort"] = normalize_reasoning_effort(effort)
        return payload

    def request_meta(
        self,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        payload = self.build_payload([], max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort)
        return {
            "model": payload["model"],
            "thinking": payload["thinking"],
            "reasoning_effort": payload.get("reasoning_effort"),
            "max_tokens": payload["max_tokens"],
            "temperature": payload["temperature"],
        }

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
        payload = self.build_payload(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        start = time.perf_counter()
        data: dict[str, Any] | None = None
        last_error: BaseException | None = None
        for attempt in range(1, 4):
            request = urllib.request.Request(
                url=url,
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, http.client.IncompleteRead, TimeoutError) as exc:
                last_error = exc
                if attempt == 3:
                    break
                time.sleep(2 * attempt)
        if data is None:
            if isinstance(last_error, urllib.error.URLError):
                raise RuntimeError(f"DeepSeek network error: {last_error.reason}") from last_error
            raise RuntimeError(f"DeepSeek network/read error after retries: {last_error}") from last_error
        elapsed = time.perf_counter() - start

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        return ChatResult(
            content=str(message.get("content") or "").strip(),
            elapsed_seconds=elapsed,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            raw=data,
            prompt_cache_hit_tokens=int(usage.get("prompt_cache_hit_tokens") or 0),
            prompt_cache_miss_tokens=int(usage.get("prompt_cache_miss_tokens") or 0),
        )
