# Azure Deployment Tiers

This document defines the standard Azure resource tiers for RAG projects. Choose a tier based on expected usage, budget, and performance requirements.

---

## Tier Overview

| Tier | Target | Monthly Est. (EUR) | Use Case |
|------|--------|--------------------|----------|
| **Development** | Individual dev / PoC | €50 – €150 | Local-first with minimal cloud resources |
| **Staging** | Team testing / QA | ≤ €150 | Shared environment, mirrors production stack |
| **Production** | End users | ≤ €250 | Cost-conscious production with monitoring |

---

## Tier 1 — Development

Minimal cloud footprint. Most services run locally; only essential Azure resources are provisioned.

| Resource | SKU / Config | Notes |
|----------|-------------|-------|
| **Resource Group** | 1 per developer or shared | `{project}-dev` |
| **Azure Functions** | Consumption plan (Y1) | Pay-per-execution, free grant of 1M requests/month |
| **Storage Account** | Standard LRS | Single blob container for documents |
| **Azure OpenAI** | S0 (pay-as-you-go) | `text-embedding-ada-002` + `gpt-4o-mini` |
| **Qdrant** | Local Docker (`qdrant/run.sh`) | No cloud cost |
| **Database** | Local PocketBase / SQLite | No cloud cost |
| **App Insights** | Free tier (5 GB/month) | Basic telemetry |

### Environment variables

```bash
# .env (local development)
CONNECTION_STRING="UseDevelopmentStorage=true"   # Azurite
QDRANT_URL="http://localhost:6333"
AZURE_OPENAI_ENDPOINT="https://{resource}.openai.azure.com/"
AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o"
```

---

## Tier 2 — Staging (≤ €150/month target)

Shared cloud environment for integration testing and stakeholder demos. Uses the same stack as production at smaller scale.

| Resource | SKU / Config | Est. €/month | Notes |
|----------|-------------|-------------|-------|
| **Resource Group** | `{project}-staging` | — | Separate from dev & prod |
| **Azure Functions** | Consumption plan (Y1) | ~€0 – €10 | Scale-to-zero; free grant covers light usage |
| **Storage Account** | Standard LRS | ~€2 | Single container |
| **Azure OpenAI** | S0 (pay-as-you-go) | ~€20 – €50 | Same models as production for parity; lower traffic |
| **Qdrant** | Azure Container Instance (1 vCPU, 1.5 GB) | ~€30 – €40 | Persistent volume; stop outside business hours to save |
| **Database** | Azure App Service (B1) + PocketBase | ~€13 | Or PostgreSQL Flexible Burstable B1ms (~€15 – €25) |
| **App Insights** | Free tier (5 GB/month) | €0 | |
| **Azure Key Vault** | Standard | ~€1 | Centralise secrets |
| | | **~€65 – €115** | **Buffer to stay under €150** |

### Deployment

```bash
# From backend/
./deploy.sh   # Provisions RG, Storage, Insights, Function App
```

---

## Tier 3 — Production (≤ €250/month target)

Cost-conscious production deployment. Keep total Azure spend **under €250/month** by using Consumption plans and right-sized resources.

| Resource | SKU / Config | Est. €/month | Notes |
|----------|-------------|-------------|-------|
| **Resource Group** | `{project}-prod` | — | Locked with Azure Policy |
| **Azure Functions** | Consumption plan (Y1) | ~€0 – €20 | Free grant covers most workloads; upgrade to EP1 only if cold starts are unacceptable |
| **Storage Account** | Standard LRS | ~€5 | Upgrade to ZRS only if durability requirements demand it |
| **Azure OpenAI** | S0 (pay-as-you-go) | ~€50 – €100 | `text-embedding-ada-002` + `gpt-4o`; monitor token usage closely |
| **Qdrant** | ACI (1 vCPU, 1.5 GB) | ~€30 – €40 | Persistent volume for storage; sufficient for ≤500K vectors |
| **Database** | Azure Database for PostgreSQL Flexible (Burstable B1ms) | ~€15 – €25 | 1 vCore, 2 GB RAM, 32 GB storage; automated backups included |
| **App Insights** | Free tier (5 GB/month) | €0 | Upgrade to pay-per-GB only if you exceed 5 GB |
| **Azure Key Vault** | Standard | ~€1 | All secrets via Key Vault references |
| **Static Web Apps** | Free or Standard | €0 – €9 | Frontend hosting |
| **Managed Identity** | System-assigned | €0 | No API keys in app settings where possible |
| | | **~€100 – €200** | **Buffer to stay under €250** |

### Security checklist

- [ ] All secrets in Key Vault (no plain-text app settings)
- [ ] Managed Identity enabled on Function App
- [ ] VNET integration for Function App ↔ Qdrant / DB
- [ ] CORS restricted to frontend domain only
- [ ] Branch protection on `main` (require PR + 1 approval)
- [ ] IP restrictions on database and storage

---

## Resource Naming Convention

```
{project}-{environment}-{resource}
```

| Example | Description |
|---------|-------------|
| `myrag-dev-func` | Development Function App |
| `myrag-staging-storage` | Staging Storage Account |
| `myrag-prod-insights` | Production App Insights |

---

## Cost Optimisation Tips

1. **Use Consumption plan** for dev/staging — you only pay for actual invocations.
2. **Start with `gpt-4o` or equivalent** for development; switch to higher in final testing/production if quality demands it.
3. **Right-size Qdrant** — 1 GB RAM handles ~500K vectors with 1536 dimensions.
4. **Enable auto-shutdown** on dev/staging ACI resources outside business hours.
5. **Monitor with budgets** — set Azure Cost Management alerts at €200 (80%) and €250 (100%).

---

## Scaling Path

```
Development          Staging              Production
─────────────────    ─────────────────    ─────────────────
Consumption (Y1)  →  Consumption (Y1)  →  Consumption (Y1) *
Local Qdrant      →  ACI (1 vCPU)     →  ACI (1 vCPU, 1.5 GB)
Local PocketBase  →  App Service (B1)  →  PostgreSQL Flexible (Burstable B1ms)
Azurite           →  Standard LRS      →  Standard ZRS
Free Insights     →  Free Insights     →  Free Insights

* Upgrade to Premium (EP1) only if cold starts become a problem.
```
