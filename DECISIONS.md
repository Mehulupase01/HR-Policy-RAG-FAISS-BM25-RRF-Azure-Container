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

## D-06 Markdown chunking strategy

**Context**
Markdown documents have explicit heading hierarchy. We want chunks that
respect document structure.

**Considered**
Fixed-size / sentence-level / paragraph-level / header-aware (H2/H3)

**Choice**
Header-aware on H2/H3 boundaries. Each chunk gets a breadcrumb prepended for embedding.

**Reasoning**
If we see Headings carry semantic meaning and a chunk's section title is information that should be in its embedding and also Header-aware splits also aligns with how humans naturally find info in these kind of textual content

**Trade-off accepted**
Some short H2 sections attach to other H2 sections and some long paragrahs pack within

**If I had more time / future work**
I would've tried implementing semantic chunking, embedding adjacent paragraph pairs and split where there's a drop in similarity.

## D-07 PDF chunking strategy

**Context**
PDFs lose explicit heading structure when text is extracted

**Considered**
Font-size based heading detection / paragraph-pack / fixed-size with overlap

**Choice**
Paragraph-pack with form-feed (\f) as a soft boundary

**Reasoning**
Our PDFs are pandoc/typst conversions thus have clean text with intact paragraph breaks, no complex tables Hence Paragraph-pack is simpler and as effective as font-size detection on this content

**Trade-off accepted**
No breadcrumbs for PDF chunks and page markers compensate

**If I had more time / future work**
I could have used pdfplumber, which has structure analysis to detect heading-like elements (large/bold text starting a section)

## D-08 Chunk size + overlap

**Context**
Trade-off between context-per-chunk and retrieval precision

**Considered**
400/50 OR 800/100 OR 1200/150 (But these can be many values)

**Choice**
800 tokens max, 100 token overlap

**Reasoning**
So we do the math, 800 tokens almost fits a complete policy paragraph in this corpus and the 100-token overlap (~12.5%) covers boundary cases and lastly  the top-4 retrieval gives gpt-4o  roughly 3,200 tokens (800*4) of context which is plenty of headroom in the 128k window.

**Trade-off accepted**
Larger chunks might marginally improve answer quality, but this needs test based verification.

**If I had more time / future work**
If I had more time then I could've runned tests across
{400/50, 600/75, 800/100, 1000/125}, report the trade-off curve soo the decision is based on precision than assumption

## D-09 Tiny + consolidated file handling

**Context**
Two corpus contrasts oen very short files (a few hundred bytes), and the other a consolidated PDF that duplicates the markdown splits

**Considered**
For Tiny: Split anyway (creates useless single chunks) / keep whole
For Consolidated: Ingest (creates duplicates) / skip / ingest
with markdown preference

**Choice**
For Tiny: which mostly are <400 tokens, in that case we make a whole file chunk regardless of structure
For Consolidated: I just hardcoded in the loader to skip the PDF

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
