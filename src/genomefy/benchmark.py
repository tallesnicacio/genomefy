from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import Gene
from .retrieval import GenomeRetriever, terms
from .store import GenomeStore, stable_json, utc_now
from .tokens import get_counter


@dataclass(slots=True)
class MethodResult:
    ids: list[str]
    context: str
    tokens: int
    citations_valid: int


def _full_context(store: GenomeStore) -> MethodResult:
    counter = get_counter()
    genes = store.all_genes()
    context = "\n\n".join(GenomeRetriever._render_gene(gene) for gene in genes)
    return MethodResult([gene.id for gene in genes], context, counter.count(context), len(genes))


def _lexical(store: GenomeStore, query: str, budget: int) -> MethodResult:
    counter = get_counter()
    q = terms(query)
    ranked: list[tuple[float, Gene]] = []
    for gene in store.all_genes():
        body = terms(f"{gene.label} {gene.summary} {gene.content}")
        score = len(q & body) / max(1, len(q | body))
        if score:
            ranked.append((score, gene))
    chosen: list[Gene] = []
    used = 0
    for _, gene in sorted(ranked, key=lambda item: (-item[0], item[1].id)):
        rendered = GenomeRetriever._render_gene(gene)
        cost = counter.count(rendered)
        if used + cost <= budget:
            chosen.append(gene); used += cost
    context = "\n\n".join(GenomeRetriever._render_gene(gene) for gene in chosen)
    return MethodResult([gene.id for gene in chosen], context, counter.count(context), len(chosen))


def _retrieved(store: GenomeStore, query: str, budget: int, **features: bool) -> MethodResult:
    result = GenomeRetriever(store).query(query, budget=budget, **features)
    ids = [item["gene_id"] for item in result.selected]
    valid = sum(1 for item in result.selected if item["citation"]["source_id"] and item["citation"]["source_location"])
    return MethodResult(ids, result.context, int(result.metrics["context_tokens"]), valid)


def _metrics(result: MethodResult, expected: set[str]) -> dict[str, float | int]:
    selected = set(result.ids)
    hits = len(selected & expected)
    recall = hits / len(expected) if expected else 1.0
    precision = hits / len(selected) if selected else (1.0 if not expected else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rr = next((1.0 / rank for rank, item in enumerate(result.ids, 1) if item in expected), 0.0)
    dcg = sum((1.0 if item in expected else 0.0) / __import__("math").log2(rank + 1) for rank, item in enumerate(result.ids, 1))
    ideal = sum(1.0 / __import__("math").log2(rank + 1) for rank in range(1, min(len(expected), len(result.ids)) + 1))
    return {
        "recall": recall, "precision": precision, "f1": f1, "mrr": rr,
        "ndcg": dcg / ideal if ideal else (1.0 if not expected else 0.0),
        "answer_key_fact_coverage": recall,
        "citation_accuracy": result.citations_valid / len(result.ids) if result.ids else 1.0,
        "context_tokens": result.tokens, "selected": len(result.ids),
    }


def _bootstrap(deltas: list[float], iterations: int = 10_000, seed: int = 20260718) -> dict[str, float]:
    if not deltas:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "iterations": iterations}
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(iterations))
    return {
        "mean": statistics.fmean(deltas), "ci95_low": means[int(iterations * 0.025)],
        "ci95_high": means[min(iterations - 1, int(iterations * 0.975))], "iterations": iterations,
    }


def run_benchmark(store: GenomeStore, suite_path: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
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
    rows: list[dict[str, Any]] = []
    for question in questions:
        expected = set(question["expected_gene_ids"])
        budget = int(question.get("budget", suite.get("budget", 600)))
        for method, runner in methods.items():
            result = runner(question["query"], budget)
            rows.append({"question_id": question["id"], "method": method, **_metrics(result, expected)})

    summaries: dict[str, dict[str, float]] = {}
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        keys = ("recall", "precision", "f1", "mrr", "ndcg", "answer_key_fact_coverage", "citation_accuracy", "context_tokens")
        summaries[method] = {key: statistics.fmean(float(row[key]) for row in subset) for key in keys}

    baselines = ["full_context", "local_rag", "graph_baseline"]
    comparator = sorted(
        baselines,
        key=lambda name: (-summaries[name]["answer_key_fact_coverage"], summaries[name]["context_tokens"], name),
    )[0]
    genome = summaries["genomefy"]
    base = summaries[comparator]
    savings = 1.0 - genome["context_tokens"] / base["context_tokens"] if base["context_tokens"] else 0.0
    quality_delta = genome["answer_key_fact_coverage"] - base["answer_key_fact_coverage"]
    gates = {
        "token_savings_at_least_25pct": savings >= 0.25,
        "quality_noninferior_within_2pp": quality_delta >= -0.02,
        "citation_accuracy_at_least_95pct": genome["citation_accuracy"] >= 0.95,
    }
    outcome = "PASS" if all(gates.values()) else "FAIL"
    if len(questions) < 30:
        outcome = "INCONCLUSIVE" if all(gates.values()) else "FAIL"
    quality_deltas = []
    token_deltas = []
    for question in questions:
        gid = question["id"]
        grow = next(row for row in rows if row["question_id"] == gid and row["method"] == "genomefy")
        brow = next(row for row in rows if row["question_id"] == gid and row["method"] == comparator)
        quality_deltas.append(float(grow["answer_key_fact_coverage"]) - float(brow["answer_key_fact_coverage"]))
        token_deltas.append(float(brow["context_tokens"]) - float(grow["context_tokens"]))
    report = {
        "schema": "genomefy-benchmark-v1", "created_at": utc_now(), "suite": suite.get("name", Path(suite_path).stem),
        "questions": len(questions), "token_counter": get_counter().name, "comparator": comparator,
        "thresholds": {"token_savings": 0.25, "quality_margin": -0.02, "citation_accuracy": 0.95, "minimum_questions_for_pass": 30},
        "observed": {"token_savings": savings, "quality_delta": quality_delta, "citation_accuracy": genome["citation_accuracy"]},
        "gates": gates, "outcome": outcome, "summaries": summaries,
        "paired_bootstrap": {"quality_delta": _bootstrap(quality_deltas), "tokens_saved": _bootstrap(token_deltas)},
        "rows": rows,
        "notes": [
            "graph_baseline is a local deterministic graph retrieval baseline, not an official Graphify execution.",
            "PASS is withheld for suites with fewer than 30 questions.",
        ],
    }
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def compare_reports(left: str | Path, right: str | Path) -> dict[str, Any]:
    a = json.loads(Path(left).read_text(encoding="utf-8"))
    b = json.loads(Path(right).read_text(encoding="utf-8"))
    keys = ("token_savings", "quality_delta", "citation_accuracy")
    return {
        "left": str(left), "right": str(right),
        "delta": {key: float(b["observed"][key]) - float(a["observed"][key]) for key in keys},
        "outcome_change": f"{a['outcome']} -> {b['outcome']}",
    }
