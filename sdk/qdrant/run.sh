#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# Local Qdrant vector database management
#
# Usage:
#   ./qdrant/run.sh start    # Start Qdrant (foreground, Ctrl+C to stop)
#   ./qdrant/run.sh status   # Show container status
#   ./qdrant/run.sh stop     # Stop and remove container
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="qdrant-local"
DATA_DIR="$SCRIPT_DIR/data"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_GRPC_PORT="${QDRANT_GRPC_PORT:-6334}"
QDRANT_IMAGE="qdrant/qdrant:latest"

# Load optional .env
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

mkdir -p "$DATA_DIR"

case "${1:-help}" in
  start)
    echo "Starting Qdrant on http://localhost:$QDRANT_PORT ..."
    docker run --rm \
      --name "$CONTAINER_NAME" \
      -p "$QDRANT_PORT:6333" \
      -p "$QDRANT_GRPC_PORT:6334" \
      -v "$DATA_DIR:/qdrant/storage" \
      ${QDRANT_API_KEY:+-e QDRANT__SERVICE__API_KEY="$QDRANT_API_KEY"} \
      "$QDRANT_IMAGE"
    ;;
  status)
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    ;;
  stop)
    echo "Stopping $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || echo "Container not running."
    ;;
  *)
    echo "Usage: $0 {start|status|stop}"
    ;;
esac
