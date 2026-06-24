#!/usr/bin/env bash
# Lumira — start the full stack (frontend, backend API, Celery worker, VILA-M3 model, infra).
#
# Usage:
#   ./run.sh              Start everything (auto GPU if available)
#   ./run.sh start        Same as above
#   ./run.sh start --gpu  Force full VILA-M3 GPU mode
#   ./run.sh start --lite Force VILA-M3 lite (CPU) mode
#   ./run.sh start -f     Foreground (attach logs, Ctrl+C to stop)
#   ./run.sh stop         Stop all services
#   ./run.sh restart      Rebuild and restart
#   ./run.sh status       Show container status + VILA-M3 health
#   ./run.sh logs         Follow all service logs
#   ./run.sh logs api     Follow one service (api, web, worker, vila-m3, …)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

COMPOSE_BASE="docker-compose.yml"
COMPOSE_GPU="docker-compose.gpu.yml"
ENV_FILE=".env"
USE_GPU="auto"   # auto | 1 | 0
FOREGROUND=0
NO_BUILD=0
DOWNLOAD_MODEL=0

log() { printf '\033[1;34m[lumira]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[lumira]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[lumira]\033[0m %s\n' "$*" >&2; }

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

need_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker is required. Install Docker and try again."
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    err "Docker Compose v2 is required (docker compose)."
    exit 1
  fi
}

host_has_gpu() {
  command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1
}

docker_gpu_ready() {
  docker info 2>/dev/null | grep -qi 'nvidia'
}

checkpoint_ready() {
  local path="${1:-./data/checkpoints/Llama3-VILA-M3-8B}"
  [[ -d "$path/llm" ]] && compgen -G "$path/llm/*.safetensors" >/dev/null 2>&1
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating $ENV_FILE from .env.example"
    cp .env.example "$ENV_FILE"
  fi
}

resolve_gpu_mode() {
  case "$USE_GPU" in
    1)
      if ! host_has_gpu; then
        err "--gpu requested but no NVIDIA GPU found on this host."
        exit 1
      fi
      if ! docker_gpu_ready; then
        err "GPU requested but Docker has no NVIDIA runtime."
        err "Run: sudo ./scripts/install-nvidia-container-toolkit.sh"
        exit 1
      fi
      echo 1
      ;;
    0) echo 0 ;;
    auto)
      if host_has_gpu && docker_gpu_ready; then
        echo 1
      else
        echo 0
      fi
      ;;
    *) echo 0 ;;
  esac
}

compose() {
  local gpu="$1"
  shift
  local args=(docker compose -f "$COMPOSE_BASE")
  if [[ "$gpu" -eq 1 ]]; then
    args+=(-f "$COMPOSE_GPU")
  fi
  "${args[@]}" "$@"
}

maybe_download_checkpoint() {
  if [[ "$DOWNLOAD_MODEL" -eq 0 ]]; then
    return
  fi
  if checkpoint_ready; then
    log "VILA-M3 checkpoint already present."
    return
  fi
  log "Downloading VILA-M3 checkpoint (this may take a while)…"
  bash ./scripts/download-vila-checkpoint.sh
}

print_urls() {
  cat <<'EOF'

  Lumira is running:

    Web app (frontend)  http://localhost:5173
    API (backend)       http://localhost:8000/docs
    VILA-M3 (model)     http://localhost:8100/health
    MinIO console       http://localhost:9001
    Flower (Celery)     http://localhost:5555
    Adminer (database)  http://localhost:8080

  Login: admin@lumira.dev / admin12345

EOF
}

print_vila_health() {
  if curl -sf http://localhost:8100/health >/dev/null 2>&1; then
    local health
    health="$(curl -sf http://localhost:8100/health)"
    log "VILA-M3: $health"
  else
    warn "VILA-M3 health endpoint not reachable yet."
  fi
}

wait_for_core() {
  local tries=60
  log "Waiting for API and VILA-M3 to become healthy…"
  while (( tries > 0 )); do
    local api_ok=0 vila_ok=0
    curl -sf http://localhost:8000/health >/dev/null 2>&1 && api_ok=1
    curl -sf http://localhost:8100/health >/dev/null 2>&1 && vila_ok=1
    if [[ "$api_ok" -eq 1 && "$vila_ok" -eq 1 ]]; then
      print_vila_health
      return 0
    fi
    sleep 3
    tries=$((tries - 1))
  done
  warn "Timed out waiting for health checks. Check: ./run.sh logs"
}

cmd_start() {
  need_docker
  ensure_env

  local gpu
  gpu="$(resolve_gpu_mode)"

  if [[ "$gpu" -eq 1 ]]; then
    log "Mode: GPU (full VILA-M3)"
    if ! checkpoint_ready; then
      warn "Checkpoint not found at ./data/checkpoints/Llama3-VILA-M3-8B"
      warn "Run: ./scripts/download-vila-checkpoint.sh"
      warn "Or:  ./run.sh start --download-model"
    fi
    maybe_download_checkpoint
  else
    log "Mode: lite (CPU VILA-M3 demo — no GPU passthrough)"
    if host_has_gpu && ! docker_gpu_ready; then
      warn "NVIDIA GPU detected but Docker GPU runtime is not configured."
      warn "For full model: sudo ./scripts/install-nvidia-container-toolkit.sh"
      warn "Then:         ./run.sh start --gpu"
    fi
  fi

  local up_args=(up)
  if [[ "$FOREGROUND" -eq 0 ]]; then
    up_args+=(-d)
  fi
  if [[ "$NO_BUILD" -eq 0 ]]; then
    up_args+=(--build)
  fi

  log "Starting stack (postgres, redis, minio, api, worker, web, vila-m3)…"
  compose "$gpu" "${up_args[@]}"

  if [[ "$FOREGROUND" -eq 0 ]]; then
    wait_for_core
    print_urls
    log "Follow logs: ./run.sh logs"
  fi
}

cmd_stop() {
  need_docker
  local gpu
  gpu="$(resolve_gpu_mode)"
  log "Stopping all services…"
  compose "$gpu" down
}

cmd_restart() {
  cmd_stop || true
  cmd_start
}

cmd_status() {
  need_docker
  local gpu
  gpu="$(resolve_gpu_mode)"
  compose "$gpu" ps
  echo ""
  curl -sf http://localhost:8000/health 2>/dev/null && log "API: ok" || warn "API: not reachable"
  print_vila_health
}

cmd_logs() {
  need_docker
  local gpu service="${1:-}"
  gpu="$(resolve_gpu_mode)"
  if [[ -n "$service" ]]; then
    compose "$gpu" logs -f "$service"
  else
    compose "$gpu" logs -f
  fi
}

# --- parse global flags then subcommand ---
CMD="${1:-start}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpu) USE_GPU=1; shift ;;
    --lite) USE_GPU=0; shift ;;
    --download-model) DOWNLOAD_MODEL=1; shift ;;
    -f|--foreground) FOREGROUND=1; shift ;;
    --no-build) NO_BUILD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

case "$CMD" in
  start|up) cmd_start "$@" ;;
  stop|down) cmd_stop "$@" ;;
  restart) cmd_restart "$@" ;;
  status|ps) cmd_status "$@" ;;
  logs) cmd_logs "$@" ;;
  help|-h|--help) usage ;;
  *)
    err "Unknown command: $CMD"
    usage
    exit 1
    ;;
esac
