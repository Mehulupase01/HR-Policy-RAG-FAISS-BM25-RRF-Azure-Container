#!/usr/bin/env bash
set -euo pipefail

# Microsoft CLI docs checked before writing this script:
# - az storage account create flags including --kind, --sku, and --allow-blob-public-access:
#   https://learn.microsoft.com/en-us/cli/azure/storage/account?view=azure-cli-latest
# - az storage container create with Microsoft Entra login auth:
#   https://learn.microsoft.com/en-us/azure/storage/blobs/blob-containers-cli
#   https://learn.microsoft.com/en-us/azure/storage/blobs/authorize-data-operations-cli

SUBSCRIPTION_ID="7550559f-20b4-4528-ab93-4add5a0d6c7d"
TENANT_ID="07f7e037-e81e-4516-ba96-62f787723bb0"
RESOURCE_GROUP="rg-hr-rag-mehul"
LOCATION="swedencentral"
STORAGE_BASENAME="stragragintvwmehul"
CONTAINER_NAME="rag-index"

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

ensure_azure_login() {
  if ! az account show >/dev/null 2>&1; then
    log "Azure CLI is not logged in; opening login for tenant ${TENANT_ID}"
    az login --tenant "$TENANT_ID" --only-show-errors >/dev/null
  fi

  log "Selecting Azure subscription ${SUBSCRIPTION_ID}"
  az account set --subscription "$SUBSCRIPTION_ID" --only-show-errors
}

pick_storage_name() {
  local existing candidate suffix available

  existing="$(az storage account list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?starts_with(name, '${STORAGE_BASENAME}')].name | [0]" \
    -o tsv \
    --only-show-errors | clean_az_output || true)"

  if [[ -n "$existing" ]]; then
    printf '%s' "$existing"
    return
  fi

  candidate="$STORAGE_BASENAME"
  available="$(az storage account check-name \
    --name "$candidate" \
    --query nameAvailable \
    -o tsv \
    --only-show-errors | clean_az_output)"
  if [[ "$available" == "true" ]]; then
    printf '%s' "$candidate"
    return
  fi

  suffix="${SUBSCRIPTION_ID//-/}"
  candidate="${STORAGE_BASENAME}${suffix:0:5}"
  printf '%s' "$candidate"
}

ensure_storage_account() {
  STORAGE_ACCOUNT_NAME="$(pick_storage_name)"

  if az storage account show \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "Storage account exists: ${STORAGE_ACCOUNT_NAME}"
  else
    log "Creating StorageV2 account: ${STORAGE_ACCOUNT_NAME}"
    az storage account create \
      --name "$STORAGE_ACCOUNT_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --kind StorageV2 \
      --sku Standard_LRS \
      --allow-blob-public-access false \
      --only-show-errors >/dev/null
  fi

  STORAGE_ACCOUNT_URL="$(az storage account show \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "primaryEndpoints.blob" \
    -o tsv \
    --only-show-errors | clean_az_output)"
}

ensure_container() {
  log "Creating private blob container if missing: ${CONTAINER_NAME}"
  az storage container create \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --name "$CONTAINER_NAME" \
    --auth-mode login \
    --only-show-errors >/dev/null
}

main() {
  require_command az
  ensure_azure_login
  ensure_storage_account
  ensure_container

  printf '\nStorage setup complete.\n'
  printf 'BLOB_ACCOUNT_URL=%s\n' "$STORAGE_ACCOUNT_URL"
  printf 'BLOB_INDEX_CONTAINER=%s\n' "$CONTAINER_NAME"
}

main "$@"

# Role assignment for the Container App user-assigned managed identity is handled
# by deploy/setup-rbac.sh in Phase 11.
