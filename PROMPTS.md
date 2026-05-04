## Phase 1: Setup & Azure access
**Context:** Just pure environment setup. No AI used

### Gave Instructions to Codex about what the project is and basically a project brief:

>This was one of the first prompts that I gave to Codex, with the project starter .md instruction set and project kickoff skill that are sort of my standard templates for any production grade project that I make with Codex.

>Secondly I explained the whole RAG System's Architecture with full detailed setup, retireval, cloud deployment, embedding, geenration, secrets, docker & etc.

>



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

### I further asked Codex to create a schema/proforma for me to write DECISIONS.md:

So the rubric wants to see decisions documented as we make them, not all written up at the end in one go. So, let's start that work now since its still the very beginning of the project.

As you can see I have already DECISIONS.md at the repo root.

I want 10 stub entries in there, D-01 through D-10, that we'll fill in progressively as we go through each phase, maybe Iâ€™ll create more if required

For the format, keep it consistent for each entry. A heading like ## D-NN <Decision Title> then short bold sections for:

Context (why this decision needs to be made)
Considered (the alternatives we looked at)
Choice (what we picked)
Reasoning (why we picked it over the others)
Trade-off accepted (what we're explicitly giving up)
If I had more time / future work (the future work or v2 or something).

Leave all of them empty / todo placeholders for now as I am going to fill it.

But fill in title for the first three. D-01 is the compute target, D-02 is the web framework, D-03 is the vector store

## Phase 3: The deployable skeleton

### Creating FastAPI Skeleton:
Okay soo now we actually start writing code, we are starting with Phase 3

The goal for this prompt is just the skeleton of the API. It should be production-shaped, but the actual RAG logic is stubbed out for now.



So the whole point is that we want something we can deploy to Azure now and try to prove that pipeline works before we get into the clever retrieval and generation stuff, altogether we are doing this now than later as it is much better to debug small codebase than a huge one.

Set up a FastAPI app under app/ with a sensible module split

The factory and lifespan handler live in app/main.py.

Config goes in app/config.py using pydantic-settings, loading from .env. And I want it to fail fast with a clear error if a required variable is missing, silent fallback to defaults is exactly the kind of thing that bites you in production so please don't do that.

Health endpoints go in app/api/health.py, I want two of them  /healthz should always return 200 quickly and synchronously, and it should never call Azure OpenAI. This is what the platform's load balancer hits to check if the container is alive, so if OpenAI is having a issue then I don't want that to take down our health check too!

/readyz on the other hand should actually call Azure OpenAI with a two second timeout just to confirm the upstream is actually reachable.

The query endpoint goes in app/api/query.py as POST /query. For now it returns hardcoded mock JSON, but I want real Pydantic models for the request and response so the contract is solid even though the data is fake.

The models I want are QueryRequest with question: str and an optional top_k: int | None

Then I want Citation with file_path, source typed as Literal["opengov", "madetech"], chunk_idx, and snippet


Lastly the QueryResponse with answer, a list of citations, and retrieval_scores.

The stub /query should just return something like {"answer": "Stub for Later phase Blah blah"citations": [], "retrieval_scores": null} so we have something real to curl once it's deployed

Also wire up exception handlers. Pydantic validation errors come back as 422 with the field details, HTTP exceptions pass through cleanly, and anything uncaught becomes a 500 with the traceback logged but nothing internal leaked in the response body

Skip auth, CORS, rate limiting, and observability for now, all of that comes in later phases
Once it's done, run it locally with uvicorn and curl both endpoints. Show me what came back

### Containerizing the App:

Okay so now we actually try to deploy this thing.

The reason I want to do the whole deployment part now, with just a stub and not even real RAG yet, is that honestly the deployment is where most projects burn hours unexpectedly. ACR auth issues, wrong CLI flag names, containers failing to start with no logs, ingress not configured properly


So thatâ€™s the reason why I'd much rather discover all that now with a small FastAPI app than at the end moment when we have actual RAG to debug on top of it.

Write deploy/deploy-stub.sh as a bash script that really sort of makes sure whatever's missing and deploys the app. It should read the OpenAI key from .env.

For the Azure resources:

the resource group is rg-rag-interview-mehul
region is swedencentral.


Call the Azure Container Registry acrragintvwmehul, but be aware ACR names have to be globally unique so adjust if it collides. The Container Apps environment is cae-rag-interview and the app itself is hr-rag-stub.

The script should be safe to run more than once. So just create the ACR if it doesn't exist (Basic SKU is more than fine, admin-enabled is also fine for v1), and use az acr build to have the registry build the image directly from source, that way I don't have to build and push from my laptop. Create the Container Apps environment if it doesn't exist either.

Then create or update the Container App itself. Half a CPU, 1 GiB memory, scale between one and three replicas, external ingress on port 8000. Also most importantly, the OpenAI key really needs to go in as a Container Apps secret, not as a plain environment variable whatsoever. The other config like endpoint, API version, deployment names, those can be plain env vars which I think should be fine.

One thing before you write the actual az containerapp create command. I want you to verify against the latest Microsoft docs that the flag names you're using are current.

As per my google search these have changed across CLI versions, things like --secrets versus --secret-name, the way registry identity is specified, the ingress flags, and once again maybe your training will be old soo lookup the docs. Also just cite the docs URL you used as a comment at the top of the script.

Once the deploy succeeds, fetch the app's FQDN and curl /healthz against it. If it returns 200, echo the URL clearly so I can just simply copy paste it.

And lastly finish the script with a comment block listing what it explicitly does not set up for i.e. things like custom domains, monitoring, autoscaling etc. That way the scope is honest and we know what's left for later phases.

Also by the way I forgot to tell, AZURE_ACCESS.md has the Azure Access details, my account email ID is upasemehul@gmail.com


### Deploying the App:

Okay so now we actually try to deploy this thing.

The reason I want to do the whole deployment part now, with just a stub and not even real RAG yet, is that honestly the deployment is where most projects burn hours unexpectedly. ACR auth issues, wrong CLI flag names, containers failing to start with no logs, ingress not configured properly


So thatâ€™s the reason why I'd much rather discover all that now with a small FastAPI app than at the end moment when we have actual RAG to debug on top of it.

Write deploy/deploy-stub.sh as a bash script that really sort of makes sure whatever's missing and deploys the app. It should read the OpenAI key from .env.

For the Azure resources:

the resource group is rg-rag-interview-mehul
region is swedencentral.


Call the Azure Container Registry acrragintvwmehul, but be aware ACR names have to be globally unique so adjust if it collides. The Container Apps environment is cae-rag-interview and the app itself is hr-rag-stub.

The script should be safe to run more than once. So just create the ACR if it doesn't exist (Basic SKU is more than fine, admin-enabled is also fine for v1), and use az acr build to have the registry build the image directly from source, that way I don't have to build and push from my laptop. Create the Container Apps environment if it doesn't exist either.

Then create or update the Container App itself. Half a CPU, 1 GiB memory, scale between one and three replicas, external ingress on port 8000. Also most importantly, the OpenAI key really needs to go in as a Container Apps secret, not as a plain environment variable whatsoever. The other config like endpoint, API version, deployment names, those can be plain env vars which I think should be fine.

One thing before you write the actual az containerapp create command. I want you to verify against the latest Microsoft docs that the flag names you're using are current.

As per my google search these have changed across CLI versions, things like --secrets versus --secret-name, the way registry identity is specified, the ingress flags, and once again maybe your training will be old soo lookup the docs. Also just cite the docs URL you used as a comment at the top of the script.

Once the deploy succeeds, fetch the app's FQDN and curl /healthz against it. If it returns 200, echo the URL clearly so I can just simply copy paste it.

And lastly finish the script with a comment block listing what it explicitly does not set up for i.e. things like custom domains, monitoring, autoscaling etc. That way the scope is honest and we know what's left for later phases.

Also by the way I forgot to tell, AZURE_ACCESS.md has the Azure Access details, my account email ID is upasemehul@gmail.com
