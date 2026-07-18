# Changelog

All notable changes to Genomefy are documented here.

## 0.2.0 — 2026-07-18

### Added

- deterministic facet decomposition with auditable core terms;
- coverage-aware context selection under the existing hard token budget;
- temporal allele selection by locus and validity metadata;
- bounded multipath graph-score accumulation;
- Stage 2 corpus, 60-question suite, stability checks and paired bootstrap reporting;
- full original and post-fix benchmark artifacts.

### Changed

- FTS input now normalizes punctuation and hyphenated terms safely;
- candidate recall includes deterministic lightweight morphology;
- candidates that directly cover a facet core survive the expression threshold;
- query transcripts expose facets, temporal mode, term matches and coverage gains;
- the optional tokenizer falls back cleanly when its encoding cache is offline.

### Evidence

- the frozen first Stage 2 run remains `FAIL` at 95.83% key-fact coverage;
- the known-suite post-fix regression reaches `PASS`, 100% coverage, 92.50% context-token reduction, 100% citation integrity and 100% deterministic stability;
- the post-fix result is regression evidence, not independent confirmation on an unseen suite.
