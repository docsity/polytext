#!/usr/bin/env bash
set -euo pipefail

# Example custom run:
# ./scripts/run_audio_model_comparison.sh \
#   --audio-files /Users/marcodelgiudice/Projects/polytext/audio_8_barbero_0_5_ore.m4a \
#   --gcs-video-files gcs://opit-da-test-ml-ai-store-bucket/learning_resources/course_id=132/module_id=312/id=4020/2333.mp4 \
#   --models gemini-2.0-flash gemini-3.1-flash-lite-preview \
#   --quality-model gemini-3.1-pro-preview \
#   --max-eval-chars 30000 \
#   --save-raw-chunks-files \
#   --output-dir test_performance/audio_model_comparison
#
# You can also pass --timeout-minutes N, --llm-api-key YOUR_KEY, or --no-markdown-output.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPARE_SCRIPT="$ROOT_DIR/tests/test_compare_audio_models.py"
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

# Ensure ffmpeg can be discovered on macOS homebrew installs.
if [[ -d "/opt/homebrew/bin" ]]; then
  export PATH="/opt/homebrew/bin:$PATH"
fi

cd "$ROOT_DIR"
exec "$PYTHON_BIN" "$COMPARE_SCRIPT" "$@"
