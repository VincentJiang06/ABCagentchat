from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .api import ModelSettings
from .local_diffusion import LocalSettings


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_COORDINATOR_MODEL = "deepseek-v4-pro"
DEFAULT_ROLE_MODEL = "deepseek-v4-pro"
COORDINATOR_MAX_TOKENS = 65536
ROLE_MAX_TOKENS = 6144

# Local DiffusionGemma backend (ABC_BACKEND=local). The model runs through
# llama-diffusion-cli, so generation length is capped to bound wall-clock time
# and GPU batch memory; raise DG_*_MAX_N for more detail at the cost of speed.
# Coordinator thinking is OFF by default: with thinking ON the model burns the
# whole budget reasoning and gets truncated before emitting its JSON/report.
DEFAULT_COORD_MAX_N = 4096
DEFAULT_ROLE_MAX_N = 1536


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "on", "yes")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class AppConfig:
    coordinator_key: str
    role_keys: dict[str, str]
    base_url: str
    coordinator_model: str
    role_model: str
    coordinator_settings: ModelSettings
    role_settings: ModelSettings
    backend: str = "deepseek"
    coordinator_local: LocalSettings | None = None
    role_local: LocalSettings | None = None

    @classmethod
    def from_env(cls, root: Path, *, timeout: int = 600) -> "AppConfig":
        load_dotenv(root / ".env")
        backend = os.getenv("ABC_BACKEND", "deepseek").strip().lower()
        if backend in ("local", "diffusiongemma", "local-diffusion"):
            return cls._local(root, timeout=timeout)
        base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        coordinator_model = (
            os.getenv("DEEPSEEK_COORDINATOR_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or DEFAULT_COORDINATOR_MODEL
        )
        role_model = os.getenv("DEEPSEEK_ROLE_MODEL") or DEFAULT_ROLE_MODEL
        coordinator_key = os.getenv("DEEPSEEK_COORDINATOR_KEY") or os.getenv("DEEPSEEK_API_KEY") or ""
        role_keys = {
            "A": os.getenv("DEEPSEEK_ROLE_A_KEY") or "",
            "B": os.getenv("DEEPSEEK_ROLE_B_KEY") or "",
            "C": os.getenv("DEEPSEEK_ROLE_C_KEY") or "",
            "D": os.getenv("DEEPSEEK_ROLE_D_KEY") or "",
        }
        missing = []
        if not coordinator_key:
            missing.append("DEEPSEEK_COORDINATOR_KEY")
        missing.extend(name for name, value in role_keys.items() if not value)
        if missing:
            printable = ", ".join(
                f"DEEPSEEK_ROLE_{name}_KEY" if len(name) == 1 else name for name in missing
            )
            raise RuntimeError(f"Missing API key environment values: {printable}")

        return cls(
            coordinator_key=coordinator_key,
            role_keys=role_keys,
            base_url=base_url,
            coordinator_model=coordinator_model,
            role_model=role_model,
            coordinator_settings=ModelSettings(
                model=coordinator_model,
                base_url=base_url,
                max_tokens=COORDINATOR_MAX_TOKENS,
                thinking_enabled=True,
                reasoning_effort=os.getenv("DEEPSEEK_COORDINATOR_REASONING", "max"),
                temperature=0.2,
                timeout=timeout,
            ),
            role_settings=ModelSettings(
                model=role_model,
                base_url=base_url,
                max_tokens=ROLE_MAX_TOKENS,
                thinking_enabled=False,
                reasoning_effort=None,
                temperature=0.8,
                timeout=timeout,
            ),
        )

    @classmethod
    def _local(cls, root: Path, *, timeout: int) -> "AppConfig":
        """Local DiffusionGemma backend: no API keys, one CLI process, serial roles."""
        coord_max_n = int(os.getenv("DG_COORD_MAX_N", str(DEFAULT_COORD_MAX_N)))
        role_max_n = int(os.getenv("DG_ROLE_MAX_N", str(DEFAULT_ROLE_MAX_N)))
        local_timeout = int(os.getenv("DG_TIMEOUT", str(max(timeout, 1800))))
        coordinator_local = LocalSettings(
            model_label="diffusiongemma-26B-A4B-it-Q4_K_M",
            thinking_enabled=_env_truthy("DG_COORD_THINKING", "0"),
            max_tokens=COORDINATOR_MAX_TOKENS,
            max_n=coord_max_n,
            temperature=0.2,
            timeout=local_timeout,
        )
        role_local = LocalSettings(
            model_label="diffusiongemma-26B-A4B-it-Q4_K_M",
            thinking_enabled=False,
            max_tokens=ROLE_MAX_TOKENS,
            max_n=role_max_n,
            temperature=0.8,
            timeout=local_timeout,
        )
        return cls(
            coordinator_key="local",
            role_keys={"A": "local", "B": "local", "C": "local", "D": "local"},
            base_url="local",
            coordinator_model=coordinator_local.model_label,
            role_model=role_local.model_label,
            coordinator_settings=coordinator_local._as_model_settings(),
            role_settings=role_local._as_model_settings(),
            backend="local",
            coordinator_local=coordinator_local,
            role_local=role_local,
        )
