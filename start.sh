#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-neuro-bot}"
CONTAINER_NAME="${CONTAINER_NAME:-neuro-bot}"
SKIP_BUILD="${SKIP_BUILD:-0}"

# Resolve script directory so this works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

JOB_CONFIG_FILE="$SCRIPT_DIR/app/services/jenkins/config/job_config.ini"

SECRETS_ENV_FILE="${SECRETS_ENV_FILE:-$HOME/.config/neuro-bot/secrets.env}"

if [[ ! -f "$SECRETS_ENV_FILE" ]]; then
  echo "Missing required secrets file: $SECRETS_ENV_FILE"
  echo "Create it with WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID and JENKINS_<INSTANCE>_USERNAME/TOKEN values."
  exit 1
fi

echo "Using secrets from $SECRETS_ENV_FILE"

# Validate required keys before launching container.
set -a
# shellcheck disable=SC1090
source "$SECRETS_ENV_FILE"
set +a

if [[ -z "${WEBEX_BOT_TOKEN:-}" || -z "${WEBEX_BOT_PERSON_ID:-}" ]]; then
  echo "Missing required variables in $SECRETS_ENV_FILE: WEBEX_BOT_TOKEN / WEBEX_BOT_PERSON_ID"
  exit 1
fi

instances=$(awk -F '=' '/^[[:space:]]*instance[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); if ($2 != "") print $2}' "$JOB_CONFIG_FILE" | sort -u)
if [[ -z "$instances" ]]; then
  echo "No instances found in $JOB_CONFIG_FILE"
  exit 1
fi

for instance in $instances; do
  key=$(echo "$instance" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')
  user_var="JENKINS_${key}_USERNAME"
  token_var="JENKINS_${key}_TOKEN"
  if [[ -z "${!user_var:-}" || -z "${!token_var:-}" ]]; then
    echo "Missing required variables in $SECRETS_ENV_FILE: $user_var / $token_var"
    exit 1
  fi
done

if [[ "$SKIP_BUILD" == "1" ]]; then
  echo "[1/3] Skipping image build (SKIP_BUILD=1), using image: $IMAGE_NAME"
else
  echo "[1/3] Building Docker image: $IMAGE_NAME"
  docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "[2/3] Removing existing container: $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
else
  echo "[2/3] No existing container to remove"
fi

echo "[3/3] Starting container: $CONTAINER_NAME"
docker_cmd=(
  docker run -d --name "$CONTAINER_NAME"
  --user "$(id -u):$(id -g)"
  --env-file "$SECRETS_ENV_FILE"
)

echo "Using image-bundled job/group config"
echo "Injecting secrets via --env-file"

docker_cmd+=("$IMAGE_NAME")

"${docker_cmd[@]}" >/dev/null

echo "Container started successfully."
echo "Logs: docker logs -f $CONTAINER_NAME"
echo "Stop: docker rm -f $CONTAINER_NAME"
