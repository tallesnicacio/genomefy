from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import Gene
from .retrieval import GenomeRetriever, terms
from .store import GenomeStore, stable_json, utc_now
from .tokens import get_counter


PRIMARY_GATES = {
    "token_savings": 0.25,
    "quality_margin": -0.02,
    "citation_accuracy": 0.95,
    "minimum_questions_for_pass": 30,
}
STAGE2_GATES = {
    **PRIMARY_GATES,
    "category_quality_margin": -0.10,
    "deterministic_stability": 1.0,
}


@dataclass(slots=True)
class MethodResult:
    ids: list[str]
    context: str
    tokens: int
    citations_valid: int
    elapsed_ms: float


def _file_sha256(path: Path) -> str:
    data = path.read_bytes()
    # Git may materialize text fixtures with LF or CRLF depending on platform.
    # Stage 2 was originally locked from a CRLF checkout, so canonicalizing to
    # CRLF preserves its published digest while making verification portable.
    canonical = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(canonical).hexdigest()


def _valid_gene_citation(gene: Gene, sources: dict[str, dict[str, Any]]) -> bool:
    source = sources.get(gene.source_id)
    return bool(
        source
        and gene.source_location
        and len(str(source.get("content_hash", ""))) == 64
        and int(source.get("version", 0)) >= 1
    )


def _full_context(store: GenomeStore) -> MethodResult:
    started = time.perf_counter()
    counter = get_counter()
    genes = store.all_genes()
    sources = store.sources()
    context = "\n\n".join(GenomeRetriever._render_gene(gene) for gene in genes)
    return MethodResult(
        [gene.id for gene in genes], context, counter.count(context),
        sum(_valid_gene_citation(gene, sources) for gene in genes),
        (time.perf_counter() - started) * 1000,
    )


def _lexical(store: GenomeStore, query: str, budget: int) -> MethodResult:
    started = time.perf_counter()
    counter = get_counter()
    q = terms(query)
    ranked: list[tuple[float, Gene]] = []
    for gene in store.all_genes():
        body = terms(f"{gene.label} {gene.summary} {gene.content}")
        score = len(q & body) / max(1, len(q | body))
        if score:
            ranked.append((score, gene))
    chosen: list[Gene] = []
    for _, gene in sorted(ranked, key=lambda item: (-item[0], item[1].id)):
        tentative = chosen + [gene]
        candidate_context = "\n\n".join(GenomeRetriever._render_gene(item) for item in tentative)
        if counter.count(candidate_context) <= budget:
            chosen.append(gene)
    sources = store.sources()
    context = "\n\n".join(GenomeRetriever._render_gene(gene) for gene in chosen)
    return MethodResult(
        [gene.id for gene in chosen], context, counter.count(context),
        sum(_valid_gene_citation(gene, sources) for gene in chosen),
        (time.perf_counter() - started) * 1000,
    )


def _retrieved(store: GenomeStore, query: str, budget: int, **features: bool) -> MethodResult:
    started = time.perf_counter()
    result = GenomeRetriever(store).query(query, budget=budget, **features)
    ids = [item["gene_id"] for item in result.selected]
    sources = store.sources()
    valid = 0
    for item in result.selected:
        citation = item["citation"]
        source = sources.get(citation["source_id"])
        if (
            source
            and citation["source_location"]
            and citation.get("source_hash") == source["content_hash"]
            and citation.get("source_version") == source["version"]
        ):
            valid += 1
    return MethodResult(
        ids, result.context, int(result.metrics["context_tokens"]), valid,
        (time.perf_counter() - started) * 1000,
    )


def _metrics(result: MethodResult, expected: set[str]) -> dict[str, float | int]:
    selected = set(result.ids)
    hits = len(selected & expected)
    recall = hits / len(expected) if expected else 1.0
    precision = hits / len(selected) if selected else (1.0 if not expected else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rr = next((1.0 / rank for rank, item in enumerate(result.ids, 1) if item in expected), 0.0)
    dcg = sum((1.0 if item in expected else 0.0) / math.log2(rank + 1) for rank, item in enumerate(result.ids, 1))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(expected), len(result.ids)) + 1))
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "mrr": rr,
        "ndcg": dcg / ideal if ideal else (1.0 if not expected else 0.0),
        "answer_key_fact_coverage": recall,
        "citation_accuracy": result.citations_valid / len(result.ids) if result.ids else 1.0,
        "context_tokens": result.tokens,
        "context_chars": len(result.context),
        "context_bytes": len(result.context.encode("utf-8")),
        "selected": len(result.ids),
        "latency_ms": result.elapsed_ms,
    }


def _bootstrap(deltas: list[float], iterations: int = 10_000, seed: int = 20260718) -> dict[str, float]:
    if not deltas:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "iterations": iterations}
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(iterations))
    return {
        "mean": statistics.fmean(deltas),
        "ci95_low": means[int(iterations * 0.025)],
        "ci95_high": means[min(iterations - 1, int(iterations * 0.975))],
        "iterations": iterations,
    }


def validate_suite(store: GenomeStore, suite_path: str | Path, suite: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(suite_path).resolve()
    data = suite or json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("benchmark suite must contain a non-empty questions list")

    ids = [str(question.get("id", "")) for question in questions]
    queries = [str(question.get("query", "")) for question in questions]
    if any(not value for value in ids + queries):
        raise ValueError("every benchmark question requires a non-empty id and query")
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark question ids must be unique")
    if len(queries) != len(set(queries)):
        raise ValueError("benchmark queries must be unique; stability uses explicit repetitions")
    expected_count = int(data.get("expected_questions", len(questions)))
    if len(questions) != expected_count:
        raise ValueError(f"suite expected {expected_count} questions but contains {len(questions)}")

    known_genes = {gene.id for gene in store.all_genes()}
    missing: dict[str, list[str]] = {}
    for question in questions:
        expected = [str(gene_id) for gene_id in question.get("expected_gene_ids", [])]
        if not expected:
            raise ValueError(f"question {question['id']} has no expected_gene_ids")
        unknown = sorted(set(expected) - known_genes)
        if unknown:
            missing[str(question["id"])] = unknown
    if missing:
        raise ValueError(f"suite references genes absent from the store: {missing}")

    observed_categories = dict(sorted(Counter(str(question.get("category", "uncategorized")) for question in questions).items()))
    declared_categories = data.get("category_counts")
    if declared_categories and observed_categories != declared_categories:
        raise ValueError(f"category counts do not match: declared={declared_categories}, observed={observed_categories}")

    corpus_path: Path | None = None
    corpus_hash: str | None = None
    if data.get("corpus_file"):
        corpus_path = (path.parent / str(data["corpus_file"])).resolve()
        if path.parent not in corpus_path.parents:
            raise ValueError("corpus_file escapes the suite directory")
        if not corpus_path.is_file():
            raise ValueError(f"declared corpus file does not exist: {corpus_path}")
        corpus_hash = _file_sha256(corpus_path)
        if corpus_hash != data.get("corpus_sha256"):
            raise ValueError("corpus SHA-256 does not match the locked suite")

    locked_gates = data.get("locked_gates")
    if locked_gates and locked_gates != STAGE2_GATES:
        raise ValueError(f"stage-2 gates differ from the frozen protocol: {locked_gates}")

    stability = data.get("stability", {})
    stability_ids = [str(item) for item in stability.get("question_ids", [])]
    unknown_stability = sorted(set(stability_ids) - set(ids))
    if unknown_stability:
        raise ValueError(f"unknown stability question ids: {unknown_stability}")
    if stability_ids and int(stability.get("repetitions", 0)) < 2:
        raise ValueError("stability repetitions must be at least 2")

    return {
        "suite_path": str(path),
        "suite_sha256": _file_sha256(path),
        "corpus_path": str(corpus_path) if corpus_path else None,
        "corpus_sha256": corpus_hash,
        "question_ids_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
        "expected_gene_ids_sha256": hashlib.sha256(
            stable_json({question["id"]: sorted(question["expected_gene_ids"]) for question in questions}).encode("utf-8")
        ).hexdigest(),
        "categories": observed_categories,
        "locked_gates": locked_gates or PRIMARY_GATES,
    }


def _summarize(rows: list[dict[str, Any]], methods: list[str]) -> dict[str, dict[str, float]]:
    keys = (
        "recall", "precision", "f1", "mrr", "ndcg", "answer_key_fact_coverage",
        "citation_accuracy", "context_tokens", "context_chars", "context_bytes", "latency_ms",
    )
    summaries: dict[str, dict[str, float]] = {}
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        summaries[method] = {key: statistics.fmean(float(row[key]) for row in subset) for key in keys}
    return summaries


def _stability_report(
    store: GenomeStore,
    questions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    ids = [str(item) for item in config.get("question_ids", [])]
    if not ids:
        return {"configured": False, "score": 1.0, "questions": 0, "repetitions": 0, "details": []}
    repetitions = int(config["repetitions"])
    by_id = {str(question["id"]): question for question in questions}
    details: list[dict[str, Any]] = []
    for question_id in ids:
        question = by_id[question_id]
        signatures: list[str] = []
        for _ in range(repetitions):
            result = _retrieved(store, question["query"], int(question.get("budget", 600)))
            signatures.append(hashlib.sha256(stable_json({
                "ids": result.ids, "context": result.context, "tokens": result.tokens,
            }).encode("utf-8")).hexdigest())
        details.append({
            "question_id": question_id,
            "stable": len(set(signatures)) == 1,
            "unique_signatures": len(set(signatures)),
        })
    score = sum(bool(item["stable"]) for item in details) / len(details)
    return {
        "configured": True,
        "score": score,
        "questions": len(details),
        "repetitions": repetitions,
        "details": details,
    }


def run_benchmark(store: GenomeStore, suite_path: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    suite_file = Path(suite_path)
    suite = json.loads(suite_file.read_text(encoding="utf-8"))
    integrity = validate_suite(store, suite_file, suite)
    questions = suite["questions"]
    methods: dict[str, Callable[[str, int], MethodResult]] = {
        "full_context": lambda query, budget: _full_context(store),
        "local_rag": lambda query, budget: _lexical(store, query, budget),
        "graph_baseline": lambda query, budget: _retrieved(store, query, budget, use_graph=True, use_epigenetics=False, use_repressors=False, use_splicing=False),
        "genomefy": lambda query, budget: _retrieved(store, query, budget),
        "ablation_no_epigenetics": lambda query, budget: _retrieved(store, query, budget, use_epigenetics=False),
        "ablation_no_repressors": lambda query, budget: _retrieved(store, query, budget, use_repressors=False),
        "ablation_no_splicing": lambda query, budget: _retrieved(store, query, budget, use_splicing=False),
        "ablation_promoters_only": lambda query, budget: _retrieved(store, query, budget, use_graph=False, use_epigenetics=False, use_repressors=False, use_splicing=False),
    }
    method_names = list(methods)
    rows: list[dict[str, Any]] = []
    for question in questions:
        expected = set(question["expected_gene_ids"])
        budget = int(question.get("budget", suite.get("budget", 600)))
        for method, runner in methods.items():
            result = runner(question["query"], budget)
            rows.append({
                "question_id": question["id"],
                "category": question.get("category", "uncategorized"),
                "method": method,
                "budget": budget,
                **_metrics(result, expected),
            })

    summaries = _summarize(rows, method_names)
    categories = sorted({str(question.get("category", "uncategorized")) for question in questions})
    category_summaries = {
        category: _summarize([row for row in rows if row["category"] == category], method_names)
        for category in categories
    }

    baselines = ["full_context", "local_rag", "graph_baseline"]
    comparator = sorted(
        baselines,
        key=lambda name: (-summaries[name]["answer_key_fact_coverage"], summaries[name]["context_tokens"], name),
    )[0]
    genome = summaries["genomefy"]
    base = summaries[comparator]
    savings = 1.0 - genome["context_tokens"] / base["context_tokens"] if base["context_tokens"] else 0.0
    quality_delta = genome["answer_key_fact_coverage"] - base["answer_key_fact_coverage"]
    category_deltas = {
        category: category_summaries[category]["genomefy"]["answer_key_fact_coverage"]
        - category_summaries[category][comparator]["answer_key_fact_coverage"]
        for category in categories
    }
    worst_category_delta = min(category_deltas.values()) if category_deltas else 0.0
    stability = _stability_report(store, questions, suite.get("stability", {}))
    thresholds = suite.get("locked_gates") or PRIMARY_GATES
    gates = {
        "token_savings_at_least_25pct": savings >= float(thresholds["token_savings"]),
        "quality_noninferior_within_2pp": quality_delta >= float(thresholds["quality_margin"]),
        "citation_accuracy_at_least_95pct": genome["citation_accuracy"] >= float(thresholds["citation_accuracy"]),
    }
    if "category_quality_margin" in thresholds:
        gates["no_category_regression_beyond_10pp"] = worst_category_delta >= float(thresholds["category_quality_margin"])
    if "deterministic_stability" in thresholds:
        gates["deterministic_stability_100pct"] = stability["score"] >= float(thresholds["deterministic_stability"])

    outcome = "PASS" if all(gates.values()) else "FAIL"
    if len(questions) < int(thresholds["minimum_questions_for_pass"]):
        outcome = "INCONCLUSIVE" if all(gates.values()) else "FAIL"

    quality_deltas: list[float] = []
    token_deltas: list[float] = []
    for question in questions:
        question_id = question["id"]
        grow = next(row for row in rows if row["question_id"] == question_id and row["method"] == "genomefy")
        brow = next(row for row in rows if row["question_id"] == question_id and row["method"] == comparator)
        quality_deltas.append(float(grow["answer_key_fact_coverage"]) - float(brow["answer_key_fact_coverage"]))
        token_deltas.append(float(brow["context_tokens"]) - float(grow["context_tokens"]))

    report = {
        "schema": "genomefy-benchmark-report-v2",
        "created_at": utc_now(),
        "suite": suite.get("name", suite_file.stem),
        "evaluation_scope": suite.get("evaluation_scope", "retrieval-only"),
        "questions": len(questions),
        "token_counter": get_counter().name,
        "comparator": comparator,
        "dataset_integrity": integrity,
        "thresholds": thresholds,
        "observed": {
            "token_savings": savings,
            "quality_delta": quality_delta,
            "citation_accuracy": genome["citation_accuracy"],
            "worst_category_quality_delta": worst_category_delta,
            "deterministic_stability": stability["score"],
        },
        "gates": gates,
        "outcome": outcome,
        "summaries": summaries,
        "category_summaries": category_summaries,
        "category_quality_deltas": category_deltas,
        "stability": stability,
        "paired_bootstrap": {
            "quality_delta": _bootstrap(quality_deltas),
            "tokens_saved": _bootstrap(token_deltas),
        },
        "rows": rows,
        "notes": [
            "This is a controlled retrieval evaluation, not end-to-end generated-answer scoring.",
            "The corpus is fictional and deterministic so it can be published without private-project leakage.",
            "Citation accuracy checks referential integrity (source id, location, version and hash), not semantic truth.",
            "graph_baseline is a local deterministic graph retrieval baseline, not an official Graphify execution.",
            "PASS is withheld for suites below the frozen minimum question count.",
        ],
    }
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def compare_reports(left: str | Path, right: str | Path) -> dict[str, Any]:
    a = json.loads(Path(left).read_text(encoding="utf-8"))
    b = json.loads(Path(right).read_text(encoding="utf-8"))
    keys = ("token_savings", "quality_delta", "citation_accuracy")
    return {
        "left": str(left),
        "right": str(right),
        "delta": {key: float(b["observed"][key]) - float(a["observed"][key]) for key in keys},
        "outcome_change": f"{a['outcome']} -> {b['outcome']}",
    }
