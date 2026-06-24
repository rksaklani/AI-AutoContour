FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/vila-m3/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/vila-m3/ .

ENV VILA_M3_MODE=lite
ENV VILA_M3_PORT=8100

EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -f http://localhost:8100/health || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
