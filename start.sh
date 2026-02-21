#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="neuro-bot"
CONTAINER_NAME="neuro-bot"

# Resolve script directory so this works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="$SCRIPT_DIR/config.py"
CREDS_FILE="$SCRIPT_DIR/jenkins/credentials.ini"
JOB_CONFIG_FILE="$SCRIPT_DIR/jenkins/job_config.ini"
GROUPS_FILE="$SCRIPT_DIR/jenkins/groups.ini"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing $CONFIG_FILE"
  echo "Create it from config.py.example first."
  exit 1
fi

if [[ ! -f "$CREDS_FILE" ]]; then
  echo "Missing $CREDS_FILE"
  echo "Create it from jenkins/credentials.ini.example first."
  exit 1
fi

echo "[1/3] Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "[2/3] Removing existing container: $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
else
  echo "[2/3] No existing container to remove"
fi

echo "[3/3] Starting container: $CONTAINER_NAME"
docker run -d --name "$CONTAINER_NAME" \
  -v "$CONFIG_FILE:/app/config.py:ro" \
  -v "$CREDS_FILE:/app/jenkins/credentials.ini:ro" \
  -v "$JOB_CONFIG_FILE:/app/jenkins/job_config.ini:ro" \
  -v "$GROUPS_FILE:/app/jenkins/groups.ini:ro" \
  "$IMAGE_NAME" >/dev/null

echo "Container started successfully."
echo "Logs: docker logs -f $CONTAINER_NAME"
echo "Stop: docker rm -f $CONTAINER_NAME"
