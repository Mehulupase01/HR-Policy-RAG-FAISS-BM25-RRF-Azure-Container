# AI Engineer Technical Interview: RAG System on Azure

Welcome, and thanks for taking the time. This exercise is designed to give us a realistic look at how you build, evaluate, and ship a RAG system to production. We'd much rather see a polished, well-evaluated, narrowly-scoped solution than an ambitious one that doesn't run.

## The Task

Build a Retrieval-Augmented Generation (RAG) system that answers employee questions over the provided HR policy documents, then deploy it to Azure.

**Concretely, you will:**

1. Use the provided RAG SDK template (`https://github.com/refreshworks-ai/rag-python-sdk-template.git`) as your starting point
2. Implement a RAG pipeline over the documents in `./corpus/`
3. Expose the RAG as an HTTP API (a single `POST /query` endpoint is fine)
4. Containerize and deploy the API to Azure Container Apps in the resource group we've provisioned for you
5. Build an evaluation harness against the corpus and demonstrate that your system meets a quality bar of your choosing
6. Document your work, your decisions, and your prompt collaboration

## What's Provided

- `https://github.com/refreshworks-ai/rag-python-sdk-template.git` — Our internal RAG SDK template. Read the docstrings before reaching for alternatives. You may add to it; please don't fork its core abstractions.
- `./corpus/` — 32 HR policy documents (24 markdown + 8 PDF) drawn from two real publicly published company handbooks. See [CORPUS_SOURCES.md](CORPUS_SOURCES.md) for provenance, licenses, and the deliberate quirks (e.g. some topics appear in both sources with different rules).
- `AZURE_ACCESS.md` — Your sandbox subscription details, resource group, OpenAI endpoint, and how to fetch the API keys.
- An Azure OpenAI resource with `gpt-4o` and `text-embedding-3-large` already deployed in your resource group. Endpoint and deployment names are in `AZURE_ACCESS.md`; the API keys are visible on the resource itself in Azure AI Foundry — grab them there. Use a `.env` for local dev (gitignored, don't commit it). At deploy time, pass the key in as an env var or Container Apps secret. Don't bake it into the image.

## Requirements
- The deployed API responds to `POST /query {"question": "..."}` with `{"answer": "...", "citations": [...]}`
- The system handles out-of-corpus questions gracefully (does not hallucinate)
- The system cites the source documents it used


## Time Expectations

We estimate **48–72 hours** of work for this exercise. Honor system — we won't be tracking it. If you run out of time, document what's left and how you'd do it. We will not penalize an incomplete submission with strong notes; we will be skeptical of a complete submission with no acknowledged tradeoffs.

You have 7 days from receiving this brief to submit.

## Deliverables

1. A working deployed endpoint (URL in your README)
2. Your code in the GitHub repo we've forked for you
3. A `DECISIONS.md` documenting your key choices and tradeoffs (chunking strategy, embedding model, retrieval approach, why this Azure compute target, etc.)
4. A `PROMPTS.md` *and* the raw chat transcripts under `./chats/` — see "AI Collaboration" below
5. An eval results file showing your system's performance on the test set you built
6. A 5–10 minute Loom (or similar) walking through your architecture — optional but recommended

## AI Collaboration

**Use AI assistants heavily.** We do, and we want to see how you collaborate with them. We're not testing whether you can avoid Claude or ChatGPT; we're testing whether you can use them well.

We want **two things** in the repo, not one:

1. **Raw transcripts** — under `./chats/`. Export the full conversation history from every LLM you use on this assignment (ChatGPT, Claude, Cursor, Copilot Chat, Gemini, whatever — all of it) and commit the exports. Whatever format the tool produces is fine: JSON, markdown, plain text, screenshots if it's the only option. We want to read what you actually asked, not just your summary of it. Redact any keys or personal data before committing.
2. **`PROMPTS.md`** — your curated narrative on top of those transcripts:
   - A chronological log of meaningful AI interactions (skip "fix this typo")
   - For each: what you were trying to accomplish, what you asked, what you did with the output (kept as-is / edited heavily / threw out), and a pointer into the relevant raw chat file

Commit both incrementally as you work. We'd rather see an honest "I asked Claude to write this whole module and rewrote the auth handling" than a fabricated retrospective — and the raw transcripts let us tell the difference.

## Evaluation

We score on:
- **RAG quality (45%)** — retrieval, faithfulness, edge case handling, eval rigor
- **Production readiness (30%)** — secrets handling, observability, deploy correctness
- **Code quality (15%)** — structure, typing, tests, documentation
- **Prompt collaboration (10%)** — thoughtfulness, iteration, decomposition

The detailed scoring sheet is in `RUBRIC.md` (provided) — same one we'll use.

## The Walkthrough

After submission, we'll book 45–60 minutes to go through it together. Be ready to:
- Walk us through the architecture
- Show us a query that retrieves badly and discuss how you'd improve it
- Defend a tradeoff you made
- Tell us what you'd do with another week

## Submission

Open a PR to `main` with everything in place. Tag @[username] when you're done. We'll deploy it to a staging slot to verify it runs, then schedule the walkthrough.

Questions before you start? Email [contact]. Once you start, please don't ask us for clarification on the requirements — make assumptions, document them in `DECISIONS.md`, and move on.

Good luck.
