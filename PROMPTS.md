## Phase 1: Setup & Azure access
**Context:** Just pure environment setup. No AI used

### Gave Instructions to Codex about what the project is and basically a project brief:

>This was one of the first prompts that I gave to Codex, with the project starter .md instruction set and project kickoff skill that are sort of my standard templates for any production grade project that I make with Codex.

>Secondly I explained the whole RAG System's Architecture with full detailed setup, retireval, cloud deployment, embedding, geenration, secrets, docker & etc.

>I deeply explained it the architecture of the project as to what API, we are using, Vector Store, Retrieval System, LLM. 

>I explained the files, SDK and what this RAG system is for (The 32 HR policy documents) also explained it what .md files exist and why.

>Codex understood them and agreed to help me as a assistant. 



### Explained Codex the roughly planned Phases and gave some more instructions:

1. Phase 1: Setup & Azure access (Which I have completed)
2. Phase 2:Repo scaffolding & SDK exploration (we are starting from here)
3. Phase 3: The deployable skeleton (stub on Azure)
4. Phase 4: Loading the corpus
5. Phase 5: Chunking the documents
6. Phase 6: Embeddings & the FAISS index
7. Phase 7: Retrieval (dense + lexical, fused)
8. Phase 8: Generation, citations, prompt
9. Phase 9: Out-of-corpus & disagreement handling
10. Phase 10: The evaluation harness
11. Phase 11: Real deployment with secrets
12. Phase 12: Observability, polish, Loom through

>The Instructions were that it has to run full end to end tests after we complete each phase, also verifications and then commit & push the changes to Github and also maintain a phase vs percentage complete table.


## Phase 2: Repo scaffolding & SDK exploration

**Context:** Here I sort of needed to understand what the SDK considers core abstractions vs. extension points before building on top of it.

>I asked Codex to deeply explore the SDK, and the Architecture and specifically asked Codex to find the core abstractions and the runtime glues, further asked it to split it into four buckets Core Abstractions, Extension Points, Azure Function glue, and Qdrant glue. 

>Codex very accurately identified and categorized the files

>This was a really important step in the process becasue, its imperative for the model to know the structure of SDK and then building on top of it, especially given that the SDK is framed around Azure functions, and the assignment asks for deployment on Azure Container Apps with ACR & Blob Storage. 

### I further asked Codex to fill in the erd-template:

>This is because the ERD Template and the Plan.md both I feel were really crucial to fill, as these would also help codex when the context compacts after being full.

>This also sort of creates like a high level roadmap/goal that's been set, soo Codex or Claude Code can try to maximize its effort towards achieving that goal. 

### Codex made some mistake, I pointed out the mistakes:
> It made some mistakes which I pointed out in the ERD Template.

>It used the wrong env variable name for Azure OpenAI key which I asked it to fix.

>It created an extra uneccessary field field in the parquet schema, i.e. source field & the extra one was handbook field which was not required.

>It misunderstood that we are rebulding the BM25 Index every time we startup that's not true, it would create tokenization drift and also it is much slower soo instead we persist the bm25.pkl at ingest time to Blob alongside FAISS Index and Parquet. 


### I further asked Codex to create a schema/proforma for me to write DECISIONS.md:
> In this I asked codex to create a structured schema for DECISIONS.md which had fields like:
1. Context (why this decision needs to be made)
2. Considered (the alternatives we looked at)
3. Choice (what we picked)
4. Reasoning (why we picked it over the others)
5. Trade-off accepted (what we're explicitly giving up)
6. If I had more time / future work (the future work or v2 or something).


## Phase 3: The deployable skeleton
**Context:** In this step I asked Codex to create a FastAPI Skeleton, then I asked it to containerize the App and Lastly I asked it to deploy it. This step is crucial as doing this after completing the whole development increases the chances of messing up during deployment. 

### Creating FastAPI Skeleton:
>In this step I asked Codex to make a FastAPI Skeleton and with barely anything in it

### Containerizing the App:
>In this step I asked codex to wrap the app in a container, and asked it to do a two stage build to cut down on build tools, also running it locally with .env sort of validates it will run with container app and container secrets instead of .env

>Codex did it as expected without any bugs. 

>It made sure the OpenAI Key and other things from env are passed as Container App Secrets and not as plain env variable.

### Deploying the App:

>In this step I asked codex to deploy the app, this gets us a real public URL on Azure immediately, so we know the deploy pipeline works before we have anything important to deploy. plus less risk on doing it on early stage than advanced stages. 

>It gave the deployed app URL: https://hr-rag-stub.lemonisland-a021bbbf.swedencentral.azurecontainerapps.io


## Phase 4: Loading the corpus

**Context**In this phase I asked Codex to make the ingestion pipeline, and it doesn't do chunking, embedding etc. it just reads files and attaches metadata. 

### Building the Corpus Loader: 

>In this step Codex helped me build the file reader and tag each document with its source. 

>It was imperative for me to specify that we are doing a hardcoded list approach, as for any LLM the general instinct is to write a clever filename matcher, this messes up with unknown files and breaks in subtle ways in cases.

>I asked Codex to also skip the consolidated PDF

>I also asked Codex for suggestions, it suggested firstly to change from Raw path to Relative path, it was a good suggestion given how whole paths would look in parquet, citations etc.

>It also suggested on PDF fallback handle extraction exceptions

>I accepted first three suggestions but rejected last one about document_id, which it suggested to add. 


## Phase 5: Chunking the documents

**Context:**Second stage of ingestion. Chunking strategy is one of the rubric's explicit grading targets, so the choice and the measured stats both matter.

### Build the Chunker: 

>I asked Codex to split documents into retrieval-sized pieces while preserving their structural context, and then further for markdown files I asked it to do header aware chunking

>I also asked it to do implement max_tokens=800, overlap_tokens=100, min_tokens=50 which can also be fine tuned later on as well. 

>It made chunker.py with markdown header-aware chunking and PDF paragraph/page-aware chunking

>Chunk frozen dataclass in models.py

>It also created test_chunker.py covering tiny files, breadcrumbs, overlap, max-token safety, PDF page markers, and chunk_idx reset

>It Updated loader PDF extraction to preserve page breaks with \f

### Recommendations by Codex: 

>Codex also suggested three solid suggestions

1. Make chunk_id deterministic
2. Add a real-corpus metadata invariant test, it makes sure every generated chunk has some checks in place
3. Tightening small section merge behaviour

>The recommendations were really solid, I asked Codex to incorporate them immediately


## Phase 6: Embeddings & the FAISS index

**Context:** The third (and final) ingestion stage, After this phase, we have a queryable index and the end-to end ingestion (load > chunk > embed > index > upload) becomes one command

### Building the embedder:

>In this step I asked Codex to wrap the Azure OpenAI embdedding call so we can just run it against the whole corpus without falling over, I also asked to make a rate limiter which prevents throttling during mid-run so the retries handle the failure that come along. 

>Codex completed all of it perfectly in one go, and it created the indexer, blob_store, storage setup and also a indexer test

>I didn't run the python - app.ingest as that would call Azure OpenAI and actually spend embedding tokens

>Codex had missed out on core packages like azure-storage-blob and azure-identity but it is not reflected in requirements.txt so this could potentially fail at runtime, I had suspected the bug and Codex also recommended the bug I suspected.

>Codex recommended to align the blob container name with what we have in .env so we standardized on rag-index

>Soo Codex's recommendation and the initial prompt for embedder made everything work perfectly. 

### Building the indexer, the Blob persistence, and the ingest entry point: 

>I asked Codex to build the indexer, the blob persistance layer and the orchestrator that ties the whole ingestion pipeline together with a single command. 

>Two things that are very imperative that I made very clear to Codex are L2 normalize before adding to FAISS and the second is shared tokenize_for_bm25 function, this prevents the indexer vs retriever tokenization drift bug. 

>Codex completed this phase perfectly. 

## Phase 7: Retrieval (dense + lexical, fused)

**Context:** In this phase we do the first half of the query path. Input is a string question and output is top_k RetrievedChunks stored by RRF Score, and each carrying source/file_path/breadcrumb/text plus its dense score, BM25 rank and final RRF score. 

## Building the hybrid retrievar: 

>I asked Codex to make a hybrid retrieval system with RRF fusion. again the shared-tokenization import is the one detail that prevents a class of subtle bugs that are otherwise nearly impossible to catch. 

>I asked Codex to create tests and run them and also I asked it to do out of corpus tests

>I specified the technicalities for the hybrid retrievar to Codex rrf_constant=60, dense_pool=20, and bm25_pool=2

>I made some clarification about the pool size to Codex, that it retrieves 20 from each method and take 8 from the union, not 8 from each, the core reason is that a chunk ranked 9th by dense might be 2nd by BM25, and on RRF that chunk should actually win so obviously taking only 8 from each would lose it.

>I asked Codex to do the disagreement coverage test as well.

>I asked Codex to return some quality related stats from the tests it did, and the results were in expected or good range.

>Lastly it gave some recommendation regarding adding a tiny SDK adapter, I denied the recommended change as that's something more better in next phase as the adapter is the bridge between our retrieval layer and the SDK's generation layer. 