## Phase 1: Setup & Azure access
**Context:** Just pure environment setup. No AI used

### Gave Instructions to Codex about what the project is and basically a project brief:

>This was one of the first prompts that I gave to Codex, with the project starter .md instruction set and project kickoff skill that are sort of my standard templates for any production grade project that I make with Codex.

>Secondly I explained the whole RAG System's Architecture with full detailed setup, retireval, cloud deployment, embedding, geenration, secrets, docker & etc.

>I explained the files, SDK and what this RAG system is for (The 32 HR policy documents) also explained it what .md files exist and why



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

>The Instructions were that it has to run full end to end tests after we complete each phase, also verifications and then commit & push the changes to Github


## Phase 2: Repo scaffolding & SDK exploration

**Context:** Here I sort of needed to understand what the SDK considers core abstractions vs. extension points before building on top of it.

>I asked Codex to deeply explore the SDK, and the Architecture and specifically asked Codex to find the core abstractions and the runtime glues, further asked it to split it into four buckets Core Abstractions, Extension Points, Azure Function glue, and Qdrant glue. 

### I further asked Codex to fill in the erd-template:

>This is because the ERD Template and the Plan.md both I feel were really crucial to fill, as these would also help codex when the context compacts after being full.


### Codex made some mistake, I pointed out the mistakes:
> It made some mistakes which I pointed out in the ERD Template.


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
>In this step I asked Codex to make a FastAPI Skeleton and with barely anything

### Containerizing the App:
>In this step I asked codex to wrap the app in a container, and asked it to do a two stage build to cut down on build tools, also running it locally with .env sort of validates it will run with container app and container secrets instead of .env


### Deploying the App:

>In this step I asked codex to deploy the app, this gets us a real public URL on Azure immediately, so we know the deploy pipeline works before we have anything important to deploy. plus less risk on doing it on early stage than advanced stages. 


## Phase 4: Loading the corpus

**Context**