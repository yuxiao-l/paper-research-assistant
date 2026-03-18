from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    openalex_email: str | None


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def load_settings() -> Settings:
    _load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openalex_email=os.getenv("OPENALEX_EMAIL"),
    )
