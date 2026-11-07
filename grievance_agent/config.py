"""Runtime settings, read from environment variables (or a local .env file)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the project has no hard dependency on python-dotenv."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] in ('"', "'") and value[0] in value[1:]:
            value = value[1:value.index(value[0], 1)]       # quoted value: keep '#' inside the quotes
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()  # drop an inline comment
        os.environ.setdefault(key.strip(), value)


_load_dotenv(ROOT / ".env")


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM (Qwen, served locally) ---
    llm_backend: str            # "ollama" | "openai" (vLLM / LM Studio / llama.cpp server) | "mock" (tests only)
    llm_model: str
    ollama_host: str
    openai_base_url: str
    llm_timeout: float
    dialogue_temperature: float
    llm_seed: int
    use_llm_urgency_judge: bool

    # --- storage ---
    database_url: str

    # --- local models ---
    embed_backend: str          # "sentence-transformers" | "hashing"
    embed_model: str
    nli_backend: str            # "cross-encoder" | "lexical"
    nli_model: str
    nli_threshold: float
    knn_similarity_threshold: float

    # --- privacy ---
    pii_backend: str            # "regex" | "presidio" (regex is always applied; presidio adds names etc.)
    retention_days: int

    # --- institution ---
    institution_name: str
    reviewer_password: str
    support_contacts: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            llm_backend=os.getenv("LLM_BACKEND", "ollama").lower(),
            llm_model=os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1").rstrip("/"),
            llm_timeout=_f("LLM_TIMEOUT", 600.0),
            dialogue_temperature=_f("DIALOGUE_TEMPERATURE", 0.3),
            llm_seed=int(os.getenv("LLM_SEED", "7")),
            use_llm_urgency_judge=os.getenv("USE_LLM_URGENCY_JUDGE", "1") == "1",
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'dev.db'}"),
            embed_backend=os.getenv("EMBED_BACKEND", "sentence-transformers").lower(),
            embed_model=os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            nli_backend=os.getenv("NLI_BACKEND", "cross-encoder").lower(),
            nli_model=os.getenv("NLI_MODEL", "cross-encoder/nli-deberta-v3-small"),
            nli_threshold=_f("NLI_THRESHOLD", 0.5),
            knn_similarity_threshold=_f("KNN_SIMILARITY_THRESHOLD", 0.62),
            pii_backend=os.getenv("PII_BACKEND", "regex").lower(),
            retention_days=int(os.getenv("RETENTION_DAYS", "365")),
            institution_name=os.getenv("INSTITUTION_NAME", "the University"),
            reviewer_password=os.getenv("REVIEWER_PASSWORD", "change-me"),
            support_contacts=os.getenv(
                "SUPPORT_CONTACTS",
                "Emergency: 112 | Tele-MANAS, free and 24x7: 14416 or 1-800-891-4416 | "
                "Campus counselling centre: <add your campus number in .env>",
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
