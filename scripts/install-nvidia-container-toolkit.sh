#!/usr/bin/env bash
# Install NVIDIA Container Toolkit on Ubuntu (required for docker compose GPU).
# Run: sudo ./scripts/install-nvidia-container-toolkit.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  > /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update
apt-get install -y nvidia-container-toolkit

nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

echo ""
echo "OK — verify with:"
echo "  docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi"
echo "  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d vila-m3"
echo "  curl http://localhost:8100/health"
