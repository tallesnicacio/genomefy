# Genomefy operations

The helper delegates to the canonical local package and accepts the same CLI arguments.

```powershell
python scripts/genomefy_skill.py --root <project> status
python scripts/genomefy_skill.py --root <project> query "<question>" --budget 1200 --json
python scripts/genomefy_skill.py --root <project> audit <run-id>
python scripts/genomefy_skill.py --root <project> audit verify
```

Mutating operations require explicit user intent:

```powershell
python scripts/genomefy_skill.py --root <project> init
python scripts/genomefy_skill.py --root <project> ingest docs <relative-path>
python scripts/genomefy_skill.py --root <project> ingest graphify <relative-graph.json>
python scripts/genomefy_skill.py --root <project> feedback <run-id> --accepted --reason "explicit reason"
python scripts/genomefy_skill.py --root <project> replay
```

Failure handling:

- Missing `.genomefy`: do not imply there is stored memory; ask to initialize and ingest.
- Stale source: re-ingest only with permission; changed sources become new versions.
- Invalid audit chain: stop using feedback-derived ranking, report the integrity failure, and preserve files for diagnosis.
- `regex-estimate-v1`: call the count an estimate. `o200k_base` may be called a tokenizer count.
- Graphify import: preserve source fields and identify the graph baseline as local unless an official Graphify run actually produced it.
