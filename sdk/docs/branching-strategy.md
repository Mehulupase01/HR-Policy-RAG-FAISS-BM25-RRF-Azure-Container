# Branching Strategy & Git Workflow

## Branch Model

The repository uses a **two-tier protected branch** model:

```
feature branch  ──PR──▶  dev  ──PR──▶  main
```

| Branch | Purpose | Direct push |
|--------|---------|-------------|
| `main` | Production-ready code | **Never** |
| `dev` | Integration / QA — collects completed features | **Never** |
| `dev - {Monday ticket}` | Active work on a specific ticket | ✅ (developer works here) |

---

## Branch Protection Rules

Configure in **GitHub → Settings → Branches** for both `main` and `dev`.

### `main` protection

| Rule | Value |
|------|-------|
| Require pull request before merging | ✅ |
| Required approvals | 1 (minimum) |
| Dismiss stale reviews on new pushes | ✅ |
| Require status checks to pass | ✅ (`lint`, `test-unit`) |
| Require branches to be up to date | ✅ |
| Restrict who can push to matching branches | ✅ (admins only) |

### `dev` protection

| Rule | Value |
|------|-------|
| Require pull request before merging | ✅ |
| Required approvals | 1 (minimum) |
| Require status checks to pass | ✅ (`lint`, `test-unit`) |
| Require branches to be up to date | ✅ |

---

## Branch Naming

Feature branches are created from `dev` and named after the **Monday ticket**:

```
dev - {Monday ticket name}
```

**Examples:**
- `dev - Exact verbeteren`
- `dev - RAG agent implementatie`
- `dev - File upload validatie`
- `dev - Chat UI redesign`

> **Rule:** The branch name must match the Monday ticket name exactly so anyone
> can see at a glance which ticket is being worked on.

---

## Workflow Step-by-Step

### 1. Start work on a ticket

```bash
# Make sure dev is up to date
git checkout dev
git pull origin dev

# Create a feature branch named after the Monday ticket
git checkout -b "dev - Exact verbeteren"
```

### 2. Develop & commit

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
[optional footer]
```

| Type | When |
|------|------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or correcting tests |
| `chore` | Maintenance (deps, CI, tooling) |

**Scope** = Monday ticket name or component (e.g., `exact`, `blob-client`, `rag-agent`).

**Examples:**
```
feat(exact): implement PDF chunking with overlap
fix(blob-client): handle empty container on first list
docs(README): add local development instructions
chore(deps): bump qdrant-client to 1.10.0
```

### 3. PR → `dev`

```bash
git push origin "dev - Exact verbeteren"
```

1. Open a **Pull Request** from `dev - Exact verbeteren` → `dev`.
2. Fill in the PR template (problem, solution, test evidence).
3. CI checks must pass (lint + unit tests).
4. Get at least **1 approval** from a team member.
5. **Squash-merge** into `dev`.
6. Delete the feature branch.

### 4. PR → `main` (release)

When `dev` is stable and tested:

1. Open a **Pull Request** from `dev` → `main`.
2. Verify all integration tests pass.
3. Get at least **1 approval**.
4. **Merge** (regular merge, not squash — preserves history).
5. Tag the release if needed (see below).

---

## Visual Flow

```
                        ┌──────────────────────────┐
                        │  dev - Exact verbeteren   │
                        │  dev - Chat UI redesign   │
                        │  dev - File upload fix     │
                        └────────────┬─────────────┘
                                     │ PR (squash-merge)
                                     ▼
                              ┌──────────┐
                              │   dev    │  ← integration / QA
                              └─────┬────┘
                                    │ PR (merge)
                                    ▼
                              ┌──────────┐
                              │   main   │  ← production
                              └──────────┘
```

---

## Release Process

For projects that need versioned releases:

1. Merge `dev` → `main` via PR.
2. Create a Git tag: `git tag -a v1.0.0 -m "Release 1.0.0"`.
3. Push the tag: `git push origin v1.0.0`.
4. CI deploys the tagged commit to production.
