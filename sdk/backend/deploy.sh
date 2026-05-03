#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# Deploy backend Azure Function App
#
# Prerequisites:
#   - Azure CLI (`az`) installed and logged in
#   - Azure Functions Core Tools 4.x (`func`)
#   - A .env file in this directory with required settings
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# ── TODO: Replace with your project-specific names ───────────────────────────
RESOURCE_GROUP="my-rag-project"
LOCATION="swedencentral"
STORAGE_ACCOUNT="myragfuncstorage"        # Must be globally unique
FUNCTION_APP_NAME="myrag-backend-func"    # Must be globally unique
APP_INSIGHTS_NAME="myrag-backend-insights"
PYTHON_VERSION="3.11"

# ── Load .env ────────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  echo "Loading environment variables from $ENV_FILE"
  set -a; source "$ENV_FILE"; set +a
else
  echo "⚠️  No $ENV_FILE found. Environment variables will not be synced."
fi

# ── Verify Azure login ──────────────────────────────────────────────────────
echo "Checking Azure login status..."
az account show > /dev/null 2>&1 || { echo "Not logged in. Run 'az login' first."; exit 1; }
echo "Using subscription: $(az account show --query name -o tsv)"
echo "────────────────────────────────────────────────"

# ── Resource Group ───────────────────────────────────────────────────────────
if az group show --name "$RESOURCE_GROUP" &>/dev/null; then
  echo "Resource Group '$RESOURCE_GROUP' exists."
else
  echo "Creating Resource Group '$RESOURCE_GROUP'..."
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
fi

# ── Storage Account ─────────────────────────────────────────────────────────
if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "Storage Account '$STORAGE_ACCOUNT' exists."
else
  echo "Creating Storage Account '$STORAGE_ACCOUNT'..."
  az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku "Standard_LRS"
fi

# ── Application Insights ────────────────────────────────────────────────────
if az monitor app-insights component show --app "$APP_INSIGHTS_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "App Insights '$APP_INSIGHTS_NAME' exists."
else
  echo "Creating App Insights '$APP_INSIGHTS_NAME'..."
  az monitor app-insights component create \
    --app "$APP_INSIGHTS_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --kind "web"
fi
APP_INSIGHTS_KEY=$(az monitor app-insights component show --app "$APP_INSIGHTS_NAME" --resource-group "$RESOURCE_GROUP" --query "instrumentationKey" -o tsv)

# ── Function App ─────────────────────────────────────────────────────────────
if az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "Function App '$FUNCTION_APP_NAME' exists."
else
  echo "Creating Function App '$FUNCTION_APP_NAME'..."
  az functionapp create \
    --name "$FUNCTION_APP_NAME" \
    --storage-account "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --consumption-plan-location "$LOCATION" \
    --functions-version 4 \
    --runtime python \
    --runtime-version "$PYTHON_VERSION" \
    --os-type "Linux" \
    --app-insights-key "$APP_INSIGHTS_KEY"
fi

# ── Publish ──────────────────────────────────────────────────────────────────
echo "Publishing function from $SCRIPT_DIR..."
(cd "$SCRIPT_DIR" && func azure functionapp publish "$FUNCTION_APP_NAME") || {
  echo "⚠️  Publish failed. See Azure Functions Core Tools docs for troubleshooting."
}

# ── Sync app settings from .env ──────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  echo "Syncing app settings from $ENV_FILE..."
  mapfile -t APP_SETTINGS < <(
    python3 - <<'PY' "$ENV_FILE"
import sys
from pathlib import Path
env_path = Path(sys.argv[1])
if not env_path.exists():
    sys.exit(0)
with env_path.open() as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        if key:
            print(f"{key}={value}")
PY
  )
  if [[ ${#APP_SETTINGS[@]} -gt 0 ]]; then
    az functionapp config appsettings set \
      --name "$FUNCTION_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --settings "${APP_SETTINGS[@]}"
    echo "✅ App settings updated."
  fi
fi

echo ""
echo "✅ Deployment complete."
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  App Insights:    $APP_INSIGHTS_NAME"
echo "  Function App:    $FUNCTION_APP_NAME"
