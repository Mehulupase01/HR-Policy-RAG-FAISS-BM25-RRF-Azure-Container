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


## Phase 8: Generation, citations, and the prompt
**Context:** In this we do the second half of the query path and then we wire up the retriever from phase 7 and build a generator and then connect them in app/api/query.py so POST /Query returns real answers. We also wire the FastAPI lifespan so retriever and cleints are constructed once at startup and not per request.

Also, we are not doing the Oout of Corpus detector and disagreement detector in this phase

>This phase is simple answerer: retrieve, prompt, generate, verify citations and return.

### Building the asnwerer and its system prompt:

>In this step I asked Codex to build the generator and lock in the system prompt that shapes the answer quality.

>Further Codex built the citation validation against the retrieved chunks which prevents the LLM's occasional habit of inventing chunk refrences.

>Also asked it to perform a small test to check citation key behaviour.

### Wiring the retriever and answerer into the FastAPI App:

>I asked Codex to pull the components from phase 6,7 and 8 into a working endpoint, explained it to load FAISS Index once at startup and it stays in the memory for eevry subsequent request.

>I asked Codex to do a bit of error handling i.e. 502, 503 and 422 etc.

>Also to perform tests and a tough case "How many sick days do I get?" and asked it to retur me the responses and retrieval scores

>Codex successfully completed all this and also few recommendations from Codex were partially aceepted.

## Phase 9: Out-of-corpus & disagreement handling

**Context:** We are making two small but important modules:

1. Out of Corpus  Detector: If we are given retrieved chunks + question, it decides wether to refuse based on two signals score threshold + LLM judge.

2. Disagreement Detector: If we are given retrieved chunks, it decides wether they represent two sources disagreeing on the same topic, if yes the answerer's system prompt get's additional instruction of compare & attribute

### Building the out of corpus and disagreement handling:

>I asked Codex to make out of corpus & disagreement detector and handling on top of the working RAG, I asked to create a two signal AND gate for out of corpus handling.

>Further I also asked it to make a centroid similarity disagreement detector which uses (multisource presence + centroid) cosine > 0.7

>I asked it to perform tests that covers the edge cases and the out of corpus truth table (score above/below crossed with judge says yes/no)

>I asked it to do tests on diagreement detector as well by having positive case (two cases with similar centroids) and negative (two cases with orthogonal centroids)

>it completed all these perfectly.

## Phase 10: The evaluation framework

### Asked Codex to make a Test set:

>I asked Code to make a structured test with deliberate category coverage, I also asked it to verify against the actual corpus.

>I asked to create the test like this:
>A] 5 verbatim queries
>D] 8 source-disagreement
>E] 4 single-source-only (where the topic could exist in both but only one source actually covers it)
>F] 5 clearly out-of-corpus

>G] 4 plausibly out-of-corpus (adjacent to corpus topics but not actually covered), and 3 adversarial.

>Codex created the test set, and returned it. I verified them and approved it.

### Asked Codex to make the evalution framwork:

>I asked Codex to build a runner that turns the test set into reproducible numebrs and a readable report.

>I asked Codex to perform the full evaluation locally, with the following metrics to be reported in JSON and results.md:

1. Retrieval Recall >= 0.85
2. refusal accuracy >= 0.90
3. Surface both sources >= 0.75
4. Mean Faithfulness >= 0.80

>At first results weren't that good:

>Overall results:

1. Recall: 0.929 met the 0.85 bar
2. Refusal accuracy: 0.925 met the 0.90 bar
3. Surfaces-both: 0.625 missed the 0.75 bar
4. Mean faithfulness: 0.250 missed the 0.80 bar
5. Mean latency: 3333 ms

>Then I gave it some fixes I had in mind:


1. Fix 1:  Recalibrate the faithfulness judge prompt
2. Fix 2 : The empty-question 422 (case H01) as the eval expected an empty question to be refused with the refusal sentence (200 OK with refusal text) but Instead the API returned 422 because Pydantic rejected the empty string at validation time that's my best guess.
3. Fix 3: The 503 on prompt injection (case H02). just running Azure OpenAI failure mid-eval atleast that's what I think not a system bug, just a flaky run and re-running should fix it

4. Fix 4: look at the D02/D04/D06 logs to diagnose surfaces both, then either fix retrieval or lower the centroid threshold accordingly and re-run

>Updated Results:

1. Recall: met (0.982 >= 0.85).
2. Refusal: met (0.975 >= 0.90).
3. Surfaces-both: met (1.000 >= 0.75).
4. Faithfulness: met (0.982 >= 0.80).

## Phase 11: Real deployment with secrets
**Context:** The same container app in phase 3, now we'll run the real RAG. The shape of the deploy is identical, what changes is:
1. Image now includes full app/
2. Container apps secrets hold the OpenAI key not plain env var
3. A user assignned managed identity grants the app read access to the blob storage container.
4. On starting up the app downlaods the data/index/ from blob as container's filesystem is empty.

### Asked Codex to Deploy the real app with secrets and managed identity

>I asked Codex to provision the managed identity, and then assign it the role to read index from blob and then it deploys the real app with OpenAI key as an encrypted secret rather 

Phase 11 as deferred/blocked by Azure RBAC permissions, not failed architecture. The important pieces are still useful and correct:

1. Real deploy scripts are written.
2. Blob artifacts are uploaded.
3. ACR image builds work.
4. The blocker is specifically missing roleAssignments/write permission for managed identity RBAC.

Real RAG Container Apps deployment was implemented but not completed because the Azure account lacked permission to create RBAC role assignments for the user-assigned managed identity

## Phase 12: Observability, polish, Loom

