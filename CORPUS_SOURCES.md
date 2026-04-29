# Corpus Sources

The HR policy documents in `./corpus/` are sourced from two real, publicly published company handbooks. They describe **two different fictional employers' policies**, intentionally — that's part of the test. Some topics (e.g. sick leave, time off) appear in both sources with different rules. A good RAG should ground its answers in the cited document and surface the disagreement when relevant rather than collapsing both into a single fictional policy.

## Sources

### OpenGov Foundation HR Manual — 19 markdown + 3 PDFs (22 files total)

A small US nonprofit's policy manual. Formal, legalistic register; US-flavored (Federal holidays, FMLA references, Google Suite tooling, $-denominated). Originally one monolithic `manual.md`; split here on H3 headings into per-policy files. Two of those split files (`harassment-policy`, `expense-reimbursement-policy`) were converted from `.md` to `.pdf` via `pandoc --pdf-engine=typst` for format variety. The upstream consolidated PDF is also included as `opengov-handbook-consolidated.pdf`.

- **Upstream:** <https://github.com/opengovfoundation/hr-manual>
- **License:** [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) (public domain — no attribution required, but provided here)
- **Files (kebab-cased from H3 headings):** `about-and-values.md`, `equal-employment-policy.md`, `harassment-policy.pdf`, `reporting-violations-policy.md`, `drug-and-alcohol-policy.md`, `conflict-of-interest-policy.md`, `professional-conduct-policy.md`, `media-contact-policy.md`, `payroll-policy.md`, `health-insurance-coverage.md`, `performance-assessments.md`, `raises-and-bonuses.md`, `expense-reimbursement-policy.pdf`, `professional-development-policy.md`, `work-schedule-policy.md`, `vacation-and-leave-policy.md`, `sick-leave-policy.md`, `email-and-password-policy.md`, `calendar-policy.md`, `meetings-policy.md`, `tools-and-services.md`, `opengov-handbook-consolidated.pdf`

### Made Tech handbook — 5 markdown + 5 PDFs (10 files total)

A UK technology consultancy's open-source company handbook. Conversational, modern register; UK-flavored (statutory pay, GBP-denominated, references to gov.uk, NHS-adjacent benefits). Files were copied as-is from the upstream repo and renamed to kebab-case for consistency. Five of the longer files were converted to PDF (`parental-leave`, `holiday`, `hybrid-working`, `whistleblowing`, `equipment-and-work-ready-budget`) via `pandoc --pdf-engine=typst`.

- **Upstream:** <https://github.com/madetech/handbook>
- **License:** Not declared in the upstream repo. The repo is public and self-describes as "the Made Tech open source company handbook." Used here for an internal interview corpus only — not redistributed.
- **Files:** `parental-leave-policy.pdf`, `holiday-policy.pdf`, `hybrid-working-policy.pdf`, `flexible-working-policy.md`, `sick-leave-procedures.md`, `leave-types-overview.md`, `raising-an-issue.md`, `whistleblowing-policy.md`, `pension-scheme.md`, `equipment-and-work-ready-budget.pdf`

## Format mix

24 markdown + 8 PDFs at the time of writing — intentional, so the candidate has to handle both extraction paths. The PDFs were generated via `pandoc … --pdf-engine=typst`, except for `opengov-handbook-consolidated.pdf` which is the upstream original.

## Known quirks (left in deliberately)

- **Internal markdown links may be broken.** Made Tech files reference siblings like `paid_counselling.md` that aren't in this corpus. Real handbooks have broken links; this is realistic noise.
- **Two sources mean two answers for some questions** — e.g. sick leave and time off are described differently in `sick-leave-policy.md` (OpenGov) vs `sick-leave-procedures.md` (Made Tech). The eval cases are designed around this.
- **Some files are very short** (a few hundred bytes) and some are several kilobytes. Chunking strategies that assume uniform document size will struggle.
