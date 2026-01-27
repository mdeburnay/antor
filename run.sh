#!/bin/bash
# Start Anki (if on macOS) then run Antor. Run from anywhere:
#   /path/to/antor/run.sh
# or from inside the project: ./run.sh
cd "$(dirname "$0")"
if [[ "$(uname)" == Darwin ]]; then
  open -a Anki 2>/dev/null || true
  echo "Waiting for Anki to start…"
  sleep 3
fi
exec python3 -m streamlit run app.py
