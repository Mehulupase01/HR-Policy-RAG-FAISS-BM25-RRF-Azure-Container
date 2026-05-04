# Project Plan

## 1. Vision & Scope

| Field | Value |
|-------|-------|
| **Project name** | Refreshworks AI HR Policy RAG |
| **Owner** | Mehul |
| **Primary goal** | Build a containerized RAG API that answers employee HR policy questions with grounded citations. |
| **Deployment target** | Azure Container Apps |
| **API surface** | `POST /query` returning `{ "answer": "...", "citations": [...] }` |

### Problem Statement

Employees need reliable answers over 32 HR policy documents that come from two different handbook sources. The system must retrieve relevant policy passages, answer with Azure OpenAI `gpt-4o`, cite the source chunks it used, avoid hallucinating on out-of-corpus questions, and surface source disagreement when policies differ between the OpenGov and Made Tech handbooks.

### Success Criteria

- [x] `POST /query` runs locally and in Azure Container Apps.
- [ ] Answers cite the retrieved policy chunks used to support the response.
- [ ] Retrieval uses hybrid dense + lexical search: FAISS plus BM25 fused with Reciprocal Rank Fusion, `k=60`.
- [ ] Ingestion handles markdown and PDF corpus files while skipping `opengov-handbook-consolidated.pdf`.
- [ ] Source identity comes from the hardcoded corpus mapping, not filename inference.
- [ ] Out-of-corpus questions return a grounded "not enough information" answer rather than hallucinated policy.
- [ ] Disagreement between OpenGov and Made Tech policies is called out instead of merged.
- [ ] Evaluation results, deployment notes, `DECISIONS.md`, `PROMPTS.md`, and raw chat transcripts are ready for submission.

---

## 2. Architecture Overview

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

### Components

| Component | Tech | Purpose |
|-----------|------|---------|
| `app/` | FastAPI, Pydantic, Uvicorn | Container API wrapper exposing `POST /query`. |
| `sdk/backend/agent/` | Existing SDK RAG abstractions | Keep `Retriever`, `RetrievalResult`, `AgentResult`, and `generate_reply`. |
| Hybrid retriever | FAISS, BM25, RRF | Retrieve and fuse dense + lexical chunk rankings. |
| Ingestion pipeline | Python 3.11, `pypdf`, SDK chunker | Load corpus, extract text, chunk, embed, and build artifacts. |
| Artifact storage | Azure Blob Storage | Store FAISS `.index`, parquet metadata, and `bm25.pkl` artifacts. |
| LLM provider | Azure OpenAI | `gpt-4o` for answers, `text-embedding-3-large` for embeddings. |
| Container runtime | Azure Container Apps | Required deployment target for the assignment. |

---

## 3. Backlog

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| P1 | Setup and Azure access | High | Complete |
| P2 | Repo scaffolding and SDK exploration | High | In progress |
| P3 | Deployable FastAPI skeleton | High | Planned |
| P4 | Corpus loading | High | Planned |
| P5 | Document chunking | High | Planned |
| P6 | Embeddings and FAISS artifact build | High | Planned |
| P7 | Hybrid retrieval with BM25 + FAISS + RRF | High | Planned |
| P8 | Generation, citations, and prompt | High | Planned |
| P9 | Out-of-corpus and disagreement handling | High | Planned |
| P10 | Evaluation harness | High | Planned |
| P11 | Real Azure deployment with secrets | High | Planned |
| P12 | Observability, polish, and walkthrough prep | Medium | Planned |

---

## 4. Phase Plan

### Phase 1: Setup And Azure Access

- [x] Azure sandbox details available in `AZURE_ACCESS.md`.
- [x] Azure OpenAI deployments identified: `gpt-4o` and `text-embedding-3-large`.
- [x] Local `.env` is gitignored and must never be committed.

### Phase 2: Repo Scaffolding And SDK Exploration

- [x] Read SDK agent, ingestion, blob client, runtime, docs, and template files.
- [x] Identify stable SDK abstractions to keep: `Retriever`, `RetrievalResult`, `AgentResult`, `generate_reply`, `DocumentChunk`.
- [x] Identify runtime glue to replace: Azure Functions entrypoint, Functions deploy scripts, and Qdrant-specific retriever/config.
- [x] Fill `sdk/planning/erd-template.md` with the actual architecture.
- [ ] Finalize this `sdk/planning/plan.md`.
- [ ] Run existing SDK unit tests before closing the phase.

### Phase 3: Deployable Skeleton

- [x] Add FastAPI app structure under `app/`.
- [x] Add Pydantic request/response/error models for `POST /query`.
- [x] Add a stub implementation that returns a clearly marked non-RAG response.
- [x] Add Dockerfile and local run command.
- [x] Verify local container startup and `POST /query`.
- [x] Prepare Azure Container Apps stub deployment path.

### Phase 4: Loading The Corpus

- [x] Implement markdown and PDF text loading for files under `corpus/`.
- [x] Skip `corpus/opengov-handbook-consolidated.pdf`.
- [x] Encode the `CORPUS_SOURCES.md` file-to-source mapping explicitly.
- [x] Preserve source, file path, document format, and raw content on `RawDocument`.
- [x] Add tests using actual corpus files.

### Phase 5: Chunking The Documents

- [ ] Reuse or extend SDK `DocumentChunk` and `chunk_document`.
- [ ] Choose chunk size and overlap based on corpus shape and citation quality.
- [ ] Preserve `chunk_id`, `source`, `file_path`, `chunk_idx`, `text`, and metadata.
- [ ] Add tests over actual corpus text.

### Phase 6: Embeddings And FAISS Index

- [ ] Use Azure OpenAI `text-embedding-3-large` deployment.
- [ ] Generate 3072-dimensional embeddings for chunks.
- [ ] Build FAISS index, BM25 index, and parquet chunk metadata.
- [ ] Persist artifacts locally and upload to Azure Blob Storage.
- [ ] Validate FAISS row order against metadata `vector_row`.

### Phase 7: Retrieval

- [ ] Implement FAISS dense search.
- [ ] Implement BM25 lexical search.
- [ ] Fuse dense and lexical rankings with RRF, `k=60`.
- [ ] Implement the SDK `Retriever` protocol.
- [ ] Add retrieval tests using real artifacts when available.

### Phase 8: Generation, Citations, And Prompt

- [ ] Use Azure OpenAI `gpt-4o` deployment for final answers.
- [ ] Build a policy-QA prompt that requires grounded answers and citations.
- [ ] Return citation objects with source, file path, chunk id, chunk index, text, and score.
- [ ] Avoid adding unsupported facts not present in retrieved context.

### Phase 9: Out-Of-Corpus And Disagreement Handling

- [ ] Detect low-confidence or irrelevant retrieval contexts.
- [ ] Return a clear "not enough information" response for out-of-corpus questions.
- [ ] Surface disagreement when OpenGov and Made Tech sources provide different rules.
- [ ] Add targeted tests for out-of-corpus and conflicting-policy cases.

### Phase 10: Evaluation Harness

- [ ] Build a small evaluation set grounded in the actual corpus.
- [ ] Include answerability, citation relevance, faithfulness, out-of-corpus, and disagreement cases.
- [ ] Produce an eval results file for submission.
- [ ] Document known weak queries and likely next improvements.

### Phase 11: Real Deployment With Secrets

- [ ] Check current Microsoft documentation before Azure CLI or Azure SDK deployment work.
- [ ] Deploy the containerized FastAPI API to Azure Container Apps.
- [ ] Store Azure OpenAI key as a Container Apps secret.
- [ ] Use managed identity for Blob Storage where possible.
- [ ] Verify deployed `POST /query` against the real endpoint.

### Phase 12: Observability, Polish, And Walkthrough Prep

- [ ] Add useful structured logging without leaking secrets.
- [ ] Add health/readiness behavior appropriate for loaded retrieval artifacts.
- [ ] Update README, `DECISIONS.md`, `PROMPTS.md`, and raw chat transcript references.
- [ ] Prepare final verification notes and Loom walkthrough outline.

---

## 5. Deployment Checklist

- [x] Docker image builds locally.
- [x] Container runs locally and serves `POST /query`.
- [ ] Retrieval artifacts exist locally and in Azure Blob Storage.
- [x] Azure Container Apps environment and app are configured.
- [x] Azure OpenAI key is configured as a Container Apps secret.
- [ ] Blob access uses `DefaultAzureCredential`: local `az login` for development and managed identity in Azure.
- [ ] Deployed API returns `{ "answer": "...", "citations": [...] }`.
- [ ] README includes deployed endpoint URL and verification evidence.

---

## 6. Phase Closure Rules

- Run relevant tests before marking any phase complete.
- Update docs and handoff/progress notes when the phase changes architecture, commands, or behavior.
- Do not mark placeholder behavior as production behavior.
- Do not commit `.env`, keys, generated secret files, or raw unredacted transcripts.
- Before any Azure SDK or Azure CLI command, check the latest Microsoft docs and record the relevant URL in the work notes.
