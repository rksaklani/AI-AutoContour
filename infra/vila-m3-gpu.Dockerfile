# Lumira VILA-M3 GPU image — MONAI VLM-Radiology-Agent-Framework + Lumira sidecar.
# Base: official PyTorch CUDA image (avoids NCCL symbol mismatch on bare cuda:devel).

FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive
ENV VILA_M3_MONAI_ROOT=/opt/VLM-Radiology-Agent-Framework
ENV VILA_M3_MODE=vila
ENV VILA_M3_PORT=8100
ENV VILA_M3_MODEL_PATH=/data/checkpoints/Llama3-VILA-M3-8B
ENV VILA_M3_MODEL_ID=MONAI/Llama3-VILA-M3-8B
ENV VILA_M3_SOURCE=local
ENV VILA_M3_CONV_MODE=llama_3
ENV HF_HOME=/data/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl git unzip libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --recursive https://github.com/Project-MONAI/VLM-Radiology-Agent-Framework \
    "${VILA_M3_MONAI_ROOT}"

COPY infra/vila-m3-monai-setup.sh /tmp/vila-m3-monai-setup.sh
RUN chmod +x /tmp/vila-m3-monai-setup.sh && /tmp/vila-m3-monai-setup.sh

WORKDIR /app
COPY services/vila-m3/ /app/
RUN pip install --no-cache-dir -r requirements-gpu.txt && chmod +x /app/entrypoint.sh

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=600s --retries=10 \
  CMD curl -f http://localhost:8100/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
