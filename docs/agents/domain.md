# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.
- **`docs/research/`**: read research documents for empirical hardware and system evaluations backing architectural decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo (most repos):

```
/
├── CONTEXT.md
├── docs/
│   ├── adr/
│   │   ├── 0001-distrobox-first-development-environment.md
│   │   └── 0002-flavor-tagged-container-images.md
│   └── research/
│       ├── zot-config-retention.md
│       └── validity-fingerprint-support.md
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_

## Workflow: Adding Documentation (Research, ADRs, Domain Docs)

Every document added or modified in the repository—including Architecture Decision Records (ADRs), Research investigations, and Domain glossaries (`CONTEXT.md`)—**must be submitted via a GitHub Pull Request** targeting `main`.

**Never commit documentation directly to `main`.**

### Document Types & Placement

1. **Architecture Decision Records (`docs/adr/`)**:
   - Numbered sequentially: `NNNN-<slug>.md` (e.g. `docs/adr/0004-hp-zbook-hardware-enablement.md`).
   - Captures hard-to-reverse architectural choices, context, trade-offs, and consequences.
2. **Research Documents (`docs/research/`)**:
   - Named by topic: `<slug>.md` (e.g. `docs/research/validity-fingerprint-support.md`).
   - Captures deep empirical investigations, primary source citations, hardware testing matrices, and feasibility verdicts backing future ADRs or recipe changes.
3. **Domain Vocabulary (`CONTEXT.md`)**:
   - Root-level glossary defining ubiquitous system terms and explicit anti-patterns (`Avoid:`).

### Pull Request Submission Process

1. **Create a Dedicated Branch**:
   - `docs/adr-<slug>` for new ADRs
   - `research/<topic>` or `docs/research-<slug>` for research investigations
   - `docs/<topic>` for general domain doc updates
2. **Author the Document**:
   - Adhere strictly to the repo's domain language from `CONTEXT.md`.
   - Cite high-trust primary sources for research.
3. **Commit with Semantic Messages**:
   - `docs(adr): add NNNN-<slug>`
   - `docs(research): add <slug> investigation report`
   - `docs(domain): update CONTEXT.md glossary`
4. **Open a GitHub Pull Request**:
   - Use `gh pr create --title "..." --body "..."` targeting `main`.
   - Format the PR body using the standard PR structure (Summary, Evidence, Merge Danger).
5. **Review & Merge**:
   - Documentation is only canonical once the PR has been reviewed and merged into `main`.

