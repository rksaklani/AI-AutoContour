#!/usr/bin/env bash
# Download MONAI VILA-M3 checkpoints into a local directory (GPU host volume).
set -euo pipefail

MODEL_ID="${1:-MONAI/Llama3-VILA-M3-8B}"
OUT_DIR="${2:-./data/checkpoints/Llama3-VILA-M3-8B}"

echo "Downloading ${MODEL_ID} → ${OUT_DIR}"
mkdir -p "${OUT_DIR}"

if command -v hf >/dev/null 2>&1; then
  hf download "${MODEL_ID}" --local-dir "${OUT_DIR}"
elif command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "${MODEL_ID}" --local-dir "${OUT_DIR}"
elif python3 -c "import huggingface_hub" 2>/dev/null; then
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download("${MODEL_ID}", local_dir="${OUT_DIR}")
PY
else
  echo "Install huggingface_hub: pip install huggingface_hub"
  exit 1
fi

echo "Done. Set VILA_M3_MODEL_PATH=${OUT_DIR} and VILA_M3_MODE=vila"
