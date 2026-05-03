# Architecture & Data Model Template

> **Instructions:** Fill out this document *before* starting the build phase.
> It covers the full tech stack — not just the database. Modify per project.
> Delete this instruction block when done.

---

## 1. System Architecture

```
┌─────────────┐       ┌──────────────────┐       ┌──────────────┐
│   Frontend   │──────▶│   Backend API    │──────▶│   Qdrant     │
│   (Next.js)  │ HTTPS │ (Azure Functions)│       │ (Vector DB)  │
└─────────────┘       └────────┬─────────┘       └──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
     │ Azure OpenAI │  │ Azure Blob  │  │   Database   │
     │ (Embeddings  │  │  Storage    │  │ (PocketBase/ │
     │  + Chat)     │  │ (Documents) │  │  PostgreSQL) │
     └──────────────┘  └─────────────┘  └──────────────┘
```

### Component Overview

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| **Frontend** | Next.js, React, TailwindCSS | Chat UI, file manager, admin dashboard |
| **Backend API** | Python 3.11, Azure Functions v4 | HTTP endpoints, auth middleware, orchestration |
| **RAG Agent** | Python (`backend/agent/`) | Retrieve context → generate grounded answer |
| **Ingestion Pipeline** | Python (`backend/ingestion/`) | Parse documents → chunk → embed → upsert |
| **Blob Storage** | Azure Blob Storage | Raw document storage (PDF, DOCX, XLSX, TXT, CSV) |
| **Vector DB** | Qdrant | Similarity search over document embeddings |
| **Embeddings** | Azure OpenAI (`text-embedding-ada-002` / `3-large`) | Convert text to vectors |
| **LLM** | Azure OpenAI (`gpt-4o`) | Generate answers from retrieved context |
| **Database** | PocketBase / PostgreSQL | Users, chats, messages, document metadata |
| **Auth** | PocketBase auth or custom JWT | Token-based authentication |
| **Monitoring** | Azure Application Insights | Telemetry, logging, alerts |
| **Secrets** | Azure Key Vault | API keys, connection strings |

---

## 2. Data Flow

### 2a. Document Ingestion

```
User uploads file
       │
       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│  Validation  │───▶│  Blob Store  │───▶│   Chunker    │───▶│ Embedder │
│ (type, size) │    │  (raw file)  │    │ (split text) │    │ (OpenAI) │
└──────────────┘    └──────────────┘    └──────────────┘    └─────┬────┘
                                                                  │
                                                                  ▼
                                                           ┌──────────┐
                                                           │  Qdrant  │
                                                           │ (upsert) │
                                                           └──────────┘
```

| Step | Input | Output | Module |
|------|-------|--------|--------|
| Validate | File bytes + name | Pass / reject (413, 415) | `blob_client/validation.py` |
| Store | Validated file | Blob in Azure Storage | `blob_client/client.py` |
| Parse | Blob bytes | Plain text | `ingestion/parsers.py` |
| Chunk | Plain text | List of `DocumentChunk` | `ingestion/chunkers.py` |
| Embed | Chunk text | Vector (float[]) | `agent/embeddings.py` |
| Upsert | Vector + payload | Qdrant point | `ingestion/ingest.py` |

### 2b. RAG Query

```
User asks question
       │
       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│  Embed query │───▶│  Qdrant      │───▶│  Build       │───▶│  LLM     │
│  (OpenAI)    │    │  (search)    │    │  context     │    │ (OpenAI) │
└──────────────┘    └──────────────┘    └──────────────┘    └─────┬────┘
                                                                  │
                                                                  ▼
                                                           ┌──────────┐
                                                           │  Reply   │
                                                           │ + sources│
                                                           └──────────┘
```

| Step | Input | Output | Module |
|------|-------|--------|--------|
| Embed query | Question text | Query vector | `agent/embeddings.py` |
| Retrieve | Query vector | Top-K scored chunks | `agent/qdrant_retriever.py` |
| Filter | Scored chunks | Chunks above threshold | `agent/rag_agent.py` |
| Generate | Question + context + history | Answer text | `agent/generator.py` |
| Respond | Answer + source list | JSON response | `function_app.py` |

---

## 3. API Contracts

| Method | Endpoint | Auth | Request Body | Response |
|--------|----------|------|-------------|----------|
| `GET` | `/api/health` | None | — | `{ "status": "ok" }` |
| `POST` | `/api/chat` | Bearer token | `{ "chat_id", "owner_id", "question" }` | `{ "reply", "sources": [] }` |
| `GET` | `/api/files` | Bearer token | — | `{ "files": [...] }` |
| `POST` | `/api/files` | Bearer token | `{ "blobName", "content" }` | `201` or error |
| `DELETE` | `/api/files/{name}` | Bearer token | — | `200` or error |

### Error format (all endpoints)

```json
{
  "title": "Short summary",
  "detail": "Human-readable explanation",
  "status": 413
}
```

---

## 4. Vector Store Schema (Qdrant)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID / hash | Unique chunk identifier |
| `vector` | float[] | Embedding (1536-dim for ada-002, 3072 for 3-large) |
| **Payload:** | | |
| `text` | string | Chunk content |
| `source` | string | Original blob name |
| `blob_name` | string | Same as source (compat) |
| `chunk_index` | int | Position within the document |

**Collection settings:**
- Distance metric: **Cosine**
- Default collection name: `documents` (override via `QDRANT_COLLECTION_NAME`)

---

## 5. Database ERD

```
┌─────────────────────┐       ┌─────────────────────┐
│       users          │       │      documents       │
├─────────────────────┤       ├─────────────────────┤
│ id          PK      │       │ id          PK      │
│ email       UNIQUE  │       │ blob_name   UNIQUE  │
│ name                │       │ content_type        │
│ role        ENUM    │       │ size_bytes          │
│ created_at          │       │ uploaded_by  FK→users│
│ updated_at          │       │ created_at          │
└────────┬────────────┘       │ updated_at          │
         │                    └────────┬────────────┘
         │ 1:N                         │ 1:N
         ▼                             ▼
┌─────────────────────┐       ┌─────────────────────┐
│       chats          │       │      chunks          │
├─────────────────────┤       ├─────────────────────┤
│ id          PK      │       │ id          PK      │
│ owner_id    FK→users│       │ document_id FK→docs │
│ title               │       │ chunk_index         │
│ created_at          │       │ content     TEXT     │
│ updated_at          │       │ embedding_id        │
└────────┬────────────┘       │ created_at          │
         │ 1:N                └─────────────────────┘
         ▼
┌─────────────────────┐
│     messages         │
├─────────────────────┤
│ id          PK      │
│ chat_id     FK→chats│
│ role        ENUM    │
│ content     TEXT     │
│ sources     JSON     │
│ created_at          │
└─────────────────────┘
```

### Relationships

| From | To | Type | Description |
|------|----|------|-------------|
| `users` | `chats` | 1:N | A user owns many chats |
| `chats` | `messages` | 1:N | A chat contains many messages |
| `users` | `documents` | 1:N | A user uploads many documents |
| `documents` | `chunks` | 1:N | A document is split into many chunks |

### Enums

| Enum | Values |
|------|--------|
| `user_role` | `admin`, `editor`, `viewer` |
| `message_role` | `user`, `assistant`, `system` |

### Notes

- `chunks.embedding_id` references the Qdrant point ID.
- Adapt this schema to your database engine (PocketBase, PostgreSQL, Cosmos DB, etc.).

---

## 6. Environment Variables

See `backend/.env.example` for the full list. Key groups:

| Group | Variables | Used by |
|-------|----------|---------|
| **Blob Storage** | `CONNECTION_STRING`, `BLOB_CONTAINER_NAME` | blob_client, ingestion |
| **Qdrant** | `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION_NAME` | retriever, ingestion |
| **Embeddings** | `EMBEDDINGS_MODEL_ENDPOINT`, `EMBEDDINGS_MODEL_NAME`, `EMBEDDINGS_MODEL_API_KEY` | embeddings, ingestion |
| **Chat LLM** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` | generator |
| **Database** | `DATABASE_URL` | function_app |

---

## 7. Checklist

- [ ] Architecture diagram reviewed with team
- [ ] ERD reviewed and approved before build
- [ ] API contracts agreed with frontend developer
- [ ] Qdrant collection schema confirmed (dimension, distance)
- [ ] Environment variables documented in `.env.example`
- [ ] Deployment tier selected (see `docs/azure-deployment-tiers.md`)
