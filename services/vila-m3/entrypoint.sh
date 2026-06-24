#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${VILA_M3_MODEL_PATH:-/data/checkpoints/Llama3-VILA-M3-8B}"
MODEL_ID="${VILA_M3_MODEL_ID:-MONAI/Llama3-VILA-M3-8B}"

if [[ "${VILA_M3_MODE:-lite}" == "vila" ]]; then
  if [[ ! -d "${MODEL_PATH}" ]] || [[ -z "$(ls -A "${MODEL_PATH}" 2>/dev/null || true)" ]]; then
    echo "[vila-m3] Checkpoint not found at ${MODEL_PATH}; downloading ${MODEL_ID}…"
    mkdir -p "${MODEL_PATH}"
    python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download("${MODEL_ID}", local_dir="${MODEL_PATH}")
PY
    echo "[vila-m3] Checkpoint ready at ${MODEL_PATH}"
  else
    echo "[vila-m3] Using checkpoint at ${MODEL_PATH}"
  fi
fi

exec python -m uvicorn main:app --host 0.0.0.0 --port "${VILA_M3_PORT:-8100}"
