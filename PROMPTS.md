## Phase 1: Setup & Azure access
**Context:** Just pure environment setup. No AI used 

### Gave Instructions to Codex about what the project is and basically a project brief: 

Use $Flagship Project Kickoff

Use D:\Mehul-Projects\Project Starter Codex.md as the standing 
charter.

So, you going to be my coding assistant for a RAG Project for Resfreshworks AI
I am a AI Engineer, you are my collegue. 

Read all the files I reference below before answering anything. When you're not sure about something Azure-specific, say so and check the azure docs as far as I know Microsoft azure had many changes etc, soo better to refer to their docs.

What we're building: A RAG (Retrieval-Augmented Generation) system over 32 HR policy documents. So an employ asks question the system retrieves relevant policy passages and uses GPT-4o to answer with citations and we deploy all this in a containerized manner to Azure Container Apps. 

Files to read for context: README. md has the assignment brief, CORPUS_SOURCES.md what's in the corpus and the deliberate quirks, AZURE_ACCESS.md has Azure resource details, DECISIONS.md has architectural decisions & trade offs made so far which I will fill. 

sdk/AGENTS.md and sdk/README.md has the SDK template's own conventions.

Architecture: For API FastAPI at app/. Single POST /query endpoint. Returns {answer, citations}.  

SDK is at sdk/. We keep its Python modules (agent/, ingestion/, blob_client/) but replace its Azure Functions runtime with our FastAPI wrapper. 

The Assignment brief says "don't fork the core abstractions” and we adhere to that by extending and wrapping, not rewriting much. 

For Vector store: FAISS in-memory, persisted as parquet + .index files in Azure Blob Storage and this loads on startup, and the sdk is I think designed around Qdrant but we are not using Qdrant instead we are using FAISS, which I feel is much better for this project.

Lexical: BM25 alongside FAISS for hybrid retrieval.

Retrieval: Hybrid (dense + BM25) fused via Reciprocal Rank Fusion (k=60), So clearly reranking is always better. 

LLM: We are using Azure OpenAI gpt-4o, deployment name gpt-4o. I have the keys and we have to make sure we never ever commit keys to GitHub and also we never commit .env to GitHub.

Embeddings: Azure OpenAI text-embedding-3-large, deployment name text-embedding-3 large, which has 3072 dimensions.

Compute Target: Azure Container Apps (required in assignment) we can deploy with azure container app CLI interface, the sdk is made for Azure Functions though but we are making a FastAPI wrapper soo that it works in containerized manner. 

Secrets: Container Apps secret for OpenAI key and for Blob storage we can used Managed identity.

Corpus details: The corpus has 32 files = 24 markdown + 8 PDF, drawn from two real handbooks (OpenGov Foundation US, Made Tech UK) also it is important to note some topics appear in both with different rules so the system must surface disagreement, not merge. 

There’s this one PDF (opengov handbook-consolidated.pdf) which duplicates content from the markdown splits we can just skip it during ingestion. File-to-source mapping is hardcoded (see CORPUS_SOURCES.md) don't infer from filenames. 

Conventions: So the Python version is 3.11, type hints throughout, Pydantic for API models. 

Tests: Perform with pytest. After writing or modifying code, run the relevant tests yourself and fix anything that fails before reporting back. 

Also please no fake or made up data in tests where real data is available for retrieval/embedding tests, so load the actual data/index/ artefacts.  

When you're about to call an Azure SDK or Azure CLI command I want you to check through the latest Microsoft docs first and cite the URL these change often and as far as I know maybe your training data may be old and might have old info about this. 

When something I ask conflicts with these conventions or the architecture or the plan, then in that case notify me and alert me, push back instead of going along with it, that way we can avoid any deviations from the goal. 

Environment: I have created a env in anaconda called ‘rag’ and honestly I prefer to manage environments through Anaconda Navigator or conda commands.  

Docker Desktop is running and GitHub Desktop for commits/pushes I rarely use git CLI, prefer GUI for all this and lastly, I am using VS Code as the IDE.

Acknowledge you've read this & you are ready or not, also wether you understand what I am trying to make. Lastly don’t summarize this back to me.


### Explained Codex the roughly planned Phases and gave some more instructions: 

Okay below is the rough list of phases I have planned, I expect you to do all the necessary checks, tests, verifications before marking each phase as complete as once a phase is complete I will push the changes : 

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


## Phase 2: Repo scaffolding & SDK exploration

**Context:** Here I sort of needed to understand what the SDK considers core abstractions vs. extension points before building on top of it. 

### Here I asked Codex to deeply explore the SDK, and the Architecture: 

Now before we write a single line of our own code, I really want to understand what the Refreshworks SDK actually gives us so as per the assignment & readme it says that we shouldn't fork its core abstractions, which means we need to know which parts are the core abstractions versus which parts are just runtime glue we're free to replace. 

So, I want you to read through the SDK and also specifically: 

>sdk/backend/agent/
>sdk/backend/ingestion/
>sdk/ backend/blob_client/
>sdk/backend/function_app.py
>sdk/AGENTS.md file
>But also the rest other files 


Then I want you to write me a map of what you found, organised into four sections:


1. First, the core abstractions the classes and functions that look like they're meant to be stable interfaces, the ones we should keep using rather than replace. 
2. Second, the extension points places where the SDK clearly invites you to swap in a different implementation, like a vector store interface or an embedder protocol. 
3. Third, every line of code in the SDK that couples it to Azure Functions specifically the runtime glue we'll be replacing with FastAPI. 
4. Fourth, every line that couples it to Qdrant. Since we're using FAISS instead. 


Lastly, I want you to recommend on which SDK files we keep as-is, which we wrap or extend, and which we replace right away, and given that we're deploying to Container Apps with FAISS. 

Please don't write any code yet. I really want the architectural read first, once I'm like 100% convinced you've understood the SDK properly, only then we'll start building.


### I further asked Codex to fill in the erd-template: 

Okay thanks, your analysis looks okay ! Thanks 

So the SDK ships with a template that they expect us to fill in. Go and open sdk/planning/erd-template.md

Now I want you to fill this in with the actual project architecture, not some generic one. Use the decisions we've made in the project brief and what you found in the SDK exploration earlier.

For the diagrams, include a system architecture diagram as a mermaid flowchart showing the request path from client through FastAPI to the retriever, then to the generator, and back. If I am not wrong there are already diagrams in the erd template, make similar to them or better ones. 

Then include a sequence diagram for ingestion which goes load then chunk then embed then index then upload to Blob.

And another sequence diagram for a query at runtime.

For the vector-store schema, spell out what we'll be writing to disk. So that's chunk_id, source, file_path, chunk_idx, text, embedding, and any metadata fields you think we need.

Also list the environment variables the app needs to run, I want this documented properly.

And then document the API contract for POST /query with example request and response bodies, plus the error codes we'll return.

One thing, please stay grounded in what we've actually decided. Don't invent infrastructure I haven't asked for, so no Redis, no Postgres, no Functions runtime sneaking back in. Please stick to what's in the brief.


### Codex made some mistake, I pointed out the mistakes: 

There are a few things I want you to fix before we move on.

First, the env var name. You've used AZURE_OPENAI_API_KEY in the ERD but our .env file from Phase 1 has AZURE_OPENAI_KEY. These need to match otherwise the app will just fail to read the key at startup. Go and make sure the ERD, the .env.example, and wherever we read config in the app all use the same name.

Second, in the parquet schema you have both a source field and a handbook field and they're basically doing the same thing. The standard one is source, that's what the disagreement detector is going to read, with values "opengov" or "madetech". So just drop handbook, we don't need both.

Third, for BM25 you've written that it "can be rebuilt from the parquet text field at startup" and while that's technically true, but that's not what we're doing. 


We're persisting bm25.pkl to Blob alongside the FAISS index and parquet, and loading it on startup and to be honest rebuilding at startup is like quite slower and plus it's also the kind of thing that can cause tokenization drift between index time and query time which is exactly the bug we're trying to avoid. 


Update the ERD to reflect that we persist and load bm25.pkl.

And lastly, remove AZURE_STORAGE_CONNECTION_STRING from the env vars. I know you've listed it as a local dev convenience but we're using DefaultAzureCredential which handles both local development via az login and production via managed identity, no connection string needed, also I think it does cause a security snag as well.

## Phase 3: The deployable skeleton

