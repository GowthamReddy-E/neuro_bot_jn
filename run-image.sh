#!/usr/bin/env bash
set -euo pipefail

# Run a prebuilt image with local secret/config volumes.
# Usage:
#   ./run-image.sh <image-name> [container-name]
# Example:
#   ./run-image.sh neuro-bot:latest neuro-bot

IMAGE_NAME="${1:-neuro-bot}"
CONTAINER_NAME="${2:-neuro-bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKIP_BUILD=1 IMAGE_NAME="$IMAGE_NAME" CONTAINER_NAME="$CONTAINER_NAME" "$SCRIPT_DIR/start.sh"
