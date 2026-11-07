"""Local sentence embeddings.

Default: a Sentence-Transformers model run on the local machine. If the library or the
model is unavailable (e.g. offline test machines) a deterministic hashing embedder is used
and the backend name says so, so reports never mistake one for the other.
"""
from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

log = logging.getLogger(__name__)


class HashingEmbedder:
    """Character n-gram + word hashing into a fixed vector. Weak, but offline and deterministic."""

    name = "hashing-512"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        words = re.findall(r"[a-z0-9']+", t)
        feats = [f"w:{w}" for w in words]
        feats += [f"b:{a}_{b}" for a, b in zip(words, words[1:])]
        padded = f" {t} "
        feats += [f"c:{padded[i:i + 4]}" for i in range(max(0, len(padded) - 3))]
        return feats

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for f in self._features(text):
                h = int.from_bytes(hashlib.md5(f.encode()).digest()[:8], "little")
                weight = 2.0 if f.startswith(("w:", "b:")) else 0.5
                out[i, h % self.dim] += weight if (h >> 63) == 0 else -weight
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(model_name, device="cpu")
        self.name = model_name

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)


def get_embedder(backend: str, model_name: str):
    if backend == "sentence-transformers":
        try:
            return SentenceTransformerEmbedder(model_name)
        except Exception as exc:  # library missing or model not downloaded
            log.warning("Sentence-Transformers unavailable (%s); falling back to hashing embedder.", exc)
    return HashingEmbedder()


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
