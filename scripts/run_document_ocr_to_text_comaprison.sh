#!/usr/bin/env bash
set -euo pipefail

# Example custom run:
# ./scripts/run_document_ocr_to_text_comaprison.sh \
#   --document-files /absolute/path/document.pdf \
#   --models gemini-2.0-flash gemini-3.1-flash-lite-preview \
#   --quality-model gemini-3.1-pro-preview \
#   --max-eval-chars 30000 \
#   --output-dir tests/output/document_ocr_to_text_comparison
#
# You can also pass --timeout-minutes N, --plain-text, --target-size N, --page-range 1:3, and/or --llm-api-key YOUR_KEY.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPARE_SCRIPT="$ROOT_DIR/tests/test_compare_document_ocr_to_text_models.py"
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
