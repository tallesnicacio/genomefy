# Genomefy Stage 2 — post-fix engineering regression

## Result

The facet-aware engine reached 100% key-fact coverage while reducing context tokens by 92.50% against full context. All five frozen gates passed.

This does not replace the original `FAIL` in [`STAGE2_REPORT.md`](STAGE2_REPORT.md). The same suite was inspected while developing the fixes, so the results below are post-hoc regression evidence, not independent confirmation.

## Evolution

| Run | Engine commit | Coverage | Mean context tokens | Token reduction | Worst category delta | Outcome |
|---|---|---:|---:|---:|---:|---|
| Frozen v1 | `9003036` + tokenizer fix | 95.83% | 129.10 | 92.54% | -16.67 pp | `FAIL` |
| Facet-aware | `73f3677` | 98.33% | 121.92 | 92.96% | -8.33 pp | `PASS` |
| Core-facet protection | `22b491b` | 100% | 129.75 | 92.50% | 0.00 pp | `PASS` |

The intermediate run is retained to make the second diagnostic and correction visible rather than presenting only the best result.

## Final frozen-gate comparison

| Gate | Required | Observed | Result |
|---|---:|---:|---|
| Context-token reduction | ≥25% | 92.50% | pass |
| Key-fact coverage delta | ≥-2 pp | 0.00 pp | pass |
| Referential citation integrity | ≥95% | 100% | pass |
| Worst-category coverage delta | ≥-10 pp | 0.00 pp | pass |
| Deterministic stability | 100% | 100% | pass |

All five categories reached 100% mean key-fact coverage. The 10,000-sample paired bootstrap measured a mean saving of 1,601.25 tokens per question, with a 95% interval from 1,589.37 to 1,613.07 tokens. All 12 stability questions produced identical selections, contexts and token counts in three repetitions.

## What changed

- punctuation-safe FTS normalization, including hyphenated terms;
- deterministic lightweight morphological candidate recall;
- query decomposition into auditable facets and core terms;
- coverage-aware, token-bounded selection;
- current-allele selection using locus and temporal metadata;
- graph-score accumulation from multiple bounded paths;
- protection of candidates that directly cover a facet core;
- transcript fields for the query plan, temporal mode, facet matches and coverage gains.

The implementation kept the original hard token budget, deterministic ordering, citation payloads, explicit-feedback rules and hash-chain audit behavior.

## Audit anchors

- first engine commit before its full run: `73f3677`;
- final engine commit before its full run: `22b491b`;
- final execution: 2026-07-18T18:01:29Z;
- token counter: `o200k_base`;
- corpus and suite hashes: unchanged from the frozen v1;
- final audit verification: valid, 1,218 events, zero errors;
- final audit head: `23fdd11328d2bb9ae8ef814e4df7bd7cd9b695b3fca5c996037f6c1b35379785`;
- intermediate report SHA-256: `77a03a6b785181a083d619200e43f9abcd05f6db9ebbe2621b1cadde9ac64c60`;
- final report SHA-256: `104e60a772dc456efe34799e88cf79536e22d15b42dd95a810f867aefdb85e70`.

## Artifacts

- Intermediate full report: [`stage2-postfix-73f3677.json`](stage2-postfix-73f3677.json)
- Final full report: [`stage2-postfix-22b491b.json`](stage2-postfix-22b491b.json)
- Original frozen report: [`stage2-controlled-60-v1.json`](stage2-controlled-60-v1.json)
- Frozen suite: [`../stage2/stage2-suite.json`](../stage2/stage2-suite.json)

The next meaningful validation is a new question set whose expectations and gates are committed before the facet-aware engine is run against it.
