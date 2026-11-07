#!/usr/bin/env bash
# Re-run the FIXED full system (240 development + 52 held-out cases), run the baselines on the held-out
# set, and rescore every earlier run with the same evaluator. Keeps .venv and earlier results.
#   caffeinate -i ./rerun_fixed.sh
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${MODEL:-qwen2.5:7b-instruct}"
source .venv/bin/activate
pip install -q -r requirements.txt
export LLM_BACKEND=ollama LLM_MODEL="$MODEL" DATABASE_URL="sqlite:///data/dev.db" LLM_TIMEOUT=600
python data/make_heldout.py
python -m evaluation.run_eval --systems full --rubric-per-system 10
python -m evaluation.run_eval --cases data/heldout_cases.jsonl --systems full B0 B1 --rubric-per-system 0
for d in results/*/; do
  if [ -f "$d/summary.json" ]; then
    python -m evaluation.rescore "$d"
    python -m evaluation.safety_report "$d"
  fi
done
ZIP="qwen_results_run2_$(date +%Y%m%d-%H%M).zip"
zip -qr "$ZIP" results
echo "Done. Attach $ZIP in the chat."
