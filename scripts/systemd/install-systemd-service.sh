#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${1:-jbot}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/jbot.service"
OUTPUT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root: sudo $0 [service-name]"
  exit 1
fi

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "Missing template: $TEMPLATE_FILE"
  exit 1
fi

RUN_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

if [[ -z "$RUN_HOME" ]]; then
  echo "Unable to resolve home directory for user: $RUN_USER"
  exit 1
fi

sed \
  -e "s|__REPO_DIR__|$REPO_DIR|g" \
  -e "s|__RUN_USER__|$RUN_USER|g" \
  -e "s|__RUN_GROUP__|$RUN_GROUP|g" \
  -e "s|__RUN_HOME__|$RUN_HOME|g" \
  "$TEMPLATE_FILE" > "$OUTPUT_FILE"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo "Installed and started ${SERVICE_NAME}.service"
echo "Status: systemctl status ${SERVICE_NAME}.service"
echo "Logs: journalctl -u ${SERVICE_NAME}.service -f"
