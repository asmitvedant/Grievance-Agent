"""Clients for a locally served Qwen model.

* ``ollama``  - Ollama's /api/chat (``ollama pull qwen2.5:7b-instruct``). Supports JSON-schema output.
* ``openai``  - any OpenAI-compatible local server (vLLM, LM Studio, llama.cpp server).
* ``mock``    - deterministic stand-in used ONLY by the unit tests and offline smoke runs.
               It is not a language model; numbers produced with it say nothing about Qwen.
"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

import requests

Message = dict[str, str]


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    def chat(self, messages: list[Message], *, task: str, temperature: float = 0.0,
             schema: dict | None = None, max_tokens: int = 512, context: dict | None = None) -> str: ...


class OllamaClient:
    def __init__(self, host: str, model: str, timeout: float = 120.0, seed: int = 7):
        self.host, self.model, self.timeout, self.seed = host, model, timeout, seed
        self.name = f"ollama:{model}"

    def chat(self, messages, *, task, temperature=0.0, schema=None, max_tokens=512, context=None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "seed": self.seed, "num_predict": max_tokens, "num_ctx": 8192},
        }
        if schema is not None:
            payload["format"] = schema
        try:
            r = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except Exception as exc:
            raise LLMError(f"Ollama call failed ({self.host}, model {self.model}): {exc}") from exc


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0, seed: int = 7, api_key: str = "local"):
        self.base_url, self.model, self.timeout, self.seed, self.api_key = base_url, model, timeout, seed, api_key
        self.name = f"openai-compatible:{model}"

    def chat(self, messages, *, task, temperature=0.0, schema=None, max_tokens=512, context=None) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature,
                                   "max_tokens": max_tokens, "seed": self.seed}
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": task, "schema": schema}}
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=payload, timeout=self.timeout,
                              headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError(f"OpenAI-compatible call failed ({self.base_url}): {exc}") from exc


# ---------------------------------------------------------------------------------------
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


class MockLLM:
    """Deterministic, rule-based stand-in for tests. NOT a model of Qwen's behaviour."""

    name = "mock (tests only - not an LLM)"

    _QUESTIONS = [
        "When did this happen, and has it happened before?",
        "Who was involved? Please describe them by role, for example a warden or a senior, rather than by name.",
        "Have you already raised this with anyone, and what happened?",
        "What outcome would you like from the Grievance Cell?",
        "Is there anything else the committee should know? When you are ready, press 'Review my record'.",
    ]

    def chat(self, messages, *, task, temperature=0.0, schema=None, max_tokens=512, context=None) -> str:
        context = context or {}
        if task == "dialogue":
            n = sum(1 for m in messages if m["role"] == "assistant")
            q = self._QUESTIONS[min(n, len(self._QUESTIONS) - 1)]
            return f"Thank you for explaining this. It sounds like it has been difficult for you. {q}"
        if task == "extract":
            return json.dumps(self._extract(context.get("sentences", [])))
        if task == "urgency_judge":
            return json.dumps({"risk": "none", "reason": "mock judge does not assess risk"})
        if task == "baseline_reply":
            return "I'm so sorry you're going through this, that sounds really hard. Can you tell me more?"
        if task == "baseline_summary":
            sents = split_sentences(context.get("student_text", ""))
            summary = " ".join(f"The student says {s[0].lower() + s[1:]}" for s in sents[:3]) if sents else ""
            text = context.get("student_text", "").lower()
            esc = any(k in text for k in ("kill myself", "suicide", "end my life", "want to die"))
            return json.dumps({"summary": summary, "escalate": esc, "category": "other"})
        raise LLMError(f"MockLLM has no behaviour for task {task!r}")

    @staticmethod
    def _extract(sents: list[str]) -> dict:
        belief_re = re.compile(r"\b(i think|i feel like|i believe|maybe|probably|i guess|i'm sure)\b", re.I)
        want_re = re.compile(r"\b(i want|i would like|i'd like|please|i need|i request)\b", re.I)
        claims, beliefs, outcome = [], [], None
        for i, s in enumerate(sents, 1):
            if want_re.search(s) and outcome is None:
                outcome = i
            elif belief_re.search(s):
                beliefs.append(i)
            elif len(s.split()) >= 4:
                claims.append({"id": i, "kind": "event"})
        lower = " ".join(sents).lower()
        cat = "other"
        for key, words in (("scholarship", ("scholarship",)), ("ragging", ("ragging", "ragged")),
                           ("harassment", ("harass",)), ("discrimination", ("caste", "discriminat")),
                           ("fees_refund", ("fee", "refund")), ("exams_results", ("result", "exam")),
                           ("evaluation", ("marks", "grade")), ("infrastructure", ("hostel", "wifi", "water", "lab"))):
            if any(w in lower for w in words):
                cat = key
                break
        return {"category": cat, "claims": claims[:8], "beliefs": beliefs[:4], "requested_outcome": outcome,
                "clarity": "clear" if len(claims) >= 2 else "unclear",
                "missing": [] if len(claims) >= 2 else ["what happened", "when"], "neutral_summary": ""}


def get_llm(settings) -> LLMClient:
    if settings.llm_backend == "ollama":
        return OllamaClient(settings.ollama_host, settings.llm_model, settings.llm_timeout, settings.llm_seed)
    if settings.llm_backend == "openai":
        return OpenAICompatClient(settings.openai_base_url, settings.llm_model, settings.llm_timeout, settings.llm_seed)
    if settings.llm_backend == "mock":
        return MockLLM()
    raise ValueError(f"Unknown LLM_BACKEND {settings.llm_backend!r}")


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences or leading prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))
