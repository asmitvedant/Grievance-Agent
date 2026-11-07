#!/usr/bin/env bash
# One-click start for Mac / Linux. Sets everything up the first time, then opens both apps in your browser:
#   student app on http://localhost:8501, staff portal (reviewers + admin) on http://localhost:8502
#   ./start_app.sh            # with Qwen (needs the Ollama app)
#   MOCK=1 ./start_app.sh     # look at the screens without Qwen (replies come from a test stub)
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 Settings"
if [ ! -f .env ]; then
  # first run: copy the template and use SQLite so no database server is needed
  sed 's#^DATABASE_URL=mysql.*#DATABASE_URL=sqlite:///data/dev.db#' .env.example > .env
  echo "Created .env (SQLite database in data/dev.db). Edit .env to change the password, college name or model."
fi
MODEL="$(grep -E '^LLM_MODEL=' .env | head -1 | cut -d= -f2 | awk '{print $1}')"
MODEL="${MODEL:-qwen2.5:7b-instruct}"

echo "== 2/4 Python"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Python 3.10 or newer is needed. On a Mac: brew install python@3.12 (or python.org)."; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  touch .venv/.installed
fi

if [ "${MOCK:-0}" = "1" ]; then
  export LLM_BACKEND=mock
  echo "== 3/4 MOCK=1: skipping Qwen (replies come from a test stub)"
else
  echo "== 3/4 Qwen through Ollama ($MODEL)"
  command -v ollama >/dev/null || { echo "Install Ollama from https://ollama.com/download, open it once, then run this again."; exit 1; }
  curl -sf http://localhost:11434/api/tags >/dev/null || { (ollama serve >/dev/null 2>&1 &); sleep 6; }
  ollama list | grep -q "^${MODEL}" || ollama pull "$MODEL"
fi

echo "== 4/4 Local embedding + NLI models (downloaded once)"
python scripts/download_models.py || echo "   Could not download them; the app will use simpler offline stand-ins."

echo
echo "Student app:   http://localhost:8501"
echo "Staff portal:  http://localhost:8502   (reviewers and admins; password: REVIEWER_PASSWORD in .env, default change-me)"
echo "Press Ctrl+C here to stop both."
streamlit run app/staff_app.py --server.port 8502 --server.headless true --theme.primaryColor "#5856D6" &
STAFF_PID=$!
trap 'kill $STAFF_PID 2>/dev/null' EXIT INT TERM
(sleep 4; command -v open >/dev/null && open http://localhost:8502) &
streamlit run app/student_app.py --server.port 8501 --server.headless false
