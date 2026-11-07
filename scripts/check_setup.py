"""Check every local component and create the database tables.

    python scripts/check_setup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grievance_agent.config import get_settings  # noqa: E402
from grievance_agent.embeddings import get_embedder  # noqa: E402
from grievance_agent.llm import LLMError, get_llm  # noqa: E402
from grievance_agent.store import Store  # noqa: E402
from grievance_agent.verifier import get_nli  # noqa: E402

s = get_settings()
ok = True
try:
    store = Store(s.database_url)
    print(f"[ok]   database   {s.database_url.split('@')[-1]}")
except Exception as exc:
    ok = False
    print(f"[FAIL] database   {exc}\n       Is MySQL running? `docker compose up -d`, or use DATABASE_URL=sqlite:///data/dev.db")
try:
    out = get_llm(s).chat([{"role": "user", "content": "Reply with the word ok."}], task="dialogue", max_tokens=5)
    print(f"[ok]   LLM        {s.llm_backend}:{s.llm_model} -> {out.strip()[:20]!r}")
except LLMError as exc:
    ok = False
    print(f"[FAIL] LLM        {exc}\n       Run `ollama serve` and `ollama pull {s.llm_model}`.")
emb = get_embedder(s.embed_backend, s.embed_model)
print(f"[{'ok' if emb.name != 'hashing-512' else 'WARN'}] embeddings {emb.name}")
nli = get_nli(s.nli_backend, s.nli_model)
print(f"[{'ok' if 'fallback' not in nli.name else 'WARN'}] NLI        {nli.name}")
if emb.name == "hashing-512" or "fallback" in nli.name:
    print("       Fallback in use: run `python scripts/download_models.py` once with internet access.")
sys.exit(0 if ok else 1)
