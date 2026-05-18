#!/usr/bin/env bash
set -euo pipefail

export AZURE_CORE_NO_COLOR=1
export NO_COLOR=1
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1

# Microsoft CLI docs checked before writing this script:
# - az acr create/build/update: https://learn.microsoft.com/en-us/cli/azure/acr?view=azure-cli-latest
# - az containerapp env create: https://learn.microsoft.com/en-us/cli/azure/containerapp/env?view=azure-cli-latest
# - az containerapp create/update: https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest
# - az containerapp secret set: https://learn.microsoft.com/en-us/cli/azure/containerapp/secret?view=azure-cli-latest
# - az containerapp registry set: https://learn.microsoft.com/en-us/cli/azure/containerapp/registry?view=azure-cli-latest
# - az containerapp ingress enable: https://learn.microsoft.com/en-us/cli/azure/containerapp/ingress?view=azure-cli-latest
# - Container Apps env vars and secret refs: https://learn.microsoft.com/en-us/azure/container-apps/environment-variables

SUBSCRIPTION_ID="7550559f-20b4-4528-ab93-4add5a0d6c7d"
TENANT_ID="07f7e037-e81e-4516-ba96-62f787723bb0"
EXPECTED_ACCOUNT="upasemehul@gmail.com"

RESOURCE_GROUP="rg-hr-rag-mehul"
LOCATION="swedencentral"
ACR_BASENAME="acrragintvwmehul"
CONTAINER_APP_ENV="cae-hr-rag"
CONTAINER_APP_NAME="hr-rag-stub"
IMAGE_REPOSITORY="hr-rag-stub"
SECRET_NAME_OPENAI_KEY="openai-key"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  ROOT_DIR_FOR_AZ="$(cygpath -w "$ROOT_DIR")"
elif [[ "$ROOT_DIR" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
  drive_letter="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:lower:]' '[:upper:]')"
  rest_path="${BASH_REMATCH[2]//\//\\}"
  ROOT_DIR_FOR_AZ="${drive_letter}:\\${rest_path}"
else
  ROOT_DIR_FOR_AZ="$ROOT_DIR"
fi
ENV_FILE="${ROOT_DIR}/.env"

log() {
  printf '\n==> %s\n' "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

clean_az_output() {
  tr -d '\r'
}

read_env_value() {
  local key="$1"
  local line value

  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)"
  [[ -n "$line" ]] || fail "Required variable ${key} is missing from ${ENV_FILE}"

  value="${line#*=}"
  value="${value%$'\r'}"

  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi

  [[ -n "$value" && "$value" != "<fill-here>" && "$value" != "replace-me" ]] \
    || fail "Required variable ${key} in ${ENV_FILE} is empty or still a placeholder"

  printf '%s' "$value"
}

ensure_azure_login() {
  if ! az account show >/dev/null 2>&1; then
    log "Azure CLI is not logged in; opening login for tenant ${TENANT_ID}"
    az login --tenant "$TENANT_ID" --only-show-errors >/dev/null
  fi

  log "Selecting Azure subscription ${SUBSCRIPTION_ID}"
  az account set --subscription "$SUBSCRIPTION_ID" --only-show-errors

  local current_user
  current_user="$(az account show --query user.name -o tsv --only-show-errors | clean_az_output || true)"
  if [[ -n "$current_user" && "$current_user" != "$EXPECTED_ACCOUNT" ]]; then
    printf 'WARNING: Azure CLI account is "%s"; expected "%s". Continuing because the subscription is selected.\n' \
      "$current_user" "$EXPECTED_ACCOUNT" >&2
  fi
}

ensure_resource_group() {
  if az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "Resource group exists: ${RESOURCE_GROUP}"
  else
    log "Creating resource group: ${RESOURCE_GROUP}"
    az group create \
      --name "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --only-show-errors >/dev/null
  fi
}

pick_acr_name() {
  local existing candidate suffix available

  existing="$(az acr list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?starts_with(name, '${ACR_BASENAME}')].name | [0]" \
    -o tsv \
    --only-show-errors | clean_az_output || true)"

  if [[ -n "$existing" ]]; then
    printf '%s' "$existing"
    return
  fi

  candidate="$ACR_BASENAME"
  available="$(az acr check-name --name "$candidate" --query nameAvailable -o tsv --only-show-errors | clean_az_output)"
  if [[ "$available" == "true" ]]; then
    printf '%s' "$candidate"
    return
  fi

  suffix="${SUBSCRIPTION_ID//-/}"
  candidate="${ACR_BASENAME}${suffix:0:8}"
  available="$(az acr check-name --name "$candidate" --query nameAvailable -o tsv --only-show-errors | clean_az_output)"
  if [[ "$available" == "true" ]]; then
    printf '%s' "$candidate"
    return
  fi

  candidate="${ACR_BASENAME}$(date +%m%d%H%M)"
  printf '%s' "$candidate"
}

ensure_acr() {
  ACR_NAME="$(pick_acr_name)"

  if az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "ACR exists: ${ACR_NAME}"
    az acr update \
      --name "$ACR_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --admin-enabled true \
      --only-show-errors >/dev/null
  else
    log "Creating ACR: ${ACR_NAME}"
    az acr create \
      --name "$ACR_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --sku Basic \
      --admin-enabled true \
      --only-show-errors >/dev/null
  fi

  ACR_LOGIN_SERVER="$(az acr show \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer \
    -o tsv \
    --only-show-errors | clean_az_output)"
}

build_image_in_acr() {
  IMAGE_TAG="phase3-$(date +%Y%m%d%H%M%S)"
  IMAGE="${ACR_LOGIN_SERVER}/${IMAGE_REPOSITORY}:${IMAGE_TAG}"

  log "Building image in ACR: ${IMAGE}"
  MSYS_NO_PATHCONV=1 az acr build \
    --registry "$ACR_NAME" \
    --image "${IMAGE_REPOSITORY}:${IMAGE_TAG}" \
    --no-logs \
    "$ROOT_DIR_FOR_AZ" \
    --only-show-errors >/dev/null

  log "Waiting for ACR image tag to be available: ${IMAGE_TAG}"
  for _ in {1..80}; do
    if az acr repository show-tags \
      --name "$ACR_NAME" \
      --repository "$IMAGE_REPOSITORY" \
      --query "[?@=='${IMAGE_TAG}'] | [0]" \
      -o tsv \
      --only-show-errors | clean_az_output | grep -qx "$IMAGE_TAG"; then
      return
    fi
    sleep 15
  done

  fail "ACR build was queued, but image tag ${IMAGE_TAG} was not pushed within the retry window"
}

ensure_container_app_environment() {
  if az containerapp env show --name "$CONTAINER_APP_ENV" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "Container Apps environment exists: ${CONTAINER_APP_ENV}"
  else
    log "Creating Container Apps environment: ${CONTAINER_APP_ENV}"
    az containerapp env create \
      --name "$CONTAINER_APP_ENV" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --only-show-errors >/dev/null
  fi
}

deploy_container_app() {
  local openai_endpoint openai_key openai_api_version chat_deployment embedding_deployment
  local storage_account_url blob_container faiss_blob metadata_blob bm25_blob
  local acr_username acr_password

  openai_endpoint="$(read_env_value AZURE_OPENAI_ENDPOINT)"
  openai_key="$(read_env_value AZURE_OPENAI_KEY)"
  openai_api_version="$(read_env_value AZURE_OPENAI_API_VERSION)"
  chat_deployment="$(read_env_value AZURE_OPENAI_CHAT_DEPLOYMENT)"
  embedding_deployment="$(read_env_value AZURE_OPENAI_EMBEDDING_DEPLOYMENT)"
  storage_account_url="$(read_env_value AZURE_STORAGE_ACCOUNT_URL)"
  blob_container="$(read_env_value AZURE_BLOB_CONTAINER_NAME)"
  faiss_blob="$(read_env_value FAISS_INDEX_BLOB_NAME)"
  metadata_blob="$(read_env_value CHUNK_METADATA_BLOB_NAME)"
  bm25_blob="$(read_env_value BM25_BLOB_NAME)"

  acr_username="$(az acr credential show \
    --name "$ACR_NAME" \
    --query username \
    -o tsv \
    --only-show-errors | clean_az_output)"
  acr_password="$(az acr credential show \
    --name "$ACR_NAME" \
    --query 'passwords[0].value' \
    -o tsv \
    --only-show-errors | clean_az_output)"

  if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "Updating Container App: ${CONTAINER_APP_NAME}"

    az containerapp secret set \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --secrets "${SECRET_NAME_OPENAI_KEY}=${openai_key}" \
      --only-show-errors >/dev/null

    az containerapp registry set \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --server "$ACR_LOGIN_SERVER" \
      --username "$acr_username" \
      --password "$acr_password" \
      --only-show-errors >/dev/null

    az containerapp update \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --image "$IMAGE" \
      --cpu 0.5 \
      --memory 1.0Gi \
      --min-replicas 1 \
      --max-replicas 3 \
      --replace-env-vars \
        "AZURE_OPENAI_ENDPOINT=${openai_endpoint}" \
        "AZURE_OPENAI_KEY=secretref:${SECRET_NAME_OPENAI_KEY}" \
        "AZURE_OPENAI_API_VERSION=${openai_api_version}" \
        "AZURE_OPENAI_CHAT_DEPLOYMENT=${chat_deployment}" \
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${embedding_deployment}" \
        "AZURE_STORAGE_ACCOUNT_URL=${storage_account_url}" \
        "AZURE_BLOB_CONTAINER_NAME=${blob_container}" \
        "FAISS_INDEX_BLOB_NAME=${faiss_blob}" \
        "CHUNK_METADATA_BLOB_NAME=${metadata_blob}" \
        "BM25_BLOB_NAME=${bm25_blob}" \
      --only-show-errors >/dev/null

    az containerapp ingress enable \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --type external \
      --target-port 8000 \
      --transport http \
      --only-show-errors >/dev/null
  else
    log "Creating Container App: ${CONTAINER_APP_NAME}"

    az containerapp create \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --environment "$CONTAINER_APP_ENV" \
      --image "$IMAGE" \
      --cpu 0.5 \
      --memory 1.0Gi \
      --min-replicas 1 \
      --max-replicas 3 \
      --ingress external \
      --target-port 8000 \
      --transport http \
      --registry-server "$ACR_LOGIN_SERVER" \
      --registry-username "$acr_username" \
      --registry-password "$acr_password" \
      --secrets "${SECRET_NAME_OPENAI_KEY}=${openai_key}" \
      --env-vars \
        "AZURE_OPENAI_ENDPOINT=${openai_endpoint}" \
        "AZURE_OPENAI_KEY=secretref:${SECRET_NAME_OPENAI_KEY}" \
        "AZURE_OPENAI_API_VERSION=${openai_api_version}" \
        "AZURE_OPENAI_CHAT_DEPLOYMENT=${chat_deployment}" \
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${embedding_deployment}" \
        "AZURE_STORAGE_ACCOUNT_URL=${storage_account_url}" \
        "AZURE_BLOB_CONTAINER_NAME=${blob_container}" \
        "FAISS_INDEX_BLOB_NAME=${faiss_blob}" \
        "CHUNK_METADATA_BLOB_NAME=${metadata_blob}" \
        "BM25_BLOB_NAME=${bm25_blob}" \
      --only-show-errors >/dev/null
  fi
}

wait_for_healthz() {
  local fqdn url status_code

  fqdn="$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv \
    --only-show-errors | clean_az_output)"

  [[ -n "$fqdn" ]] || fail "Could not fetch Container App FQDN"

  url="https://${fqdn}/healthz"
  log "Waiting for /healthz: ${url}"

  for _ in {1..30}; do
    status_code="$(curl --silent --output /dev/null --write-out '%{http_code}' "$url" || true)"
    if [[ "$status_code" == "200" ]]; then
      printf '\nDeployment succeeded.\n'
      printf 'Health URL: %s\n' "$url"
      printf 'App URL: https://%s\n' "$fqdn"
      return
    fi
    printf 'healthz returned %s; retrying...\n' "$status_code"
    sleep 10
  done

  fail "/healthz did not return 200 within the retry window. Check logs with: az containerapp logs show -n ${CONTAINER_APP_NAME} -g ${RESOURCE_GROUP} --follow"
}

main() {
  require_command az
  require_command curl
  [[ -f "$ENV_FILE" ]] || fail "Missing ${ENV_FILE}"

  ensure_azure_login
  ensure_resource_group
  ensure_acr
  build_image_in_acr
  ensure_container_app_environment
  deploy_container_app
  wait_for_healthz
}

main "$@"

: <<'OUT_OF_SCOPE'
This Phase 3 stub deploy script intentionally does not set up:
- custom domains or certificates
- application authentication or authorization
- CORS, rate limiting, or WAF/front-door routing
- Application Insights, OpenTelemetry, dashboards, or alerting
- managed identity permissions for Blob Storage artifacts
- Key Vault integration
- private networking, private endpoints, or VNet integration
- production autoscaling rules beyond min/max replica bounds
- blue/green traffic splitting or multi-revision release strategy
- real RAG ingestion, retrieval, generation, citations, or evaluation
OUT_OF_SCOPE
