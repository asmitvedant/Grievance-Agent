#!/usr/bin/env bash
# macOS / Linux: run the Qwen evaluation and zip the results for the slides.
#   ./run_qwen_eval.sh                                     # qwen2.5:3b-instruct, 30 dev + 52 held-out cases
#   LIMIT=15 ./run_qwen_eval.sh                            # faster trial
#   MODEL=qwen2.5:7b-instruct ./run_qwen_eval.sh           # 16 GB Macs
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${MODEL:-qwen2.5:3b-instruct}"
LIMIT="${LIMIT:-30}"
SYSTEMS="${SYSTEMS:-full B0 B1}"

echo "== 1/5 Ollama"
command -v ollama >/dev/null || { echo "Install Ollama from https://ollama.com/download/mac, open it once, then rerun."; exit 1; }
curl -sf http://localhost:11434/api/tags >/dev/null || { (ollama serve >/dev/null 2>&1 &); sleep 6; }
ollama pull "$MODEL"

echo "== 2/5 Python environment"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Python 3.10+ is needed: brew install python@3.12  (or install from python.org)"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "== 3/5 Local embedding + NLI models"
export LLM_BACKEND=ollama LLM_MODEL="$MODEL" DATABASE_URL="sqlite:///data/dev.db"
python scripts/download_models.py
python scripts/check_setup.py || true

echo "== 4/5 Evaluation"
python data/make_heldout.py
python -m evaluation.run_eval --systems $SYSTEMS --limit "$LIMIT" --rubric-per-system 10
python -m evaluation.run_eval --cases data/heldout_cases.jsonl --systems $SYSTEMS --rubric-per-system 0
python -m evaluation.component_eval
python -m evaluation.component_eval --cases data/heldout_cases.jsonl --tag heldout
for d in results/*/; do
  if [ -f "$d/summary.json" ]; then python -m evaluation.safety_report "$d"; fi
done

echo "== 5/5 Packing results"
ZIP="qwen_results_$(date +%Y%m%d-%H%M).zip"
zip -qr "$ZIP" results
echo "Done. Attach $ZIP in the chat so the slides can be updated."
