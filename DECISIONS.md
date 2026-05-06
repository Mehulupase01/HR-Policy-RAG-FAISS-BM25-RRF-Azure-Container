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

## D-04 Embedding model

**Context**
We have to convert text to vectors for retrieval

**Considered**
text-embedding-3-large (3072 dimensions) / text-embedding-3-small (1536 dimensions)

**Choice**
text-embedding-3-large

**Reasoning**
Already deployed in the provided Azure resource, secondly its higher on benchmarks scores than small and lastly the storage for such small corpus with around 250 to max 500 chunks the storage use is almost nothing.

**Trade-off accepted**
Maybe double or tripple the embedding API cost as compared to small, but for a corpus this small it would again be a really small amount ideally.

**If I had more time / future work**
Maybe experimented with Open-Source embedding models like Qwen 3, BGE-M3 etc.

## D-05 LLM for generation

**Context**
Needed a LLM to synthesize answers from retrieved chunks

**Considered**
gpt-4o / gpt-4o-mini / gpt-3.5

**Choice**
gpt-4o (deployment 2024-11-20)

**Reasoning**
Deployed in the provided resource

**Trade-off accepted**
Much more cost per query as compared to gpt-4o-mini etc.

**If I had more time / future work**
I would do a A/B test with gpt-4o-mini on the same evaluation set and I would likely use mini for non-disagreement cases and reserve gpt-4o for disagreement
prompts

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
Soo putting the tiny files as whole chunk is better as value of such short files is same as the whole file, we skip the consolidated PDF as ingesting it would double-index OpenGov content causing issue in retrieval.

**Trade-off accepted**
Consolidate PDF is skipped since it can be marked as dedup step

**If I had more time / future work**
Some sort of content validation and similarity check mechnism that would flag such near duplicate cases.

## D-10 Retrieval strategy

**Context**
Pure dense retrieval misses verbatim policy keywords i.e. FMLA and on other hand pure lexical misses paraphrases or changed queries.

**Considered**
Dense only / BM25 only / hybrid via score-weighted sum / hybrid via Reciprocal Rank Fusion

**Choice**
Hybrid via RRF with k=60

**Reasoning**
If we see RRF it normalizes across methods it uses ranks and not the raw scores so the dense retrievals's [-1,1] scale doesn't collide with BM25's unbound scale, K=60 which is standard as per the paper.

**Trade-off accepted**
Two indexes to keep in sync. Tokenization consistency enforced by sharing tokenize_for_bm25() between indexer and retriever

**If I had more time / future work**
I would have added a full scale learned cross-encoder reranker on top of the 20 fused results, it increases precision greatly at cost of slight latency overhead


## D-11 top_k for retrieval

**Context**
How many chunks to feed the LLM, and how many to consider for out of corpus detection.

**Considered**
top-3, top-5, top-8, top-10

**Choice**
 Retrieve 8 (for out of corpus judge to see if needed), present 4 to the answerer

**Reasoning**
The out of corpus judge benefits from a few extra chunks to make a better
answer yes or no call. Plus the asnwerer has sufficient context of 4chunks * 800 tokes which is 3200 tokens.

**Trade-off accepted**
Very niche but possible edge cases where the right answer could be at rank 5–8 miss the answerer

**If I had more time / future work**
Best way could be experimenting with different top_k values.



## D-12 Citation Format

**Context**
We need to cite every claim to its source

**Considered**
Inline [1] [2] / structured citation list with file_path + chunk_idx; URL + offset

**Choice**
Structured citation list with file_path + chunk_idx; URL + offset

**Reasoning**
its actually UI-friendly if we ever make an UI plus additionally its verifiable so we basically check every cited key exists in retrieved chunks before returning soo this drops fabricated citations silently

**Trade-off accepted**
a claim sourced from one sentence is cited as the whole chunk. additionally when asnwer is returned, the citations don't poin't to which sentence they belong to although this is too granular to expect but still.

**If I had more time / future work**
I could have sort of experimented with putting a character offset inside the chunk i.e. [start, end] to precisely highlight, btu also this might require LLM to do it, and below gpt-4o its unreliable.


## D-13 Out of Corpus Handling

**Context**
A very naive approach in RAG which is also a rookie mistake by the way is that it retrieves top_k anyway doesn't matter if its relevant or not and the LLM synthesizes an answer which literally causes hallucinations on out of corpus queries

**Considered**
Score-only refusal / LLM-judge-only refusal / two-signal (score & judge) / cosine distance when query is embedded.

**Choice**
The two signal approach score + LLM judge, and we refuse when max rrf < 0.02

**Reasoning**
Soo if we do this by single signal approach i.e. score or LLM judge its very like that it would over or even under refuse, but when two signals make the decision it is much more robust without much latency

**Trade-off accepted**
There always are edge cases where both signals fail in opposite directions, in these case making a boundary is better than wrong and worse than perfect.

**If I had more time / future work**
I could have calaibrated the score further by checking in corpus queries vs out of corpus queries, that could have given a more better value.

## D-14 Source diagreement handling

**Context**
OpenGov (US) and Made Tech (UK) cover the same topics with different rules, and normally a RAG averages them into a fictional unified policy which is wrong.

**Considered**
Always present both / detect disagreement and inject a "compare" instruction / let the LLM figure it out from mixed sources.

**Choice**
We try to detect a disagreement by (multisource presence + centroid) cosine > 0.7 and inject disagreement isntructions into the system prompt.

**Reasoning**
Always presenting both produces bad answers especially considering only one source is relevant, and letting LLM figure it out just fails, so altogtehr detection + instruction is the surgical fix

**Trade-off accepted**
Threshold is deafult which is 0.7 it isn't optimized

**If I had more time / future work**
I would fine tune the threshold on disagreement evaluations.


## D-15 Evaluation framework

**Context**
Neede reproducible measurements of the four metrics

**Considered**
ragas / DeepEval / promptfoo / hand-rolled

**Choice**
Hand rolled approach, 40 hand written test cases

**Reasoning**
Because hand-rolling gives sort of full control over what we measure and a
defensible methodology as every method has weak points anyway and at 40 cases, library overhead isn't worth it.

**Quality bar:** Retrieval recall ≥ 0.85, refusal accuracy ≥ 0.90,
surfaces both sources ≥ 0.75, mean faithfulness ≥ 0.80

**Trade-off accepted**
This test has no statistical significance especially given number of cases is 40 soo the results are indicative.

**If I had more time / future work**
I would implement a cross check with RAGAS also build a built in metrics logging and maybe 100+ case synthetic evaluation generated from corpus.


## D-16 Secrets and Blob auth

**Context**
OpenAI key must not be in image or git. Container needs to read pre-built indexes
from Blob Storage

**Considered**
Plain env vars / Container Apps secrets / Key Vault references / baked into image (rejected)

**Choice**
Container Apps secrets for the OpenAI key and user-assigned managed identity with Storage Blob Data Reader for Blob

**Reasoning**
Container Apps secrets are encrypted at rest and they are refrenced via secretref: soo in this case the code would read a normal en var, and the managed identity removes the blob keys from container entirely soo the same DefaultAzureCredential path just work locally via az login and in production via managed identity.

**Trade-off accepted**
Two step provisioning (storage + RBAC then app) also the rotation of OpenAI key requires az containerapp secret set + revision restart

**If I had more time / future work**
I would have moved OpenAI key into the key vault and referencd via key vault secret URL for centralizaed rotation and this is good espcially when you have multiple apps
