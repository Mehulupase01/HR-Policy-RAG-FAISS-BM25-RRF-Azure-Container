# Project Plan

> **Instructions:** Copy this file into your new project and customise each section.
> Delete this instruction block when done.

## 1. Vision & Scope

| Field | Value |
|-------|-------|
| **Project name** | _Your Project Name_ |
| **Owner** | _Team / person_ |
| **Start date** | _YYYY-MM-DD_ |
| **Target launch** | _YYYY-MM-DD_ |

### Problem statement

_Describe the business problem this RAG system solves._

### Success criteria

- [ ] _Measurable outcome 1_
- [ ] _Measurable outcome 2_

---

## 2. Architecture Overview

```
┌──────────┐     ┌──────────────┐     ┌────────────┐
│ Frontend │────▶│  Backend API │────▶│  Qdrant    │
│ (Next.js)│     │ (Azure Func) │     │ (Vector DB)│
└──────────┘     └──────┬───────┘     └────────────┘
                        │
                 ┌──────▼───────┐
                 │ Azure OpenAI │
                 │ (Embeddings  │
                 │  + Chat)     │
                 └──────────────┘
```

### Components

| Component | Tech | Purpose |
|-----------|------|---------|
| `backend/` | Python 3.11, Azure Functions | RAG pipeline, API endpoints |
| `frontend/` | Next.js | Chat UI, file management |
| `database/` | PocketBase / PostgreSQL | Auth, metadata, chat history |
| `qdrant/` | Qdrant | Vector storage & similarity search |

---

## 3. Backlog

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| W1 | Project scaffolding | High | ⬜ |
| W2 | Blob storage file management | High | ⬜ |
| W3 | Document ingestion pipeline | High | ⬜ |
| W4 | RAG agent (retrieve + generate) | High | ⬜ |
| W5 | Chat UI | Medium | ⬜ |
| W6 | Auth & user management | Medium | ⬜ |
| W7 | Admin dashboard | Low | ⬜ |

---

## 4. Sprint Plan

### Sprint 1 — Foundation (_dates_)

- [ ] Set up Azure resources (Storage, Function App, OpenAI)
- [ ] Implement blob upload/download/delete
- [ ] Configure Qdrant locally
- [ ] Write unit tests for validation

### Sprint 2 — Ingestion (_dates_)

- [ ] Build document parser (PDF, DOCX, XLSX, TXT, CSV)
- [ ] Implement chunking strategy
- [ ] Embed & upsert to Qdrant
- [ ] Integration tests

### Sprint 3 — RAG Agent (_dates_)

- [ ] Wire retriever to chat endpoint
- [ ] Implement system prompt & context injection
- [ ] Add chat history support
- [ ] End-to-end testing

---

## 5. Deployment Checklist

- [ ] Azure resources provisioned (see `docs/azure-deployment-tiers.md`)
- [ ] Environment variables set in Function App configuration
- [ ] Qdrant deployed (Azure Container Instance or Qdrant Cloud)
- [ ] Frontend deployed (Azure Static Web Apps or Vercel)
- [ ] Branch protection rules enabled on `main`
- [ ] CI/CD pipeline configured
