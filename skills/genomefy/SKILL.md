---
name: genomefy
description: Retrieve compact, cited, locally stored project context and expose an audit transcript explaining selection, exclusions, token budget, source versions, and explicit-feedback effects. Use for questions about a project whose root contains `.genomefy`, for long-running work that needs durable memory, when the user asks to query/ingest/audit/replay Genomefy, or when comparing context-token efficiency. Works with deterministic docs/JSONL ingestion and optional Graphify graph imports. Do not use as a substitute for reading files when Genomefy is absent or stale.
---

# Genomefy

Use Genomefy as a local context-retrieval layer. Treat biological language as an interface metaphor; report concrete retrieval and audit evidence.

## Query and answer workflow

1. Locate the project root and confirm `.genomefy/genomefy.db` exists. If absent, explain that initialization and ingestion are required.
2. Run `python scripts/genomefy_skill.py --root <project> query "<question>" --budget <n> --json`.
3. Use only the returned `context` as Genomefy evidence. Preserve each selected item's `citation.source_location` in the answer.
4. Answer normally, then append a compact audit summary containing run ID, selected count, context tokens/budget, token-counter name, and material exclusions.
5. Never record feedback based on silence or an inferred reaction. Run `feedback` only when the user explicitly accepts or rejects the result.

If the helper cannot locate the canonical package, tell the user to reinstall the skill. Do not silently fall back while claiming a Genomefy-backed answer.

## Ingestion workflow

Use ingestion only when the user asks to initialize, update, or index memory. Read [references/operations.md](references/operations.md) before mutation.

- Prefer `docs` for Markdown/text and `jsonl` for controlled canonical records.
- Use `graphify` only for an existing Graphify `graph.json`; Genomefy does not require Graphify to be installed.
- Keep each store local to one project.
- Reject sources outside the project root and do not ingest secret/configuration files.

## Audit and measurement

Use `audit <run-id>` to explain a response, `audit verify` for hash-chain integrity, and `benchmark run` for comparative evidence. Never describe a smoke suite as scientific validation. `PASS` requires all gates and at least 30 questions; smaller successful suites are `INCONCLUSIVE`.

Read [references/operations.md](references/operations.md) for exact commands and failure handling.
