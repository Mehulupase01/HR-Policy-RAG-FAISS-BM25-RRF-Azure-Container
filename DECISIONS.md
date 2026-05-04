# Decisions

## D-01 Compute Target

**Context**
The readme & email mandates Azure Container Apps but the SDK template assumes Azure
Functions.

**Considered**
Container Apps; Azure Functions; AKS; App Service

**Choice**
Azure Container Apps

**Reasoning**
Required by assignment rules

**Trade-off accepted**
The SDK is built for Azure Functions but we replace the function_app.py with FastAPI which can make the containerization work, though we keep the modules of SDK agent/, ingestion/, blob_client/ mostly the same

**If I had more time / future work**
If potentially a second service starts could be anything then I could add pub/sub. 

## D-02 Web Framework

**Context**
Need an HTTP runtime that hosts the SDK's Python modules

**Considered**
FastAPI / Flask / standalone aiohttp

**Choice**
 FastAPI

**Reasoning**
It is better and has Native async which is inline with AsyncAzureOpenAI, plus data validation is automatic with pydantic and moreover it is cleaner, easier to maintain and high performance. also it is very flexible. 

**Trade-off accepted**
Doesn't have auth but we don't need it for this assignment either

**If I had more time / future work**
Add OAuth2/JWT middleware so /query isn't open to the public internet

## D-03 Vector Store

**Context**
In order to find similar chunks at query time with the whole retrieval process. SDK template uses Qdrant

**Considered**
FAISS / Qdrant / Azure Doc Intelligence + Azure AI Search / PGVector

**Choice**
FAISS in memory, with embeddings.parquet + faiss.index + bm25.pkl persisted to Azure Blob Storage and downloaded on container start

**Reasoning**
Our Corpus is just around 30 documents, 31 documents to be precise (skipping the consolidated doc) soo maybe we would have around 150-350 chunks or max 500 and thus In-memeory FAISS query latency would be like sub-miliseconds, plus operational cost of running another container clearly outweighs benefits. 

**Trade-off accepted**
Cold start downloads the index from Azure Blob and loads into memory (maybe just a few seconds). Doesn't scale past 1M chunks (actually no way near it). No native metadata filtering (this is kind of a bummer) but given the corpus size this is best. 

**If I had more time / future work**
Move to Azure AI Search if the corpus grows past maybe 50k chunks, or to Qdrant for native hybrid + metadata filtering

## D-04 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-05 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-06 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-07 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-08 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-09 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO

## D-10 TODO

**Context**
TODO

**Considered**
TODO

**Choice**
TODO

**Reasoning**
TODO

**Trade-off accepted**
TODO

**If I had more time / future work**
TODO
