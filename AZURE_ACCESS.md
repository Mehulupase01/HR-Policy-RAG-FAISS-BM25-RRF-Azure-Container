# Azure Access

Connection details for the RAG interview sandbox.

## Connection details

| Setting | Value |
|---|---|
| Subscription | `7550559f-20b4-4528-ab93-4add5a0d6c7d` (Refreshworks) |
| Tenant | `07f7e037-e81e-4516-ba96-62f787723bb0` |
| Resource group | `rg-rag-interview-mehul` |
| Region | Sweden Central (`swedencentral`) |
| Role | Contributor, scoped to the resource group above |
| OpenAI account name | `oai-rag-interview-mehul` |
| OpenAI endpoint | `https://oai-rag-interview-mehul.openai.azure.com/` |
| Model deployments | `gpt-4o`, `text-embedding-3-large` |

## Logging in

After accepting the Microsoft B2B guest invitation that arrived in your inbox, sign in with:

```bash
az login --tenant 07f7e037-e81e-4516-ba96-62f787723bb0
```

Set the active subscription if you have access to multiple:

```bash
az account set --subscription 7550559f-20b4-4528-ab93-4add5a0d6c7d
```

## Getting the API keys

The OpenAI API keys are not in this file — fetch them yourself once you're signed in:

- **Via Azure AI Foundry:** sign in at <https://ai.azure.com>, select the `oai-rag-interview-mehul` resource, the keys are visible on its overview page.
- **Via the Azure portal:** open the `rg-rag-interview-mehul` resource group → `oai-rag-interview-mehul` → "Keys and Endpoint." Both `KEY 1` and `KEY 2` work.
- **Via the CLI** (once signed in):
  ```bash
  az cognitiveservices account keys list \
    --name oai-rag-interview-mehul \
    --resource-group rg-rag-interview-mehul \
    --query key1 --output tsv
  ```

## Using the keys

- Don't commit keys to the repo.
- Don't bake them into the container image.
- Use a `.env` file for local dev (do not commit it).
- At deploy time, pass the key in as an env var or Container Apps secret.

## Notes

- Both model deployments are Standard SKU at 30,000 TPM.
- `gpt-4o` is deployed at version `2024-11-20`; `text-embedding-3-large` at version `1`.
- The OpenAI account has a `CanNotDelete` resource lock. Contributor lets you do everything in the resource group except delete the OpenAI resource itself — that's intentional, so you can iterate freely without worrying about wiping the deployment.
