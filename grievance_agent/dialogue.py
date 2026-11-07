"""Dialogue layer: warm, non-clinical replies. It talks; it never writes the record."""
from __future__ import annotations

from dataclasses import dataclass, field

from .guardrails import check_reply
from .llm import LLMClient, LLMError
from .prompts import DIALOGUE_SYSTEM, GUARD_CORRECTION, SAFE_FALLBACK_REPLY


@dataclass
class DialogueReply:
    text: str
    violations_first_try: list[str] = field(default_factory=list)
    regenerated: bool = False
    fell_back: bool = False
    error: str | None = None


class DialogueLayer:
    def __init__(self, llm: LLMClient, institution: str, temperature: float = 0.3, use_guard: bool = True):
        self.llm, self.temperature, self.use_guard = llm, temperature, use_guard
        self.system = DIALOGUE_SYSTEM.format(institution=institution)

    def reply(self, history: list[dict]) -> DialogueReply:
        """history: [{"role": "student"|"assistant", "text": redacted text}, ...]"""
        msgs = [{"role": "system", "content": self.system}]
        msgs += [{"role": "user" if h["role"] == "student" else "assistant", "content": h["text"]} for h in history]
        try:
            text = self.llm.chat(msgs, task="dialogue", temperature=self.temperature, max_tokens=160).strip()
        except LLMError as exc:
            return DialogueReply(SAFE_FALLBACK_REPLY, fell_back=True, error=str(exc))
        if not self.use_guard:
            return DialogueReply(text)
        problems = check_reply(text)
        if not problems:
            return DialogueReply(text)
        out = DialogueReply(text, violations_first_try=problems, regenerated=True)
        retry = msgs + [{"role": "assistant", "content": text},
                        {"role": "user", "content": GUARD_CORRECTION.format(problems=", ".join(problems))}]
        try:
            text2 = self.llm.chat(retry, task="dialogue", temperature=0.0, max_tokens=160).strip()
        except LLMError as exc:
            text2, out.error = "", str(exc)
        if text2 and not check_reply(text2):
            out.text = text2
        else:
            out.text, out.fell_back = SAFE_FALLBACK_REPLY, True
        return out
