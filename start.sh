#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-neuro-bot}"
CONTAINER_NAME="${CONTAINER_NAME:-neuro-bot}"
SKIP_BUILD="${SKIP_BUILD:-0}"

# Resolve script directory so this works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="$SCRIPT_DIR/config.py"
CREDS_FILE="$SCRIPT_DIR/jenkins/credentials.ini"
JOB_CONFIG_FILE="$SCRIPT_DIR/jenkins/job_config.ini"
GROUPS_FILE="$SCRIPT_DIR/jenkins/groups.ini"

SECRETS_ENV_FILE="${SECRETS_ENV_FILE:-$HOME/.config/neuro-bot/secrets.env}"
LOCAL_ENV_FILE="$SCRIPT_DIR/.env.local"

load_env_file() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    echo "Loading secrets from $env_file"
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
}

sanitize_instance_key() {
  local raw="$1"
  echo "$raw" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g'
}

generate_config_py() {
  if [[ -f "$CONFIG_FILE" ]]; then
    return
  fi

  if [[ -z "${WEBEX_BOT_TOKEN:-}" || -z "${WEBEX_BOT_PERSON_ID:-}" ]]; then
    echo "Missing $CONFIG_FILE and required env vars WEBEX_BOT_TOKEN / WEBEX_BOT_PERSON_ID"
    exit 1
  fi

  umask 077
  cat >"$CONFIG_FILE" <<EOF
WEBEX_BOT_TOKEN = "${WEBEX_BOT_TOKEN}"
WEBEX_BOT_PERSON_ID = "${WEBEX_BOT_PERSON_ID}"
EOF
  chmod 600 "$CONFIG_FILE"
  echo "Generated local $CONFIG_FILE from environment variables"
}

generate_credentials_ini() {
  if [[ -f "$CREDS_FILE" ]]; then
    return
  fi

  mkdir -p "$(dirname "$CREDS_FILE")"
  umask 077

  if [[ -n "${JENKINS_CREDENTIALS_INI:-}" ]]; then
    printf '%s\n' "$JENKINS_CREDENTIALS_INI" >"$CREDS_FILE"
    chmod 600 "$CREDS_FILE"
    echo "Generated local $CREDS_FILE from JENKINS_CREDENTIALS_INI"
    return
  fi

  if [[ -n "${JENKINS_CREDENTIALS_INI_BASE64:-}" ]]; then
    printf '%s' "$JENKINS_CREDENTIALS_INI_BASE64" | base64 -d >"$CREDS_FILE"
    chmod 600 "$CREDS_FILE"
    echo "Generated local $CREDS_FILE from JENKINS_CREDENTIALS_INI_BASE64"
    return
  fi

  local instances
  instances=$(awk -F '=' '/^[[:space:]]*instance[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); if ($2 != "") print $2}' "$JOB_CONFIG_FILE" | sort -u)

  if [[ -z "$instances" ]]; then
    echo "No instances found in $JOB_CONFIG_FILE"
    exit 1
  fi

  : >"$CREDS_FILE"
  while IFS= read -r instance; do
    [[ -z "$instance" ]] && continue
    local key user_var token_var user_val token_val
    key=$(sanitize_instance_key "$instance")
    user_var="JENKINS_${key}_USERNAME"
    token_var="JENKINS_${key}_TOKEN"
    user_val="${!user_var:-}"
    token_val="${!token_var:-}"

    if [[ -z "$user_val" || -z "$token_val" ]]; then
      echo "Missing env vars for instance '$instance': $user_var and/or $token_var"
      echo "Either set those vars, or set JENKINS_CREDENTIALS_INI / JENKINS_CREDENTIALS_INI_BASE64"
      exit 1
    fi

    cat >>"$CREDS_FILE" <<EOF
[$instance]
username = $user_val
token = $token_val

EOF
  done <<<"$instances"

  chmod 600 "$CREDS_FILE"

  echo "Generated local $CREDS_FILE from per-instance environment variables"
}

load_env_file "$SECRETS_ENV_FILE"
load_env_file "$LOCAL_ENV_FILE"

generate_config_py
generate_credentials_ini

if [[ ! -f "$CONFIG_FILE" || ! -f "$CREDS_FILE" ]]; then
  echo "Required runtime files are missing after generation checks."
  exit 1
fi

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
  -v "$CONFIG_FILE:/app/config.py:ro"
  -v "$CREDS_FILE:/app/jenkins/credentials.ini:ro"
)

echo "Using image-bundled job/group config"

docker_cmd+=("$IMAGE_NAME")

"${docker_cmd[@]}" >/dev/null

echo "Container started successfully."
echo "Logs: docker logs -f $CONTAINER_NAME"
echo "Stop: docker rm -f $CONTAINER_NAME"
