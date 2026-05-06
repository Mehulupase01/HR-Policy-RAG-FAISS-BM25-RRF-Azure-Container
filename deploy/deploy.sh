#!/usr/bin/env bash
set -euo pipefail

export AZURE_CORE_NO_COLOR=1
export NO_COLOR=1
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1
export MSYS_NO_PATHCONV=1

# Microsoft docs checked before writing this script:
# - az containerapp create/update flags for --user-assigned, --registry-identity,
#   --secrets, --env-vars, --replace-env-vars, ingress, CPU/memory, and replicas:
#   https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest
# - az containerapp identity assign:
#   https://learn.microsoft.com/en-us/cli/azure/containerapp/identity?view=azure-cli-latest
# - az containerapp registry set with managed identity:
#   https://learn.microsoft.com/en-us/cli/azure/containerapp/registry?view=azure-cli-latest
# - Container Apps managed identity behavior and lifecycle:
#   https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
# - az containerapp logs show --tail:
#   https://learn.microsoft.com/en-us/cli/azure/containerapp/logs?view=azure-cli-latest

SUBSCRIPTION_ID="7550559f-20b4-4528-ab93-4add5a0d6c7d"
TENANT_ID="07f7e037-e81e-4516-ba96-62f787723bb0"
EXPECTED_ACCOUNT="upasemehul@gmail.com"

RESOURCE_GROUP="rg-rag-interview-mehul"
LOCATION="swedencentral"
ACR_BASENAME="acrragintvwmehul"
STORAGE_BASENAME="stragragintvwmehul"
CONTAINER_APP_ENV="cae-rag-interview"
CONTAINER_APP_NAME="hr-rag-app"
IMAGE_REPOSITORY="hr-rag-app"
SECRET_NAME_OPENAI_KEY="openai-key"
DEFAULT_BLOB_CONTAINER="rag-index"
INDEX_LOCAL_DIR="/tmp/index"
ACR_PULL_ROLE="AcrPull"

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
SETUP_RBAC_SCRIPT="${ROOT_DIR}/deploy/setup-rbac.sh"

log() {
  printf '\n==> %s\n' "$*"
}

dump_logs() {
  if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    printf '\n==> Last 50 console log lines for %s\n' "$CONTAINER_APP_NAME" >&2
    az containerapp logs show \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --tail 50 \
      --format text \
      --only-show-errors >&2 || true
  fi
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  dump_logs
  exit 1
}

on_error() {
  local line="$1"
  printf '\nERROR: deployment failed near line %s\n' "$line" >&2
  dump_logs
}
trap 'on_error "$LINENO"' ERR

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

read_env_value_or_default() {
  local key="$1"
  local default="$2"
  local line value

  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$default"
    return
  fi

  value="${line#*=}"
  value="${value%$'\r'}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "${value:-$default}"
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

  printf '%s' "${ACR_BASENAME}$(date +%m%d%H%M)"
}

ensure_acr() {
  ACR_NAME="$(pick_acr_name)"

  if az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "ACR exists: ${ACR_NAME}"
  else
    log "Creating ACR: ${ACR_NAME}"
    az acr create \
      --name "$ACR_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --sku Basic \
      --admin-enabled false \
      --only-show-errors >/dev/null
  fi

  ACR_LOGIN_SERVER="$(az acr show \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer \
    -o tsv \
    --only-show-errors | clean_az_output)"
  ACR_RESOURCE_ID="$(az acr show \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id \
    -o tsv \
    --only-show-errors | clean_az_output)"
}

build_image_in_acr() {
  IMAGE_TAG="phase11-$(date +%Y%m%d%H%M%S)"
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

find_storage_account_url() {
  local configured_url storage_account_name

  configured_url="$(read_env_value_or_default BLOB_ACCOUNT_URL "")"
  if [[ -n "$configured_url" && "$configured_url" != "<fill-here>" ]]; then
    printf '%s' "$configured_url"
    return
  fi

  storage_account_name="$(az storage account list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?starts_with(name, '${STORAGE_BASENAME}')].name | [0]" \
    -o tsv \
    --only-show-errors | clean_az_output || true)"
  [[ -n "$storage_account_name" ]] || fail "BLOB_ACCOUNT_URL is missing from .env and no storage account with prefix ${STORAGE_BASENAME} was found."

  az storage account show \
    --name "$storage_account_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query primaryEndpoints.blob \
    -o tsv \
    --only-show-errors | clean_az_output
}

run_setup_rbac() {
  [[ -x "$SETUP_RBAC_SCRIPT" || -f "$SETUP_RBAC_SCRIPT" ]] || fail "Missing ${SETUP_RBAC_SCRIPT}"
  log "Ensuring managed identity and Blob RBAC"
  MANAGED_IDENTITY_RESOURCE_ID="$(bash "$SETUP_RBAC_SCRIPT" | tail -n 1 | clean_az_output)"
  [[ -n "$MANAGED_IDENTITY_RESOURCE_ID" ]] || fail "setup-rbac.sh did not return a managed identity resource ID"

  MANAGED_IDENTITY_PRINCIPAL_ID="$(az identity show \
    --ids "$MANAGED_IDENTITY_RESOURCE_ID" \
    --query principalId \
    -o tsv \
    --only-show-errors | clean_az_output)"
  [[ -n "$MANAGED_IDENTITY_PRINCIPAL_ID" ]] || fail "Could not read managed identity principal ID"
}

ensure_acr_pull_role() {
  local existing

  existing="$(az role assignment list \
    --assignee-object-id "$MANAGED_IDENTITY_PRINCIPAL_ID" \
    --role "$ACR_PULL_ROLE" \
    --scope "$ACR_RESOURCE_ID" \
    --query "[0].id" \
    -o tsv \
    --only-show-errors | clean_az_output)"
  if [[ -n "$existing" ]]; then
    log "Role assignment exists: ${ACR_PULL_ROLE} at ACR scope"
    return
  fi

  log "Assigning ${ACR_PULL_ROLE} to managed identity for ACR image pulls"
  az role assignment create \
    --assignee-object-id "$MANAGED_IDENTITY_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "$ACR_PULL_ROLE" \
    --scope "$ACR_RESOURCE_ID" \
    --only-show-errors >/dev/null
}

deploy_container_app() {
  local openai_endpoint openai_key openai_api_version chat_deployment embedding_deployment
  local blob_account_url blob_container index_blob_prefix

  openai_endpoint="$(read_env_value AZURE_OPENAI_ENDPOINT)"
  openai_key="$(read_env_value AZURE_OPENAI_KEY)"
  openai_api_version="$(read_env_value AZURE_OPENAI_API_VERSION)"
  chat_deployment="$(read_env_value AZURE_OPENAI_CHAT_DEPLOYMENT)"
  embedding_deployment="$(read_env_value AZURE_OPENAI_EMBEDDING_DEPLOYMENT)"
  blob_account_url="$(find_storage_account_url)"
  blob_container="$(read_env_value_or_default BLOB_INDEX_CONTAINER "$DEFAULT_BLOB_CONTAINER")"
  index_blob_prefix="$(read_env_value_or_default INDEX_BLOB_PREFIX latest)"

  if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "Updating Container App: ${CONTAINER_APP_NAME}"

    az containerapp identity assign \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --user-assigned "$MANAGED_IDENTITY_RESOURCE_ID" \
      --only-show-errors >/dev/null

    az containerapp secret set \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --secrets "${SECRET_NAME_OPENAI_KEY}=${openai_key}" \
      --only-show-errors >/dev/null

    az containerapp registry set \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --server "$ACR_LOGIN_SERVER" \
      --identity "$MANAGED_IDENTITY_RESOURCE_ID" \
      --only-show-errors >/dev/null

    az containerapp update \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --image "$IMAGE" \
      --cpu 1.0 \
      --memory 2.0Gi \
      --min-replicas 1 \
      --max-replicas 3 \
      --replace-env-vars \
        "AZURE_OPENAI_ENDPOINT=${openai_endpoint}" \
        "AZURE_OPENAI_KEY=secretref:${SECRET_NAME_OPENAI_KEY}" \
        "AZURE_OPENAI_API_VERSION=${openai_api_version}" \
        "AZURE_OPENAI_CHAT_DEPLOYMENT=${chat_deployment}" \
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${embedding_deployment}" \
        "BLOB_ACCOUNT_URL=${blob_account_url}" \
        "BLOB_INDEX_CONTAINER=${blob_container}" \
        "INDEX_BLOB_PREFIX=${index_blob_prefix}" \
        "INDEX_LOCAL_DIR=${INDEX_LOCAL_DIR}" \
      --only-show-errors >/dev/null
  else
    log "Creating Container App: ${CONTAINER_APP_NAME}"

    az containerapp create \
      --name "$CONTAINER_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --environment "$CONTAINER_APP_ENV" \
      --image "$IMAGE" \
      --cpu 1.0 \
      --memory 2.0Gi \
      --min-replicas 1 \
      --max-replicas 3 \
      --ingress external \
      --target-port 8000 \
      --transport http \
      --registry-server "$ACR_LOGIN_SERVER" \
      --registry-identity "$MANAGED_IDENTITY_RESOURCE_ID" \
      --user-assigned "$MANAGED_IDENTITY_RESOURCE_ID" \
      --secrets "${SECRET_NAME_OPENAI_KEY}=${openai_key}" \
      --env-vars \
        "AZURE_OPENAI_ENDPOINT=${openai_endpoint}" \
        "AZURE_OPENAI_KEY=secretref:${SECRET_NAME_OPENAI_KEY}" \
        "AZURE_OPENAI_API_VERSION=${openai_api_version}" \
        "AZURE_OPENAI_CHAT_DEPLOYMENT=${chat_deployment}" \
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${embedding_deployment}" \
        "BLOB_ACCOUNT_URL=${blob_account_url}" \
        "BLOB_INDEX_CONTAINER=${blob_container}" \
        "INDEX_BLOB_PREFIX=${index_blob_prefix}" \
        "INDEX_LOCAL_DIR=${INDEX_LOCAL_DIR}" \
      --only-show-errors >/dev/null
  fi
}

app_fqdn() {
  az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv \
    --only-show-errors | clean_az_output
}

wait_for_endpoint() {
  local path="$1"
  local max_seconds="$2"
  local fqdn url deadline status_code body

  fqdn="$(app_fqdn)"
  [[ -n "$fqdn" ]] || fail "Could not fetch Container App FQDN"
  url="https://${fqdn}${path}"
  deadline=$((SECONDS + max_seconds))
  log "Waiting up to ${max_seconds}s for ${url}"

  while (( SECONDS < deadline )); do
    body="$(mktemp)"
    status_code="$(curl --silent --show-error --location --max-time 20 --output "$body" --write-out '%{http_code}' "$url" || true)"
    if [[ "$status_code" == "200" ]]; then
      printf '%s\n' "$(cat "$body")"
      rm -f "$body"
      return
    fi
    printf '%s returned %s; retrying...\n' "$path" "$status_code"
    rm -f "$body"
    sleep 10
  done

  fail "${path} did not return 200 within ${max_seconds}s"
}

main() {
  require_command az
  require_command bash
  require_command curl
  [[ -f "$ENV_FILE" ]] || fail "Missing ${ENV_FILE}"

  ensure_azure_login
  ensure_resource_group
  ensure_acr
  build_image_in_acr
  ensure_container_app_environment
  run_setup_rbac
  ensure_acr_pull_role
  deploy_container_app

  wait_for_endpoint "/healthz" 60
  wait_for_endpoint "/readyz" 90

  local fqdn
  fqdn="$(app_fqdn)"
  printf '\nDeployment succeeded.\n'
  printf 'App URL: https://%s\n' "$fqdn"
  printf 'Health URL: https://%s/healthz\n' "$fqdn"
  printf 'Ready URL: https://%s/readyz\n' "$fqdn"
}

main "$@"

: <<'OUT_OF_SCOPE'
This Phase 11 deploy script intentionally does not set up:
- custom domains or certificates
- CORS, authentication, authorization, rate limiting, WAF, or Front Door
- Application Insights, OpenTelemetry, dashboards, or alerts
- Key Vault references for secrets
- private networking, private endpoints, VNet integration, or IP restrictions
- production autoscaling rules beyond min/max replica bounds
- blue/green traffic splitting or canary promotion between revisions
- automated live eval runs against the deployed API
OUT_OF_SCOPE
