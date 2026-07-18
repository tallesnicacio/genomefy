from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .audit import AuditLog
from .models import Candidate, Gene, QueryResult
from .store import GenomeStore, digest_text, stable_json, utc_now
from .tokens import TokenCounter, get_counter


WORD = re.compile(r"[\w.-]+", re.UNICODE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from", "how", "in",
    "is", "it", "of", "on", "or", "the", "to", "what", "when", "where", "which", "why", "with",
    "a", "ao", "aos", "as", "como", "da", "das", "de", "do", "dos", "e", "é", "em", "na", "nas",
    "no", "nos", "o", "os", "ou", "para", "por", "qual", "quais", "que", "se", "um", "uma",
}
TASK_KINDS = {
    "code": {"code", "function", "class", "module", "symbol"},
    "docs": {"documentation", "section", "knowledge"},
    "decision": {"decision", "requirement", "constraint"},
    "temporal": {"event", "version", "decision"},
}


def terms(text: str) -> set[str]:
    return {token.casefold() for token in WORD.findall(text) if len(token) > 1}


def infer_task(query: str) -> str:
    lowered = query.casefold()
    query_words = terms(lowered)
    if query_words.intersection({"função", "funcoes", "funções", "classe", "código", "codigo", "bug", "function", "class"}):
        return "code"
    if query_words.intersection({"decisão", "decisao", "requisito", "constraint"}) or "por que" in lowered:
        return "decision"
    if query_words.intersection({"quando", "versão", "versao", "antes", "depois", "atual"}):
        return "temporal"
    return "docs"


class GenomeRetriever:
    def __init__(self, store: GenomeStore, counter: TokenCounter | None = None) -> None:
        self.store = store
        self.counter = counter or get_counter()
        self.audit = AuditLog(store)

    def query(
        self,
        query: str,
        *,
        task: str = "auto",
        budget: int = 1200,
        max_hops: int = 2,
        use_graph: bool = True,
        use_epigenetics: bool = True,
        use_repressors: bool = True,
        use_splicing: bool = True,
    ) -> QueryResult:
        if budget < 1:
            raise ValueError("budget must be positive")
        started = utc_now()
        task = infer_task(query) if task == "auto" else task
        positive, negative = self._parse_query(query)
        clean_query = " ".join(positive) or query
        rankings: list[list[Gene]] = []
        exact = self.store.exact(clean_query)
        if exact:
            rankings.append(exact)
        fts = [gene for gene, _ in self.store.fts(clean_query)]
        if fts:
            rankings.append(fts)

        scores: dict[str, float] = defaultdict(float)
        channels: dict[str, list[str]] = defaultdict(list)
        genes: dict[str, Gene] = {}
        for channel_index, ranked in enumerate(rankings):
            channel = "exact" if channel_index == 0 and exact else "fts"
            for rank, gene in enumerate(ranked, 1):
                scores[gene.id] += 1.0 / (60 + rank)
                channels[gene.id].append(channel)
                genes[gene.id] = gene

        if not genes:
            for gene in self._fallback_rank(clean_query, 50):
                scores[gene.id] = max(scores[gene.id], 1.0 / 61)
                channels[gene.id].append("lexical-fallback")
                genes[gene.id] = gene

        if use_graph and genes:
            frontier = list(genes)
            seen = set(frontier)
            for hop in range(1, min(max_hops, 2) + 1):
                next_frontier: list[str] = []
                for source, target, confidence, relation in self.store.neighbors(frontier):
                    anchor = source if source in frontier else target
                    neighbor = target if source in frontier else source
                    if neighbor in seen:
                        continue
                    gene = self.store.get_gene(neighbor)
                    if not gene:
                        continue
                    scores[neighbor] += scores.get(anchor, 1.0 / 61) * confidence * (0.55 ** hop)
                    channels[neighbor].append(f"graph:{relation}:h{hop}")
                    genes[neighbor] = gene
                    seen.add(neighbor)
                    next_frontier.append(neighbor)
                frontier = next_frontier
                if not frontier:
                    break

        marks = self.store.marks() if use_epigenetics else {}
        source_map = self.store.sources()
        preferred = TASK_KINDS.get(task, set())
        query_terms = {token.casefold() for token in positive}
        candidates: list[Candidate] = []
        excluded: list[dict[str, Any]] = []
        for gene_id, gene in genes.items():
            gene_terms = terms(f"{gene.label} {gene.summary} {gene.content}")
            if use_repressors and negative and gene_terms.intersection(negative):
                excluded.append({"gene_id": gene_id, "reason": "repressor matched", "matched": sorted(gene_terms.intersection(negative))})
                continue
            mark = marks.get(gene_id, {})
            if use_repressors and int(mark.get("suppressed", 0)):
                excluded.append({"gene_id": gene_id, "reason": "explicitly suppressed"})
                continue
            score = scores[gene_id] * (0.5 + 0.5 * max(0.0, min(1.0, gene.confidence)))
            reasons = [f"promoter={name}" for name in channels[gene_id]]
            lexical_coverage = len(gene_terms.intersection(query_terms)) / max(1, len(query_terms))
            score *= 0.5 + 0.5 * lexical_coverage
            reasons.append(f"lexical-coverage={lexical_coverage:.3f}")
            source = source_map.get(gene.source_id, {})
            if source:
                is_current = bool(source.get("active", 0))
                score *= 1.03 if is_current else 0.92
                reasons.append("source=current" if is_current else "source=historical")
            if preferred and gene.kind.casefold() in preferred:
                score *= 1.08
                reasons.append(f"task={task}")
            if use_epigenetics and mark:
                boost = float(mark.get("boost", 0.0))
                score *= 1.0 + boost
                reasons.append(f"epigenetic={boost:+.3f}")
            rendered = self._render_gene(gene)
            candidates.append(Candidate(
                gene=gene, score=score, channels=channels[gene_id], reasons=reasons,
                estimated_tokens=self.counter.count(rendered),
            ))

        initial_candidate_count = len(genes)
        if use_splicing and candidates:
            expression_floor = max(candidate.score for candidate in candidates) * 0.70
            expressed: list[Candidate] = []
            for candidate in candidates:
                if candidate.score + 1e-12 >= expression_floor:
                    expressed.append(candidate)
                else:
                    excluded.append({
                        "gene_id": candidate.gene.id, "reason": "expression threshold",
                        "score": round(candidate.score, 10), "threshold": round(expression_floor, 10),
                    })
            candidates = expressed
        selected, selection_excluded = self._select(candidates, budget, use_splicing)
        excluded.extend(selection_excluded)
        context = "\n\n".join(self._render_gene(candidate.gene) for candidate in selected)
        selected_payload = [self._candidate_payload(candidate, index + 1, source_map) for index, candidate in enumerate(selected)]
        used = self.counter.count(context)
        run_id = f"run:{uuid.uuid4().hex}"
        metrics = {
            "context_tokens": used,
            "budget_utilization": used / budget,
            "selected_count": len(selected),
            "excluded_count": len(excluded),
            "candidate_count": initial_candidate_count,
            "expressed_candidate_count": len(candidates),
            "token_counter": self.counter.name,
            "state_hash": self.store.state_hash(),
            "features": {
                "graph": use_graph, "epigenetics": use_epigenetics, "repressors": use_repressors,
                "splicing": use_splicing, "max_hops": min(max_hops, 2),
            },
        }
        transcript = {
            "query": query, "positive_terms": positive, "negative_terms": sorted(negative),
            "selected": selected_payload, "excluded": excluded, "context": context,
        }
        transcript_json = stable_json(transcript)
        metrics_json = stable_json(metrics)
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, query, task, budget, self.counter.name, started, utc_now(), metrics["state_hash"],
                 transcript_json, metrics_json),
            )
        self.audit.append("query.transcribed", run_id=run_id, reason="deterministic retrieval", payload={
            "selected": [item["gene_id"] for item in selected_payload], "budget": budget,
            "transcript_hash": digest_text(transcript_json), "metrics_hash": digest_text(metrics_json),
        })
        return QueryResult(run_id, query, task, budget, context, selected_payload, excluded, metrics)

    @staticmethod
    def _parse_query(query: str) -> tuple[list[str], set[str]]:
        positive: list[str] = []
        negative: set[str] = set()
        for token in WORD.findall(query):
            if token.startswith("-") and len(token) > 1:
                negative.add(token[1:].casefold())
            elif token.casefold() not in STOPWORDS:
                positive.append(token)
        return positive, negative

    def _fallback_rank(self, query: str, limit: int) -> list[Gene]:
        query_terms = terms(query)
        scored = []
        for gene in self.store.all_genes():
            overlap = len(query_terms.intersection(terms(f"{gene.label} {gene.summary} {gene.content}")))
            if overlap:
                scored.append((overlap, gene.id, gene))
        return [gene for _, _, gene in sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]]

    @staticmethod
    def _render_gene(gene: Gene) -> str:
        citation = f"{gene.source_location} | {gene.source_id} | confidence={gene.confidence:.2f}"
        return f"[GENE {gene.id}] {gene.label}\n{gene.content}\n[CITATION {citation}]"

    @staticmethod
    def _jaccard(left: Gene, right: Gene) -> float:
        a = terms(left.content); b = terms(right.content)
        return len(a & b) / len(a | b) if a or b else 0.0

    def _select(self, candidates: list[Candidate], budget: int, use_splicing: bool) -> tuple[list[Candidate], list[dict[str, Any]]]:
        remaining = sorted(candidates, key=lambda item: (-item.score, item.estimated_tokens, item.gene.id))
        selected: list[Candidate] = []
        excluded: list[dict[str, Any]] = []
        while remaining:
            rescored: list[tuple[float, Candidate]] = []
            for candidate in remaining:
                novelty = max((self._jaccard(candidate.gene, chosen.gene) for chosen in selected), default=0.0)
                mmr = candidate.score * (1.0 - 0.25 * novelty) if use_splicing else candidate.score
                rescored.append((mmr, candidate))
            _, chosen = max(rescored, key=lambda item: (item[0], item[1].score, item[1].gene.id))
            remaining.remove(chosen)
            tentative = selected + [chosen]
            exact_cost = self.counter.count("\n\n".join(self._render_gene(item.gene) for item in tentative))
            if exact_cost <= budget:
                chosen.reasons.append("budgeted-splice" if use_splicing else "score-order")
                selected.append(chosen)
            else:
                excluded.append({
                    "gene_id": chosen.gene.id, "reason": "token budget", "estimated_tokens": chosen.estimated_tokens,
                    "would_use_tokens": exact_cost,
                })
        return selected, excluded

    @staticmethod
    def _candidate_payload(candidate: Candidate, rank: int, source_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        gene = candidate.gene
        source = source_map.get(gene.source_id, {})
        return {
            "rank": rank, "gene_id": gene.id, "locus_id": gene.locus_id, "label": gene.label,
            "score": round(candidate.score, 10), "estimated_tokens": candidate.estimated_tokens,
            "citation": {
                "source_id": gene.source_id, "source_location": gene.source_location,
                "source_hash": source.get("content_hash", ""), "source_version": source.get("version"),
                "source_active": bool(source.get("active", 0)), "confidence": gene.confidence,
            },
            "reasons": candidate.reasons,
        }

    def explain(self, run_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown run: {run_id}")
        return {
            "run_id": run_id, "query": row["query"], "task": row["task"], "budget": row["budget"],
            "token_counter": row["token_counter"], "started_at": row["started_at"], "finished_at": row["finished_at"],
            "state_hash": row["state_hash"], "transcript": json.loads(row["transcript_json"]),
            "metrics": json.loads(row["metrics_json"]),
        }
