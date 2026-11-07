"""Component-level evaluation: every safety component that does NOT need the LLM, on all cases.

    python -m evaluation.component_eval

Experiments
  E1  Urgency detection + LLM-free routing (rules, embedding kNN, vagueness markers), with ablations
  E2  PII redaction: seeded identifiers removed? gold facts left intact?
  E3  Prompt-injection filter: injection lines caught? ordinary lines left alone?
  E4  Verifier: genuine quotes accepted vs systematically altered quotes rejected
      (span + entailment vs entailment only vs span only)

The Qwen risk judge, dialogue and extraction layers are NOT exercised here; their effect is measured
by `python -m evaluation.run_eval` on a machine running Qwen.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from grievance_agent.config import ROOT, get_settings
from grievance_agent.embeddings import get_embedder
from grievance_agent.extraction import _INSTRUCTION_RE
from grievance_agent.pii import redact
from grievance_agent.router import vagueness_score
from grievance_agent.taxonomy import (ESCALATION_ROUTES, HUMAN_REVIEW_AMBIGUOUS, SGRC_PRIORITY, SGRC_STANDARD,
                                      URGENCY_RANK, URGENT_ALERT)
from grievance_agent.urgency import UrgencyDetector
from grievance_agent.verifier import Verifier, get_nli

from .metrics import leaked, wilson

# ---------------------------------------------------------------- E1 urgency + routing


def route_without_llm(detector: UrgencyDetector, turns: list[str]) -> tuple[str, dict]:
    """Process turns like the harness (latest message + last 3 as context, stop at first high)."""
    best, confident, high_turn = None, True, None
    for i, t in enumerate(turns):
        a = detector.assess(t, " ".join(turns[max(0, i - 3):i]))
        confident = confident and a.confident
        if best is None or (URGENCY_RANK[a.level], a.score) > (URGENCY_RANK[best.level], best.score):
            best = a
        if a.level == "high":
            high_turn = i
            break
    text = "\n".join(turns)
    v = vagueness_score(text)
    vague = v >= 2 or (v == 1 and len(text.split()) < 40)
    if best.level == "high":
        route = URGENT_ALERT
    elif not confident or vague:
        route = HUMAN_REVIEW_AMBIGUOUS
    elif best.level == "sensitive":
        route = SGRC_PRIORITY
    else:
        route = SGRC_STANDARD
    return route, {"level": best.level, "score": best.score, "confident": confident, "vague": vague, "high_turn": high_turn,
                   "reasons": best.reasons}


def e1_urgency(cases: list[dict], embedder) -> dict:
    variants = {"rules + kNN": dict(use_rules=True, use_knn=True), "rules only": dict(use_rules=True, use_knn=False),
                "kNN only": dict(use_rules=False, use_knn=True)}
    out: dict = {}
    for name, kw in variants.items():
        det = UrgencyDetector(embedder, store=None, llm=None, use_llm_judge=False, **kw)
        rows = []
        for c in cases:
            route, info = route_without_llm(det, c["turns"])
            rows.append({"case_id": c["case_id"], "slice": c["slice"], "cue_type": c.get("cue_type"), "cue_turn": c.get("cue_turn"),
                         "gold_route": c["gold_route"], "gold_escalate": c["should_escalate"], "route": route,
                         "escalate": route in ESCALATION_ROUTES, **info})
        pos = [r for r in rows if r["gold_escalate"]]
        neg = [r for r in rows if not r["gold_escalate"]]
        tp, fp = sum(r["escalate"] for r in pos), sum(r["escalate"] for r in neg)
        hr = [r for r in rows if r["slice"] == "high_risk"]
        by_cue = {}
        for cue in ("explicit", "indirect", "violence"):
            rs = [r for r in hr if r["cue_type"] == cue]
            k = sum(r["route"] == URGENT_ALERT for r in rs)
            by_cue[cue] = {"n": len(rs), "urgent": k, "rate": k / len(rs)}
        k_urgent = sum(r["route"] == URGENT_ALERT for r in hr)
        on_cue = [r for r in hr if r["high_turn"] is not None and r["cue_turn"] is not None]
        false_high = [r for r in rows if r["slice"] != "high_risk" and r["route"] == URGENT_ALERT]
        conf = Counter((r["gold_route"], r["route"]) for r in rows)
        out[name] = {
            "urgency_recall": tp / len(pos), "urgency_recall_ci": wilson(tp, len(pos)), "tp": tp, "positives": len(pos),
            "false_escalation_rate": fp / len(neg), "fer_ci": wilson(fp, len(neg)), "fp": fp, "negatives": len(neg),
            "high_risk_urgent_rate": k_urgent / len(hr), "high_risk_urgent_ci": wilson(k_urgent, len(hr)), "high_risk_urgent": k_urgent,
            "by_cue": by_cue, "alerted_on_cue_turn": sum(r["high_turn"] == r["cue_turn"] for r in on_cue), "alerted_n": len(on_cue),
            "false_urgent_alerts": [r["case_id"] for r in false_high],
            "route_accuracy": sum(r["route"] == r["gold_route"] for r in rows) / len(rows),
            "per_slice_route_accuracy": {s: sum(r["route"] == r["gold_route"] for r in rows if r["slice"] == s) /
                                         sum(1 for r in rows if r["slice"] == s) for s in sorted({r["slice"] for r in rows})},
            "confusion": {f"{g} -> {p}": n for (g, p), n in sorted(conf.items())},
            "misses": [{"case_id": r["case_id"], "slice": r["slice"], "gold": r["gold_route"], "got": r["route"],
                        "turns": next(c["turns"] for c in cases if c["case_id"] == r["case_id"])}
                       for r in rows if r["gold_escalate"] and not r["escalate"]],
        }
    return out


# ---------------------------------------------------------------- E2 PII


def e2_pii(cases: list[dict]) -> dict:
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    damaged, spans = 0, 0
    leaks = []
    for c in cases:
        red = "\n".join(redact(t).text for t in c["turns"])
        for p in c["seeded_pii"]:
            lk = leaked(p["value"], red)
            by_type[p["type"]][0] += 1
            by_type[p["type"]][1] += lk
            if lk:
                leaks.append({"case_id": c["case_id"], "type": p["type"]})
        for f in c["gold_facts"]:
            spans += 1
            damaged += f["span"] not in red
    n = sum(v[0] for v in by_type.values())
    k = sum(v[1] for v in by_type.values())
    return {"seeded": n, "leaked": k, "leakage_rate": k / n if n else None, "by_type": {t: {"seeded": a, "leaked": b} for t, (a, b) in by_type.items()},
            "gold_spans": spans, "gold_spans_altered_by_redaction": damaged, "leaks": leaks}


# ---------------------------------------------------------------- E3 injection filter


def e3_injection(cases: list[dict]) -> dict:
    from data.generate_cases import INJECTIONS  # the probe lines used in the development set

    probes = set(INJECTIONS) | {c["injection_line"] for c in cases if c.get("injection_line")}
    tp = fn = fp = tn = 0
    false_flags = []
    for c in cases:
        for t in c["turns"]:
            is_inj = t in probes
            hit = bool(_INSTRUCTION_RE.search(t))
            tp += is_inj and hit
            fn += is_inj and not hit
            fp += (not is_inj) and hit
            tn += (not is_inj) and not hit
            if hit and not is_inj:
                false_flags.append(t)
    return {"injection_turns": tp + fn, "caught": tp, "missed": fn, "other_turns": fp + tn, "false_flags": fp,
            "detection_rate": tp / (tp + fn) if tp + fn else None, "false_flag_rate": fp / (fp + tn), "false_flag_examples": false_flags[:5]}


# ---------------------------------------------------------------- E4 verifier perturbations

_NUM = {"two": "three", "three": "five", "four": "six", "five": "three", "six": "four", "ten": "two", "once": "twice", "twice": "once"}
_MONTH_DAY = {"June": "March", "July": "January", "August": "April", "September": "May", "Monday": "Thursday",
              "Tuesday": "Sunday", "Wednesday": "Saturday", "Friday": "Tuesday", "Saturday": "Monday", "November": "October", "December": "February"}
_ROLE = {"senior": "professor", "seniors": "professors", "warden": "principal", "clerk": "dean", "classmates": "teachers",
         "HOD": "registrar", "Girls": "Boys", "girls": "boys", "teaching assistant": "hostel guard", "accounts office": "library",
         "lab in-charge": "director", "scholarship section": "sports office", "exam cell": "canteen"}
_ADDITIONS = [" on purpose", " and threatened me", " by the HOD"]


def _swap(text: str, table: dict) -> str | None:
    for a, b in table.items():
        m = re.search(rf"\b{re.escape(a)}\b", text)
        if m:
            return text[:m.start()] + b + text[m.end():]
    return None


def _digits(text: str) -> str | None:
    m = re.search(r"\d+", text)
    return None if not m else text[:m.start()] + str(int(m.group()) + 7) + text[m.end():]


def _negate(text: str) -> str | None:
    for a, b in ((r"\bhas not\b", "has"), (r"\bhave not\b", "have"), (r"\bdid not\b", "did"), (r"\bdo not\b", "do"),
                 (r"\bnot\b ", ""), (r"\b(was|were|is|are|has|have)\b", r"\1 not")):
        new, n = re.subn(a, b, text, count=1)
        if n:
            return new
    return None


PERTURBATIONS = {
    "number changed": lambda t: _swap(t, _NUM) or _digits(t),
    "date/day changed": lambda t: _swap(t, _MONTH_DAY),
    "negation flipped": _negate,
    "person/office swapped": lambda t: _swap(t, _ROLE),
    "detail added": lambda t: t + _ADDITIONS[len(t) % len(_ADDITIONS)],
}


def e4_verifier(cases: list[dict], nli, threshold: float) -> dict:
    v = Verifier(nli, threshold)
    genuine = {"span+NLI": 0, "NLI only": 0, "span only": 0, "n": 0}
    altered: dict[str, dict[str, int]] = {k: {"span+NLI": 0, "NLI only": 0, "span only": 0, "n": 0} for k in PERTURBATIONS}
    examples = {}
    for c in cases:
        src = "\n".join(c["turns"])
        for f in c["gold_facts"]:
            q = f["span"]
            chk = v.check_quote(q, "claim", src)
            genuine["n"] += 1
            genuine["span+NLI"] += chk.preserved
            genuine["NLI only"] += chk.entail >= threshold
            genuine["span only"] += bool(chk.verbatim)
            for name, fn in PERTURBATIONS.items():
                alt = fn(q)
                if not alt or alt == q:
                    continue
                chk = v.check_quote(alt, "claim", src)
                a = altered[name]
                a["n"] += 1
                # "accepted" counts; the report shows rejection = 1 - accepted/n
                a["span+NLI"] += chk.preserved
                a["NLI only"] += chk.entail >= threshold
                a["span only"] += bool(chk.verbatim)
                examples.setdefault(name, {"original": q, "altered": alt})
    tot = {k: sum(a[k] for a in altered.values()) for k in ("span+NLI", "NLI only", "span only", "n")}
    return {"nli_backend": getattr(nli, "name", "?"), "threshold": threshold,
            "genuine_accept_rate": {k: genuine[k] / genuine["n"] for k in ("span+NLI", "NLI only", "span only")}, "genuine_n": genuine["n"],
            "altered_reject_rate": {name: {k: 1 - a[k] / a["n"] for k in ("span+NLI", "NLI only", "span only")} | {"n": a["n"]}
                                    for name, a in altered.items() if a["n"]},
            "altered_reject_overall": {k: 1 - tot[k] / tot["n"] for k in ("span+NLI", "NLI only", "span only")} | {"n": tot["n"]},
            "examples": examples}


# ---------------------------------------------------------------- main


def main() -> None:
    import argparse
    import sys
    sys.path.insert(0, str(ROOT))
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "data" / "cases.jsonl"))
    ap.add_argument("--tag", default="dev")
    args = ap.parse_args()
    s = get_settings()
    cases = [json.loads(line) for line in open(args.cases, encoding="utf-8")]
    embedder = get_embedder(s.embed_backend, s.embed_model)
    nli = get_nli(s.nli_backend, s.nli_model)
    result = {"generated": datetime.now().isoformat(timespec="seconds"), "n_cases": len(cases),
              "environment": {"embedder": embedder.name, "nli": getattr(nli, "name", "?"), "llm": "not used"},
              "E1_urgency_routing": e1_urgency(cases, embedder), "E2_pii": e2_pii(cases),
              "E3_injection_filter": e3_injection(cases)}
    if any(c["gold_facts"] for c in cases):
        result["E4_verifier"] = e4_verifier(cases, nli, s.nli_threshold)
    out = ROOT / "results" / f"components-{args.tag}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "component_results.json").write_text(json.dumps(result, indent=1, default=str))
    e1 = result["E1_urgency_routing"]
    lines = [f"# Component evaluation: {args.tag} set ({len(cases)} synthetic cases, no LLM)", "",
             f"Embedder `{embedder.name}` · NLI `{getattr(nli, 'name', '?')}`", "", "## E1 Urgency detection + LLM-free routing", "",
             "| Variant | Urgency recall | False-escalation rate | High-risk → urgent alert | Route accuracy |", "|---|---|---|---|---|"]
    for k, r in e1.items():
        lines.append(f"| {k} | {r['tp']}/{r['positives']} = {r['urgency_recall']:.3f} | {r['fp']}/{r['negatives']} = {r['false_escalation_rate']:.3f} | "
                     f"{r['high_risk_urgent']}/{sum(1 for c in cases if c['slice'] == 'high_risk')} = {r['high_risk_urgent_rate']:.3f} | {r['route_accuracy']:.3f} |")
    p = result["E2_pii"]
    lines += ["", "## E2 PII redaction", "", f"Leaked {p['leaked']}/{p['seeded']} seeded identifiers; "
              f"{p['gold_spans_altered_by_redaction']}/{p['gold_spans']} gold fact spans altered by redaction.", ""]
    i = result["E3_injection_filter"]
    lines += ["## E3 Injection filter", "", f"Caught {i['caught']}/{i['injection_turns']} injection lines; "
              f"falsely flagged {i['false_flags']}/{i['other_turns']} ordinary lines.", ""]
    v = result.get("E4_verifier")
    if v:
        lines += ["## E4 Verifier", "", "| Check | Genuine quotes accepted | Altered quotes rejected |", "|---|---|---|"]
    for k in (("span+NLI", "NLI only", "span only") if v else ()):
        lines.append(f"| {k} | {v['genuine_accept_rate'][k]:.3f} (n={v['genuine_n']}) | {v['altered_reject_overall'][k]:.3f} (n={v['altered_reject_overall']['n']}) |")
    (out / "component_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
