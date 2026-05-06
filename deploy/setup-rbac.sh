#!/usr/bin/env bash
set -euo pipefail

export AZURE_CORE_NO_COLOR=1
export NO_COLOR=1
export MSYS_NO_PATHCONV=1

# Microsoft docs checked before writing this script:
# - User-assigned managed identities in Container Apps:
#   https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
# - az identity create/show:
#   https://learn.microsoft.com/en-us/cli/azure/identity?view=azure-cli-latest
# - az role assignment create/list:
#   https://learn.microsoft.com/en-us/cli/azure/role/assignment?view=azure-cli-latest
# - Azure RBAC scope guidance:
#   https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments

SUBSCRIPTION_ID="7550559f-20b4-4528-ab93-4add5a0d6c7d"
TENANT_ID="07f7e037-e81e-4516-ba96-62f787723bb0"
RESOURCE_GROUP="rg-rag-interview-mehul"
LOCATION="swedencentral"
IDENTITY_NAME="id-rag-app"
STORAGE_BASENAME="stragragintvwmehul"
BLOB_CONTAINER_NAME="rag-index"
STORAGE_READER_ROLE="Storage Blob Data Reader"

log() {
  printf '\n==> %s\n' "$*" >&2
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

ensure_identity() {
  if az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log "User-assigned managed identity exists: ${IDENTITY_NAME}"
  else
    log "Creating user-assigned managed identity: ${IDENTITY_NAME}"
    az identity create \
      --name "$IDENTITY_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --only-show-errors >/dev/null
  fi

  IDENTITY_RESOURCE_ID="$(az identity show \
    --name "$IDENTITY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id \
    -o tsv \
    --only-show-errors | clean_az_output)"
  IDENTITY_PRINCIPAL_ID="$(az identity show \
    --name "$IDENTITY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query principalId \
    -o tsv \
    --only-show-errors | clean_az_output)"

  [[ -n "$IDENTITY_RESOURCE_ID" ]] || fail "Could not read managed identity resource ID"
  [[ -n "$IDENTITY_PRINCIPAL_ID" ]] || fail "Could not read managed identity principal ID"
}

find_storage_account() {
  STORAGE_ACCOUNT_NAME="$(az storage account list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?starts_with(name, '${STORAGE_BASENAME}')].name | [0]" \
    -o tsv \
    --only-show-errors | clean_az_output || true)"

  [[ -n "$STORAGE_ACCOUNT_NAME" ]] || fail "No storage account found in ${RESOURCE_GROUP} with prefix ${STORAGE_BASENAME}. Run deploy/setup-storage.sh first."

  STORAGE_ACCOUNT_ID="$(az storage account show \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id \
    -o tsv \
    --only-show-errors | clean_az_output)"
  BLOB_CONTAINER_SCOPE="${STORAGE_ACCOUNT_ID}/blobServices/default/containers/${BLOB_CONTAINER_NAME}"
}

role_assignment_exists() {
  local role="$1"
  local scope="$2"

  az role assignment list \
    --assignee-object-id "$IDENTITY_PRINCIPAL_ID" \
    --role "$role" \
    --scope "$scope" \
    --query "[0].id" \
    -o tsv \
    --only-show-errors | clean_az_output
}

ensure_role_assignment() {
  local role="$1"
  local scope="$2"

  if [[ -n "$(role_assignment_exists "$role" "$scope")" ]]; then
    log "Role assignment exists: ${role} at ${scope}"
    return
  fi

  log "Assigning role: ${role} at ${scope}"
  az role assignment create \
    --assignee-object-id "$IDENTITY_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "$role" \
    --scope "$scope" \
    --only-show-errors >/dev/null
}

main() {
  require_command az
  ensure_azure_login
  ensure_identity
  find_storage_account
  ensure_role_assignment "$STORAGE_READER_ROLE" "$BLOB_CONTAINER_SCOPE"

  log "Managed identity is ready for Blob read access to ${BLOB_CONTAINER_NAME}"
  printf '%s\n' "$IDENTITY_RESOURCE_ID"
}

main "$@"
