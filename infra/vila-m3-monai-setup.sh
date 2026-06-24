#!/usr/bin/env bash
# Replaces `make demo_m3` with pinned PyTorch (avoids ncclCommResume symbol errors).
set -euo pipefail

ROOT="${VILA_M3_MONAI_ROOT:-/opt/VLM-Radiology-Agent-Framework}"
cd "${ROOT}"

echo "[monai-setup] Installing Python deps (torch already on image)…"
pip install -U pip setuptools wheel ninja packaging
pip install -U \
  python-dotenv gradio colored einops accelerate transformers sentencepiece \
  "monai[nibabel,pynrrd,scikit-image,fire,ignite]" \
  torchxrayvision huggingface_hub timm peft

echo "[monai-setup] Restoring base-image PyTorch (deps may upgrade torch)…"
pip install --force-reinstall \
  torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[monai-setup] Installing VILA (llava) from submodule…"
if [[ -f thirdparty/VILA/pyproject.toml ]] || [[ -f thirdparty/VILA/setup.py ]]; then
  pip install -e thirdparty/VILA
elif [[ -f thirdparty/VILA/environment_setup.sh ]]; then
  # environment_setup may pin deps; run only if editable install missing
  (cd thirdparty/VILA && ./environment_setup.sh) || pip install -e thirdparty/VILA
else
  echo "WARN: VILA submodule not found under thirdparty/VILA"
fi

echo "[monai-setup] Re-pinning PyTorch after VILA (VILA may downgrade torch)…"
pip install --force-reinstall \
  torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[monai-setup] Installing flash-attn (build against pinned torch 2.4.1+cu121)…"
MAX_JOBS="${MAX_JOBS:-$(nproc)}" pip install flash-attn==2.6.3 --no-build-isolation --force-reinstall --no-deps
python - <<'PY'
import flash_attn  # noqa: F401
import torch
print("[monai-setup] flash-attn OK, torch", torch.__version__, "cuda", torch.version.cuda)
PY

TXRV_DIR="${HOME}/.torchxrayvision/models_data"
mkdir -p "${TXRV_DIR}"
BASE="https://github.com/mlmed/torchxrayvision/releases/download/v1"
FILES=(
  nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  mimic_ch-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  mimic_nb-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  pc-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt
  pc-nih-rsna-siim-vin-resnet50-test512-e400-state.pt
)
for f in "${FILES[@]}"; do
  if [[ ! -f "${TXRV_DIR}/${f}" ]]; then
    echo "[monai-setup] Downloading TorchXRayVision ${f}…"
    wget -q --show-progress -O "${TXRV_DIR}/${f}" "${BASE}/${f}"
  fi
done

BUNDLE_DIR="${HOME}/.cache/torch/hub/bundle"
mkdir -p "${BUNDLE_DIR}"
echo "[monai-setup] Downloading MONAI VISTA3D + BraTS bundles…"
python -m monai.bundle download vista3d --version 0.5.4 --bundle_dir "${BUNDLE_DIR}"
python -m monai.bundle download brats_mri_segmentation --version 0.5.2 --bundle_dir "${BUNDLE_DIR}"
if [[ -f "${BUNDLE_DIR}/vista3d_v0.5.4.zip" ]]; then
  unzip -qo "${BUNDLE_DIR}/vista3d_v0.5.4.zip" -d "${BUNDLE_DIR}/vista3d_v0.5.4"
fi

python - <<'PY'
import torch
print("[monai-setup] torch", torch.__version__, "cuda", torch.cuda.is_available())
import monai
print("[monai-setup] monai", monai.__version__)
PY

echo "[monai-setup] Done."
