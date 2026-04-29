# Interview Evaluation Rubric (Internal)

Score each subsection 1–5, then weight per the totals. Aim to score during the walkthrough, not just from reading the repo.

**Scale**
- 5 — Senior+. Would lead a project like this.
- 4 — Solid mid-senior. Would own a project like this.
- 3 — Competent mid. Would contribute strongly with light mentorship.
- 2 — Below bar but coachable.
- 1 — Below bar.

---

## RAG Quality (45%)

### Retrieval (15%)
- Sensible chunking strategy with documented rationale (size, overlap, boundary handling)
- Embedding model choice justified
- Retrieval works for paraphrased queries, not just verbatim
- Reranking, hybrid search, or other improvements considered (or explicitly traded off)

### Answer quality (15%)
- Answers are grounded in retrieved context
- Citations match what was actually used (not just the top retrieval)
- No hallucination on out-of-corpus queries
- Handles ambiguous questions (asks back or qualifies appropriately)

### Evaluation rigor (15%)
- Extended the eval set meaningfully beyond the starter
- Added cases that probe known weak spots (synthesis, adversarial, edge cases)
- Discussed metric limitations (LLM-as-judge bias, etc.)
- Has a stated quality bar and shows the system meets it
- Eval results are reproducible

---

## Production Readiness (30%)

### Operability (20%)
- Working health checks
- Logging that would help debug a real incident
- Some form of metrics or tracing (App Insights, OTEL, etc.)
- Reasonable error handling on the API surface
- Configurable via env without code changes
- Resources sensibly named and tagged

### Security (10%)
- No keys in repo or commit history (`.env` gitignored is fine for local dev)
- OpenAI key not baked into the image — passed at deploy time as an env var or Container Apps secret
- API not wide open without rate limiting if exposed publicly (or intentionally internal)

---

## Code Quality (15%)

- Sensible structure, not one big file
- Type hints, and they're meaningful
- Tests exist and test something useful
- Docstrings where they help, not where they're noise
- No dead code, commented-out blocks, or obvious un-integrated AI copy-paste
- Dependencies pinned

---

## Prompt Collaboration (10%)

**Reading `PROMPTS.md` and the raw transcripts in `./chats/`, look for:**
- Decomposition — broke big tasks into smaller asks rather than "build me a RAG"
- Iteration — refined when output was wrong rather than accepting and patching
- Skepticism — verified AI claims, especially about Azure APIs and library behavior
- Architecture-level prompts, not just code completion
- Honest about what was AI-generated vs hand-written — the curated `PROMPTS.md` should match what the raw transcripts actually show

**Red flags:**
- Missing or suspiciously thin `./chats/` directory — if every meaningful decision is allegedly hand-thought, check git history for AI-shaped commit bursts
- `PROMPTS.md` narrative diverges materially from what the raw transcripts show
- Suspiciously polished log written all at once (check commit timestamps on `PROMPTS.md`)
- No iteration shown — every prompt got a perfect answer
- Heavy reliance on AI for things they should know cold
- AI hallucinations made it into the code (wrong API signatures, fabricated package names)

---

## Walkthrough notes

After the live walkthrough, capture:
- Could they explain *why*, not just *what*?
- How did they respond to the "break your system" challenge?
- What did they say they'd do next, and was it the right next thing?
- Communication quality — could they explain to a non-engineer?

---

## Final write-up

Score per section, compute weighted total, then add:

- **Strongest signal:** one paragraph
- **Biggest concern:** one paragraph
- **Recommendation:** strong hire / hire / no hire / strong no hire
- **Calibration note:** what would change your mind?
