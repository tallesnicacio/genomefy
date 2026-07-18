# Security policy

## Supported versions

Genomefy is currently experimental. Security fixes target the latest version on the default branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository when available. Do not open a public issue containing credentials, private corpora, path traversal details that expose a real system, or exploitable audit-chain bypasses.

Include the affected version, reproduction steps, impact and a minimal non-sensitive fixture. You should receive an acknowledgement within seven days.

## Local-data model

Genomefy stores state under `<project>/.genomefy`. Document ingestion is restricted to supported text formats, skips known sensitive paths and rejects paths outside the configured project root. Users remain responsible for reviewing a corpus before ingestion and for protecting the project directory.
