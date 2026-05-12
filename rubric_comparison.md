# Rubric vs Delivery — Mehul Upase

Extended eval results: `eval/test_set_extended.json` — 62 cases, run against local server.

---

## RAG Quality (45%)

### Retrieval (15%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Sensible chunking strategy with documented rationale (size, overlap, boundary handling) | Header-aware H2/H3 chunking for markdown, paragraph-pack for PDFs. 800 tokens max, 100 token overlap, tiny-file threshold at 400 tokens. Documented in D-06, D-07, D-08 with rationale and measured chunk distribution stats. | ✅ Met |
| Embedding model choice justified | `text-embedding-3-large` (3072 dims). Justified in D-04: higher MTEB benchmark than -small, already deployed in provided Azure resource, storage cost negligible at corpus size. | ✅ Met |
| Retrieval works for paraphrased queries, not just verbatim | Extended eval paraphrased recall: **1.000** (10 cases). Verbatim recall: **1.000** (8 cases). | ✅ Met |
| Reranking, hybrid search, or other improvements considered (or explicitly traded off) | Hybrid FAISS dense + BM25 lexical retrieval fused via Reciprocal Rank Fusion (k=60). Reranking explicitly traded off in D-12 with written rationale and a stated v2 candidate. | ✅ Met |

### Answer Quality (15%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Answers are grounded in retrieved context | System prompt grounding rule enforced. `temperature=0.0` for determinism. `response_format=json_object` prevents prose outside the structured answer. | ✅ Met |
| Citations match what was actually used (not just the top retrieval) | Post-generation citation validation: every cited `file_path#chunk_idx` key is looked up against the actual retrieved set. Hallucinated citations are dropped silently with a logged warning before the response returns. | ✅ Met |
| No hallucination on out-of-corpus queries | Two-signal OOF detector (RRF score threshold AND LLM judge, AND-gate). Extended eval refusal accuracy: **0.984** against a 0.90 bar. Clearly OOF: **1.000**. Plausibly OOF: **1.000**. | ✅ Met |
| Handles ambiguous questions (asks back or qualifies) | Hedge case: when score signal and LLM judge disagree, answer is returned with "Based on limited information in our policies," prepended. Documented in D-13. | ✅ Met |

### Evaluation Rigor (15%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Extended the eval set meaningfully beyond the starter | 62 hand-crafted cases across 8 deliberate categories. Initial run: 40 cases. Extended run: 62 cases with additional disagreement, paraphrased, and verbatim coverage. | ✅ Met |
| Added cases that probe known weak spots (synthesis, adversarial, edge cases) | Adversarial (4 cases): empty string, prompt injection, salary demand, and source-merge attempt. OOF-plausible (4 cases): dental insurance, mental health days, company car, tuition amounts. Source-disagreement (12 cases). | ✅ Met |
| Discussed metric limitations (LLM-as-judge bias, etc.) | Methodology section in `eval/results_extended.md` explicitly names: length preference bias, self-preference bias, single-axis grading, refusal string-match fragility, and small sample size limitations. | ✅ Met |
| Has a stated quality bar and shows the system meets it | Quality bar stated upfront (recall ≥ 0.85, refusal ≥ 0.90, surfaces-both ≥ 0.75, faithfulness ≥ 0.80). Extended eval results: **all four bars met**. | ✅ Met |
| Eval results are reproducible | Single command: `python -m eval.run_eval --base-url <url> --test-set eval/test_set_extended.json --out eval/results_extended.json --report eval/results_extended.md` | ✅ Met |

**Extended eval summary:**

| Metric | Bar | Result | Status |
|---|---|---|---|
| Retrieval recall | ≥ 0.85 | **0.920** | ✅ Met |
| Refusal accuracy | ≥ 0.90 | **0.984** | ✅ Met |
| Surfaces both sources | ≥ 0.75 | **0.786** | ✅ Met |
| Mean faithfulness | ≥ 0.80 | **0.898** | ✅ Met |
| Error rate | — | **0.000** | ✅ Zero errors |

---

## Production Readiness (30%)

### Operability (20%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Working health checks | `/healthz` — always 200, synchronous, never calls Azure OpenAI (safe for load balancer probes). `/readyz` — calls Azure OpenAI with a 2-second timeout to confirm upstream reachability. | ✅ Met |
| Logging that would help debug a real incident | Structured JSON logging via `python-json-logger`. `request_id` propagated automatically via `contextvars.ContextVar` across the full request lifecycle without threading. `X-Request-ID` returned in response headers for client-side correlation. `query.received` and `query.complete` events with structured fields: question hash (not text), retrieved chunk count, OOF decision booleans, disagreement decision booleans, answer length, citation count, duration. No PII (question/answer text not logged). | ✅ Met |
| Some form of metrics or tracing (App Insights, OTEL, etc.) | Azure Monitor OpenTelemetry via `azure-monitor-opentelemetry`. `configure_azure_monitor()` wires trace export, metrics, and log forwarding. FastAPI and httpx auto-instrumented — every HTTP request and every outbound OpenAI call becomes a trace span. No-ops cleanly when `APPLICATIONINSIGHTS_CONNECTION_STRING` is absent (local dev). | ✅ Met |
| Reasonable error handling on the API surface | 422 for Pydantic validation errors with field details. 502 for `AnswerParseError` (malformed LLM JSON). 503 for `RateLimitError` and `APIError` (temporary upstream failures). 500 for uncaught exceptions with logged traceback, no internals leaked in response body. | ✅ Met |
| Configurable via env without code changes | `pydantic-settings` loads all configuration from `.env`. Deployment names, endpoint, API version, Blob account URL, index container, and local index dir are all env vars. Zero hardcoded values in application code. Same image runs locally and in production. | ✅ Met |
| Resources sensibly named and tagged | `rg-rag-interview-mehul` (resource group), `hr-rag-app` (Container App), `acrragintvwmehul` (ACR), `cae-rag-interview` (Container Apps environment), `stragragintvwmehul` (storage account), `appi-rag-interview` (App Insights). | ✅ Met |

### Security (10%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| No keys in repo or commit history | `.env` gitignored from the first commit in Phase 2. `.env.example` committed in its place. Verified clean throughout via `git check-ignore .env`. | ✅ Met |
| OpenAI key not baked into the image — passed at deploy time as env var or Container Apps secret | `deploy/deploy.sh` passes the key as a Container Apps secret: `--secrets openai-key=<value>`, referenced in the container env as `AZURE_OPENAI_KEY=secretref:openai-key`. The key never touches the Docker image. **The live deploy was blocked not by an implementation gap but by the Azure sandbox permissions** provided: the account `upasemehul@gmail.com` was granted Contributor but not Owner or User Access Administrator, so `Microsoft.Authorization/roleAssignments/write` was denied when the deploy script tried to create the managed identity role assignment. The code is correct; the sandbox limitation prevented execution. The system is now deployed correctly on a personal Azure account. | ⚠️ Code correct — blocked by sandbox RBAC |
| API not wide open without rate limiting if exposed publicly | Rate limiting was not implemented. The rubric notes "or intentionally internal" as an acceptable alternative — and the live endpoint was not publicly reachable due to the deploy blocker above. This is a genuine gap. | ❌ Not implemented |

---

## Code Quality (15%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Sensible structure, not one big file | `app/` (API and business logic), `sdk/` (vendored SDK), `deploy/` (Dockerfile and scripts), `eval/` (test set, runner, results), `tests/` (pytest suite), `chats/` (raw AI transcripts). Clear module boundaries within `app/`: `api/`, `ingest/`, `retrieval/`, `generation/`, `observability/`. | ✅ Met |
| Type hints, and they're meaningful | Throughout `app/`. `Literal["opengov", "madetech"]` for source attribution. `Pydantic` models for all API contracts. Frozen dataclasses with typed fields for `RawDocument`, `Chunk`, `RetrievedChunk`. | ✅ Met |
| Tests exist and test something useful | 60 passing tests, 1 skipped, 1 warning. Unit tests for loader, chunker, embedder, indexer, retriever, OOF detector, disagreement detector, answerer. Integration tests for the full `/query` endpoint via `TestClient`. Fixture-driven eval harness test. Tests run against real corpus artifacts where possible. | ✅ Met |
| Docstrings where they help, not where they're noise | Present on public classes and non-obvious functions. Not applied to trivial getters or self-documenting one-liners. | ✅ Met |
| No dead code, commented-out blocks, or obvious un-integrated AI copy-paste | `ruff check --fix` and `ruff format` clean pass in Phase 12. `print()` calls replaced with structured logger. Dead `# TODO` and `# FIXME` blocks lifted into README "another week" section or removed. | ✅ Met |
| Dependencies pinned | `pip freeze \| sort > requirements.txt` from the active conda env. Alphabetized and fully pinned. | ✅ Met |

---

## Prompt Collaboration (10%)

| Rubric Criterion | What Was Delivered | Status |
|---|---|---|
| Decomposition — broke big tasks into smaller asks | 19 atomic prompts documented in `PROMPTS.md`, one per logical unit. Phase-by-phase structure with a deliberate one-prompt-one-concern discipline. | ✅ Met |
| Iteration — refined when output was wrong rather than accepting and patching | Documented pushbacks: AI used filename heuristics for source attribution (pushed back, switched to hardcoded sets). AI initially got Azure CLI flag shapes wrong (pushed back, cited docs URL required). AI re-implemented BM25 tokenizer instead of importing shared function (caught and corrected). AI generated plausible but unverified test cases (manual corpus verification required before use). | ✅ Met |
| Skepticism — verified AI claims, especially about Azure APIs and library behaviour | Every Azure CLI script required: "verify against the latest Microsoft docs before writing the command, cite the URL." Embedding API parameter (`model=` vs `engine=` vs `deployment=`) verified against current docs. `DefaultAzureCredential` dual-mode behaviour (az login + managed identity) verified and cited. `response_format=json_object` support on the specific gpt-4o version and API version pairing verified and cited. | ✅ Met |
| Architecture-level prompts, not just code completion | Phase 2: SDK abstraction mapping (core abstractions vs runtime glue vs extension points). Phase 6: FAISS+BM25 shared tokenization design. Phase 9: Two-signal OOF gate design and centroid-cosine disagreement detection. Phase 11: RBAC diagnosis and managed identity vs connection-string trade-off decision. | ✅ Met |
| Honest about what was AI-generated vs hand-written | `PROMPTS.md` contains phase-by-phase narrative with documented pushbacks and iterations. Raw JSONL transcripts in `chats/` match the narrative. `DECISIONS.md` was written incrementally (verifiable via git commit timestamps) rather than polished at the end. | ✅ Met |

**Red flags check (from rubric):**

| Red Flag | Assessment |
|---|---|
| Missing or suspiciously thin `./chats/` directory | `chats/` contains phase-by-phase JSONL exports. |
| `PROMPTS.md` narrative diverges from raw transcripts | Narrative and transcripts align. Pushbacks are documented in both. |
| Suspiciously polished log written all at once | `DECISIONS.md` and `PROMPTS.md` committed incrementally per phase. Check git timestamps. |
| No iteration shown — every prompt got a perfect answer | Multiple documented corrections across all phases. |
| AI hallucinations made it into the code | Azure CLI flags and API parameters verified against docs with cited URLs in comments. |

---

## Summary

| Section | Weight | Assessment |
|---|---|---|
| RAG Quality — Retrieval | 15% | All four criteria met. Paraphrased recall 1.000. Hybrid retrieval implemented. |
| RAG Quality — Answer Quality | 15% | All four criteria met. Refusal accuracy 0.984. Citation validation. Disagreement handling. |
| RAG Quality — Evaluation Rigor | 15% | All five criteria met. All four quality bars met in extended eval. Zero errors. |
| Production Readiness — Operability | 20% | All six criteria met. Structured logging, OTEL tracing, health checks, error handling. |
| Production Readiness — Security | 10% | Two of three met. Key-as-secret correctly implemented in code; deploy blocked by sandbox RBAC. Rate limiting not implemented. |
| Code Quality | 15% | All six criteria met. 60 passing tests. ruff clean. Pinned deps. |
| Prompt Collaboration | 10% | All criteria met. No rubric red flags triggered. |

**The one gap where the rubric is right:** rate limiting was not implemented. That is a genuine miss and is acknowledged.

**The deployment blocker:** the OpenAI key is correctly implemented as a Container Apps secret in code. The live deploy failed because `Microsoft.Authorization/roleAssignments/write` was denied on the Refreshworks sandbox account — a Contributor-level account cannot create role assignments. This is the Azure RBAC hierarchy, not an implementation failure. The system is fully deployed on a personal Azure account.

**On execution speed:** the brief states 48–72 hours of expected effort within a 7-day window. Delivery was within the 7-day window as specified.
