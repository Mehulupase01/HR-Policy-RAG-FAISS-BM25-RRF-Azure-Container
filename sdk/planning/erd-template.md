# Architecture & Data Model

This document describes the actual architecture for the Refreshworks AI HR policy RAG assignment. It replaces the SDK template defaults where they do not match this project: no Azure Functions runtime, no Qdrant service, no database, and no frontend/admin application in scope.

## 1. System Architecture

### Request Path

| Step | Component | What happens |
|------|-----------|--------------|
| 1 | Client or evaluator | Sends `POST /query` with a `question`. |
| 2 | FastAPI app | Validates the request and calls the query service. |
| 3 | Hybrid retriever | Embeds the question, searches FAISS and BM25, then fuses rankings with RRF. |
| 4 | SDK RAG core | Uses the SDK `generate_reply` flow with retrieved context. |
| 5 | Azure OpenAI `gpt-4o` | Generates a grounded answer from the selected policy passages. |
| 6 | FastAPI app | Returns `{ "answer": "...", "citations": [...] }`. |

### Runtime Architecture Diagram

```text
+---------------------+
| Client / evaluator  |
+----------+----------+
           |
           | POST /query {"question": "..."}
           v
+---------------------+        startup load        +--------------------------+
| FastAPI app         | <-------------------------- | Azure Blob Storage      |
| app/                |                             | .index + parquet + pkl  |
+----------+----------+                             +------------+-------------+
           |                                                     |
           v                                                     v
+---------------------+                             +--------------------------+
| Query service       |                             | In-memory artifacts     |
+----------+----------+                             | FAISS index + BM25 pkl  |
           |                                        +------------+-------------+
           v                                                     |
+---------------------+                                         |
| Hybrid retriever    | <---------------------------------------+
| SDK Retriever       |
+----+-----------+----+
     |           |
     v           v
+---------+   +---------+
| FAISS   |   | BM25    |
| dense   |   | lexical |
+----+----+   +----+----+
     |             |
     +------+------+
            v
+---------------------+
| RRF fusion, k=60    |
+----------+----------+
           |
           v
+---------------------+
| Grounded context    |
+----------+----------+
           |
           v
+---------------------+        +--------------------------+
| SDK generate_reply  | -----> | Azure OpenAI gpt-4o     |
+----------+----------+        +------------+-------------+
           |                                |
           +--------------------------------+
           |
           v
+-------------------------------+
| Response: answer + citations  |
+-------------------------------+
```

### Component Overview

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| API runtime | FastAPI, Uvicorn, Python 3.11 | Expose `POST /query`, validate request/response models with Pydantic, return JSON errors. |
| SDK RAG core | `sdk/backend/agent/rag_agent.py` | Keep the SDK orchestration and `Retriever` protocol instead of forking core abstractions. |
| Hybrid retriever | New FAISS + BM25 implementation | Implement the SDK `Retriever` protocol and return SDK `RetrievalResult` objects. |
| Dense retrieval | FAISS in memory | Search `text-embedding-3-large` vectors loaded from persisted `.index` artifacts. |
| Lexical retrieval | BM25 in memory | Load and search the persisted `bm25.pkl` artifact. |
| Fusion | Reciprocal Rank Fusion, `k=60` | Combine dense and lexical result rankings without requiring a separate reranking service. |
| Generator | Azure OpenAI `gpt-4o` | Produce grounded HR policy answers from retrieved context. |
| Embeddings | Azure OpenAI `text-embedding-3-large` | Embed corpus chunks and runtime questions with 3072-dimensional vectors. |
| Artifact storage | Azure Blob Storage | Persist generated retrieval artifacts: FAISS `.index`, chunk metadata parquet, and `bm25.pkl`. |
| Deployment target | Azure Container Apps | Run the FastAPI container required by the assignment. |

## 2. Data Flow

### 2a. Corpus Ingestion

```text
+----------------+      +----------------+      +----------------+
| Local corpus/  | ---> | Corpus loader  | ---> | SDK chunker    |
+----------------+      +-------+--------+      +-------+--------+
                              |                       |
                              | hardcoded source map  |
                              | skip duplicate PDF    |
                              v                       v
                      +----------------+      +----------------------+
                      | Extracted text | <--- | DocumentChunk records |
                      +-------+--------+      +----------------------+
                              |
                              v
                      +-----------------------------+
                      | Azure OpenAI embeddings     |
                      | text-embedding-3-large      |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      | FAISS/BM25 index builder    |
                      +--------------+--------------+
                                     |
                     +---------------+----------------+
                     |                                |
                     v                                v
          +--------------------+           +---------------------+
          | FAISS .index file  |           | Chunk metadata      |
          |                    |           | parquet + bm25.pkl  |
          +---------+----------+           +----------+----------+
                    |                                 |
                    +---------------+-----------------+
                                    v
                         +----------------------+
                         | Azure Blob Storage   |
                         +----------------------+
```

| Step | From | To | Action |
|------|------|----|--------|
| 1 | Local `corpus/` | Corpus loader | Read 24 markdown files and 8 PDF files. |
| 2 | Corpus loader | Corpus loader | Skip `opengov-handbook-consolidated.pdf` because it duplicates the OpenGov split files. |
| 3 | Corpus loader | Corpus loader | Apply the hardcoded file-to-source mapping from `CORPUS_SOURCES.md`. |
| 4 | Corpus loader | SDK chunker | Send extracted text and document metadata. |
| 5 | SDK chunker | Corpus loader | Return `DocumentChunk` records. |
| 6 | Corpus loader | Azure OpenAI embeddings | Embed each chunk with `text-embedding-3-large`. |
| 7 | Azure OpenAI embeddings | Corpus loader | Return 3072-dimensional vectors. |
| 8 | Corpus loader | FAISS/BM25 index builder | Build FAISS index, BM25 index, and metadata table. |
| 9 | FAISS/BM25 index builder | Corpus loader | Return `.index`, parquet, and `bm25.pkl` artifacts. |
| 10 | Corpus loader | Azure Blob Storage | Upload FAISS `.index`. |
| 11 | Corpus loader | Azure Blob Storage | Upload chunk metadata parquet. |
| 12 | Corpus loader | Azure Blob Storage | Upload persisted `bm25.pkl`. |

### 2b. Runtime Query

```text
+---------+      +----------------+      +----------------+
| Client  | ---> | FastAPI /query | ---> | Query service  |
+---------+      +----------------+      +-------+--------+
                                                |
                                                v
                                      +------------------+
                                      | Hybrid retriever |
                                      +---+----------+---+
                                          |          |
                                          v          v
                                   +----------+  +---------+
                                   | FAISS    |  | BM25    |
                                   | dense    |  | lexical |
                                   +----+-----+  +----+----+
                                        |             |
                                        +------+------+ 
                                               |
                                               v
                                      +------------------+
                                      | RRF fusion k=60  |
                                      +--------+---------+
                                               |
                                               v
                                      +------------------+
                                      | Retrieved chunks |
                                      +--------+---------+
                                               |
                                               v
                                      +------------------+
                                      | SDK RAG core     |
                                      | generate_reply   |
                                      +--------+---------+
                                               |
                                               v
                                      +------------------+
                                      | Azure OpenAI     |
                                      | gpt-4o           |
                                      +--------+---------+
                                               |
                                               v
                                      +------------------+
                                      | answer+citation  |
                                      +------------------+
```

| Step | From | To | Action |
|------|------|----|--------|
| 1 | Client | FastAPI `/query` | Send `POST /query {"question": "..."}`. |
| 2 | FastAPI `/query` | FastAPI `/query` | Validate that the question is present and non-empty. |
| 3 | FastAPI `/query` | Query service | Run the RAG query. |
| 4 | Query service | Hybrid retriever | Call `retrieve(question, chat_history=[])`. |
| 5 | Hybrid retriever | Azure OpenAI embeddings | Embed the runtime question. |
| 6 | Azure OpenAI embeddings | Hybrid retriever | Return the query vector. |
| 7 | Hybrid retriever | FAISS index | Run dense similarity search. |
| 8 | FAISS index | Hybrid retriever | Return ranked dense chunks. |
| 9 | Hybrid retriever | BM25 index | Run lexical keyword search. |
| 10 | BM25 index | Hybrid retriever | Return ranked lexical chunks. |
| 11 | Hybrid retriever | Hybrid retriever | Fuse rankings with RRF, `k=60`. |
| 12 | Hybrid retriever | Query service | Return SDK `RetrievalResult` records with source metadata. |
| 13 | Query service | SDK `generate_reply` | Pass question, retrieved context, and injected LLM callable. |
| 14 | SDK `generate_reply` | Azure OpenAI `gpt-4o` | Send grounded prompt and selected policy passages. |
| 15 | Azure OpenAI `gpt-4o` | SDK `generate_reply` | Return answer text. |
| 16 | SDK `generate_reply` | Query service | Return `AgentResult`. |
| 17 | Query service | FastAPI `/query` | Return answer and citations. |
| 18 | FastAPI `/query` | Client | Return `200 OK`. |

## 3. API Contract

Only one public assignment endpoint is required.

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/query` | None for assignment scope | JSON body with `question` | JSON body with `answer` and `citations` |

### Request Body

```json
{
  "question": "What is the sick leave policy?"
}
```

### Success Response

```json
{
  "answer": "The answer is grounded in the retrieved HR policy passages. If relevant policies disagree across sources, the answer calls that out instead of merging them.",
  "citations": [
    {
      "source": "OpenGov Foundation HR Manual",
      "file_path": "corpus/sick-leave-policy.md",
      "chunk_id": "sha256-or-stable-id",
      "chunk_idx": 3,
      "text": "The cited policy passage used to support the answer.",
      "score": 0.82
    }
  ]
}
```

### Error Responses

All errors use a compact problem-details style body:

```json
{
  "title": "Bad Request",
  "detail": "Field 'question' is required.",
  "status": 400
}
```

| Status | When |
|--------|------|
| `400` | Request body is invalid JSON, `question` is missing, or `question` is blank. |
| `422` | Pydantic request validation fails for a structurally invalid payload. |
| `500` | Unexpected server error. The response must not expose secrets or raw provider details. |
| `503` | Retrieval artifacts, Azure OpenAI, or Blob-loaded startup dependencies are unavailable. |

Out-of-corpus questions should return `200` with an answer that says the available documents do not contain enough information, plus an empty or low-confidence citation list. They are not API errors.

## 4. Retrieval Artifact Schema

The vector store is not a running database service. It is a set of artifacts generated by ingestion, persisted to Azure Blob Storage, downloaded on container startup, and loaded into memory.

### FAISS Index File

| Artifact | Format | Contents |
|----------|--------|----------|
| `hr-policy.faiss.index` | FAISS binary index | 3072-dimensional dense vectors for all retained chunks. |
| `bm25.pkl` | Python pickle | Persisted BM25 lexical index built at ingestion time with the same tokenization used at query time. |

The FAISS row order must match `vector_row` in the chunk metadata parquet so search results can be joined back to citations.
The BM25 artifact is persisted rather than rebuilt at startup to avoid slower cold starts and tokenization drift.

### Chunk Metadata Parquet

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | string | Stable unique chunk identifier, preferably deterministic from file path, chunk index, and content hash. |
| `source` | string | Canonical source discriminator from the hardcoded corpus mapping. Allowed values: `opengov`, `madetech`. |
| `file_path` | string | Corpus-relative path, such as `corpus/sick-leave-policy.md`. |
| `file_name` | string | Original filename for display and debugging. |
| `chunk_idx` | int | Zero-based chunk position within the source file. |
| `text` | string | Chunk text used for retrieval and citation. |
| `embedding` | list[float] or fixed-size vector column | 3072-dimensional embedding from `text-embedding-3-large`; can be omitted from API startup loading if FAISS `.index` is authoritative. |
| `vector_row` | int | Row position in the FAISS index. |
| `content_hash` | string | Hash of chunk text for reproducibility and artifact validation. |
| `document_type` | string | `markdown` or `pdf`. |
| `title` | string | Human-readable policy title when available. |
| `license` | string | Source license/provenance note from `CORPUS_SOURCES.md` where applicable. |
| `created_at` | string | Artifact creation timestamp in ISO 8601 format. |

### BM25 Support Artifact

Persist `bm25.pkl` to Blob alongside `hr-policy.faiss.index` and the chunk metadata parquet. Load it on container startup. Do not rebuild BM25 from parquet text at startup, because that is slower and can introduce tokenization drift between index time and query time.

## 5. Environment Variables

### Required at Runtime

| Variable | Purpose |
|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint, e.g. `https://oai-rag-interview-mehul.openai.azure.com/`. |
| `AZURE_OPENAI_KEY` | Azure OpenAI key. Local only via `.env`; deployed as a Container Apps secret. |
| `AZURE_OPENAI_API_VERSION` | API version used for chat and embeddings calls. |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat deployment name: `gpt-4o`. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding deployment name: `text-embedding-3-large`. |
| `BLOB_ACCOUNT_URL` | Blob account URL used with managed identity in Azure Container Apps. |
| `BLOB_INDEX_CONTAINER` | Container holding FAISS/parquet/BM25 retrieval artifacts, default `rag-index`. |
| `INDEX_BLOB_PREFIX` | Blob prefix containing `embeddings.parquet`, `faiss.index`, and `bm25.pkl`, default `latest`. |
| `INDEX_LOCAL_DIR` | Local directory to load indexes from or download indexes into, default `data/index` locally and `/tmp/index` in Container Apps. |

### Local Development Convenience

| Variable | Purpose |
|----------|---------|
| `LOCAL_ARTIFACT_DIR` | Optional local path for generated or downloaded FAISS/parquet artifacts. |
| `LOG_LEVEL` | Logging verbosity, default `INFO`. |
| `RETRIEVAL_TOP_K_DENSE` | Dense retrieval candidate count before fusion. |
| `RETRIEVAL_TOP_K_LEXICAL` | BM25 retrieval candidate count before fusion. |
| `RETRIEVAL_TOP_K_FINAL` | Final fused chunks sent to the answer generator. |
| `RRF_K` | Reciprocal Rank Fusion constant, default `60`. |

## 6. Implementation Notes

- Keep SDK core abstractions: `ChatMessage`, `RetrievalResult`, `AgentResult`, `Retriever`, `generate_reply`, `DocumentChunk`, and the blob validation helpers.
- Replace Azure Functions runtime glue with FastAPI because the assignment requires a containerized API on Azure Container Apps.
- Replace Qdrant-specific retriever/config/scripts with a FAISS+BM25 retriever that implements the existing SDK `Retriever` protocol.
- Do not ingest `corpus/opengov-handbook-consolidated.pdf`; it duplicates the OpenGov split files.
- Do not infer handbook/source identity from filenames. Use the mapping documented in `CORPUS_SOURCES.md`.
- The system must surface source disagreement when the corpus contains conflicting policies rather than flattening both handbooks into one fictional employer policy.
