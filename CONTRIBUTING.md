# Contributing to Genomefy

Genomefy is experimental. Contributions are most useful when they improve a measurable retrieval, integrity or usability outcome.

## Development setup

```bash
git clone https://github.com/tallesnicacio/genomefy.git
cd genomefy
python -m pip install -e .
python -m unittest discover -s tests -v
```

The core intentionally has no required third-party runtime dependency. Keep optional integrations behind extras and preserve a zero-dependency local path.

## Pull requests

- Explain the user-visible behavior and the failure mode addressed.
- Add or update tests for retrieval, audit integrity, replay or adapters.
- Do not weaken benchmark gates to make a result pass.
- Label approximations honestly. A local graph baseline is not an official Graphify run.
- Do not add private corpora, credentials, generated `.genomefy` stores or benchmark data without a compatible license and recorded provenance.

Run before opening a PR:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src skills/genomefy/scripts
```

## Commit style

Use concise conventional subjects where practical: `feat:`, `fix:`, `docs:`, `test:` or `chore:`.
