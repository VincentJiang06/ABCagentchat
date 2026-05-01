from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .api import ModelSettings


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_COORDINATOR_MODEL = "deepseek-v4-pro"
DEFAULT_ROLE_MODEL = "deepseek-v4-flash"
COORDINATOR_MAX_TOKENS = 65536
ROLE_MAX_TOKENS = 4096


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

    @classmethod
    def from_env(cls, root: Path, *, timeout: int = 600) -> "AppConfig":
        load_dotenv(root / ".env")
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
                thinking_enabled=True,
                reasoning_effort=os.getenv("DEEPSEEK_ROLE_REASONING", "high"),
                temperature=0.4,
                timeout=timeout,
            ),
        )
