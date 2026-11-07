"""Download the local embedding and NLI models once (needs internet). Afterwards everything runs offline.

    python scripts/download_models.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grievance_agent.config import get_settings  # noqa: E402

s = get_settings()
from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

print(f"Downloading embedding model {s.embed_model} ...")
SentenceTransformer(s.embed_model, device="cpu").encode(["test"])
print(f"Downloading NLI model {s.nli_model} ...")
CrossEncoder(s.nli_model, device="cpu").predict([("I paid the fee.", "The fee was paid.")])
print("Done. Models are cached locally.")
