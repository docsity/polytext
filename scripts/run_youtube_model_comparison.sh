#!/usr/bin/env bash
set -euo pipefail

# Example custom run:
# ./scripts/run_youtube_model_comparison.sh \
#   --youtube-urls https://www.youtube.com/watch?v=6Ql5mQdxeWk \
#   --models models/gemini-2.5-flash models/gemini-3.1-flash-lite-preview \
#   --quality-model gemini-3.1-pro-preview \
#   --max-eval-chars 30000 \
#   --output-dir tests/output/youtube_model_comparison
#
# You can also pass --timeout-minutes N and/or --llm-api-key YOUR_KEY.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPARE_SCRIPT="$ROOT_DIR/tests/test_compare_youtube_models.py"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -f "$COMPARE_SCRIPT" ]]; then
  echo "Comparison script not found: $COMPARE_SCRIPT" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "Python interpreter not found. Set PYTHON_BIN or create .venv." >&2
    exit 1
  fi
fi

cd "$ROOT_DIR"
exec "$PYTHON_BIN" "$COMPARE_SCRIPT" "$@"
