## Phase 1: Setup & Azure access
Context: Pure environment setup. No AI used 

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


### Explained Codex the Phases and gave some more instructions: 