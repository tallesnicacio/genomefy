from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .audit import AuditLog
from .models import Candidate, Gene, QueryResult
from .store import GenomeStore, digest_text, stable_json, utc_now
from .tokens import TokenCounter, get_counter


WORD = re.compile(r"-?[\w]+(?:[.-][\w]+)*", re.UNICODE)
TERM_WORD = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from", "how", "in",
    "is", "it", "of", "on", "or", "the", "to", "what", "when", "where", "which", "why", "with",
    "a", "ao", "aos", "as", "como", "da", "das", "de", "do", "dos", "e", "é", "em", "na", "nas",
    "no", "nos", "o", "os", "ou", "para", "por", "qual", "quais", "que", "se", "um", "uma",
}
FACET_NOISE = {
    "applies", "back", "behavior", "covers", "describe", "explain", "give", "identify",
    "list", "name", "protect", "state", "summarize", "tell", "using", "use",
    "aplica", "descreva", "diga", "estado", "liste", "nome", "protege", "resuma",
    "current", "currently", "latest", "atual", "atualmente", "vigente",
}
CURRENT_TERMS = {
    "after", "current", "currently", "latest", "now", "replaced",
    "apos", "atual", "atualmente", "substituiu", "vigente",
}
HISTORICAL_TERMS = {
    "before", "deprecated", "former", "historical", "old", "previous", "prior",
    "antes", "antigo", "anterior", "historico", "historica",
}
FACET_SPLIT = re.compile(r"\s+(?:and|e)\s+|[,;]", re.IGNORECASE)
TASK_KINDS = {
    "code": {"code", "function", "class", "module", "symbol"},
    "docs": {"documentation", "section", "knowledge"},
    "decision": {"decision", "requirement", "constraint"},
    "temporal": {"event", "version", "decision"},
}


def term_list(text: str) -> list[str]:
    return list(dict.fromkeys(
        token.casefold() for token in TERM_WORD.findall(text) if len(token) > 1
    ))


def terms(text: str) -> set[str]:
    return set(term_list(text))


def lexical_forms(text: str) -> set[str]:
    """Deterministic light morphology for candidate recall, not linguistic truth."""
    forms: set[str] = set()
    for token in term_list(text):
        forms.add(token)
        if len(token) > 4 and token.endswith("ing"):
            forms.add(token[:-3])
            forms.add(token[:-3] + "e")
        if len(token) > 4 and token.endswith("ed"):
            forms.add(token[:-2])
        if len(token) > 4 and token.endswith("es"):
            forms.add(token[:-1])
            forms.add(token[:-2])
        elif len(token) > 3 and token.endswith("s"):
            forms.add(token[:-1])
        if len(token) > 4 and token.endswith("er"):
            forms.add(token[:-2])
    return {form for form in forms if len(form) > 1}


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
        facets = self._plan_facets(query, positive)
        facet_forms = [lexical_forms(" ".join(facet)) for facet in facets]
        core_forms = [lexical_forms(facet[0]) if facet else set() for facet in facets]
        query_terms = set().union(*facet_forms) if facet_forms else lexical_forms(" ".join(positive))
        scores: dict[str, float] = defaultdict(float)
        channels: dict[str, list[str]] = defaultdict(list)
        genes: dict[str, Gene] = {}
        facet_hits: dict[str, set[int]] = defaultdict(set)
        protected_ids: set[str] = set()
        for facet_id, facet in enumerate(facets):
            facet_query = " ".join(facet)
            facet_scores: dict[str, float] = defaultdict(float)
            rankings = [
                ("exact", self.store.exact(facet_query)),
                ("fts", [gene for gene, _ in self.store.fts(facet_query)]),
                ("morphology", self._fallback_rank(facet_query, 50)),
            ]
            facet_candidates: set[str] = set()
            for channel, ranked in rankings:
                for rank, gene in enumerate(ranked, 1):
                    contribution = 1.0 / (60 + rank)
                    scores[gene.id] += contribution
                    facet_scores[gene.id] += contribution
                    promoter = f"{channel}:facet-{facet_id + 1}"
                    if promoter not in channels[gene.id]:
                        channels[gene.id].append(promoter)
                    genes[gene.id] = gene
                    facet_hits[gene.id].add(facet_id)
                    facet_candidates.add(gene.id)
            protected_ids.update(sorted(
                facet_candidates, key=lambda gene_id: (-facet_scores[gene_id], gene_id)
            )[:2])

        if not genes:
            for gene in self._fallback_rank(" ".join(positive) or query, 50):
                scores[gene.id] = max(scores[gene.id], 1.0 / 61)
                channels[gene.id].append("lexical-fallback")
                genes[gene.id] = gene
                facet_hits[gene.id].add(0)
                protected_ids.add(gene.id)

        if use_graph and genes:
            frontier = set(genes)
            discovered_depth = {gene_id: 0 for gene_id in genes}
            for hop in range(1, min(max_hops, 2) + 1):
                contributions: dict[str, float] = defaultdict(float)
                inherited_facets: dict[str, set[int]] = defaultdict(set)
                next_frontier: set[str] = set()
                frontier_scores = {gene_id: scores.get(gene_id, 1.0 / 61) for gene_id in frontier}
                for source, target, confidence, relation in self.store.neighbors(sorted(frontier)):
                    for anchor, neighbor in ((source, target), (target, source)):
                        if anchor not in frontier or anchor == neighbor:
                            continue
                        gene = genes.get(neighbor) or self.store.get_gene(neighbor)
                        if not gene:
                            continue
                        contributions[neighbor] += frontier_scores[anchor] * confidence * (0.55 ** hop)
                        inherited_facets[neighbor].update(facet_hits.get(anchor, set()))
                        graph_channel = f"graph:{relation}:h{hop}"
                        if graph_channel not in channels[neighbor]:
                            channels[neighbor].append(graph_channel)
                        genes[neighbor] = gene
                        if neighbor not in discovered_depth:
                            discovered_depth[neighbor] = hop
                            next_frontier.add(neighbor)
                for neighbor, contribution in contributions.items():
                    scores[neighbor] += contribution
                    facet_hits[neighbor].update(inherited_facets[neighbor])
                frontier = next_frontier
                if not frontier:
                    break

        temporal_mode = self._temporal_mode(query)
        if temporal_mode == "current":
            all_by_locus: dict[str, list[Gene]] = defaultdict(list)
            for stored_gene in self.store.all_genes():
                all_by_locus[stored_gene.locus_id].append(stored_gene)
            for gene_id, gene in list(genes.items()):
                if self._temporal_state(gene) != "historical":
                    continue
                replacements = [
                    item for item in all_by_locus[gene.locus_id]
                    if self._temporal_state(item) == "current"
                ]
                for replacement in replacements:
                    genes[replacement.id] = replacement
                    scores[replacement.id] += scores[gene_id] * 1.08
                    facet_hits[replacement.id].update(facet_hits.get(gene_id, set()))
                    channel = f"temporal:current-allele:{gene_id}"
                    if channel not in channels[replacement.id]:
                        channels[replacement.id].append(channel)
                    if gene_id in protected_ids:
                        protected_ids.add(replacement.id)

        marks = self.store.marks() if use_epigenetics else {}
        source_map = self.store.sources()
        preferred = TASK_KINDS.get(task, set())
        candidates: list[Candidate] = []
        excluded: list[dict[str, Any]] = []
        for gene_id, gene in genes.items():
            gene_terms = lexical_forms(f"{gene.label} {gene.summary} {gene.content}")
            if use_repressors and negative and gene_terms.intersection(negative):
                excluded.append({"gene_id": gene_id, "reason": "repressor matched", "matched": sorted(gene_terms.intersection(negative))})
                continue
            temporal_state = self._temporal_state(gene)
            if temporal_mode == "current" and temporal_state == "historical":
                excluded.append({
                    "gene_id": gene_id, "reason": "historical allele superseded",
                    "locus_id": gene.locus_id,
                })
                continue
            mark = marks.get(gene_id, {})
            if use_repressors and int(mark.get("suppressed", 0)):
                excluded.append({"gene_id": gene_id, "reason": "explicitly suppressed"})
                continue
            score = scores[gene_id] * (0.5 + 0.5 * max(0.0, min(1.0, gene.confidence)))
            reasons = [f"promoter={name}" for name in channels[gene_id]]
            matched_terms = gene_terms.intersection(query_terms)
            lexical_coverage = len(matched_terms) / max(1, len(query_terms))
            score *= 0.5 + 0.5 * lexical_coverage
            reasons.append(f"lexical-coverage={lexical_coverage:.3f}")
            reasons.append(f"temporal={temporal_state}")
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
                facet_ids=sorted(facet_hits.get(gene_id, set())),
                core_facet_ids=sorted(
                    facet_id for facet_id in facet_hits.get(gene_id, set())
                    if matched_terms.intersection(core_forms[facet_id])
                ),
                matched_terms=sorted(matched_terms), protected=gene_id in protected_ids,
            ))

        initial_candidate_count = len(genes)
        if use_splicing and candidates:
            expression_floor = max(candidate.score for candidate in candidates) * 0.70
            expressed: list[Candidate] = []
            for candidate in candidates:
                protects_intent = candidate.protected or bool(candidate.core_facet_ids)
                if protects_intent or candidate.score + 1e-12 >= expression_floor:
                    if protects_intent and candidate.score + 1e-12 < expression_floor:
                        reason = "core-facet-protected" if candidate.core_facet_ids else "facet-protected"
                        candidate.reasons.append(reason)
                    expressed.append(candidate)
                else:
                    excluded.append({
                        "gene_id": candidate.gene.id, "reason": "expression threshold",
                        "score": round(candidate.score, 10), "threshold": round(expression_floor, 10),
                    })
            candidates = expressed
        selected, selection_excluded = self._select(
            candidates, budget, use_splicing, len(facets), query_terms,
        )
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
            "facet_count": len(facets),
            "covered_facets": len({facet for candidate in selected for facet in candidate.facet_ids}),
            "features": {
                "graph": use_graph, "epigenetics": use_epigenetics, "repressors": use_repressors,
                "splicing": use_splicing, "max_hops": min(max_hops, 2),
            },
        }
        transcript = {
            "query": query, "positive_terms": positive, "negative_terms": sorted(negative),
            "query_plan": {
                "facets": [
                    {"id": index + 1, "terms": facet, "core_terms": sorted(core_forms[index])}
                    for index, facet in enumerate(facets)
                ],
                "temporal_mode": temporal_mode,
            },
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
        for raw_token in WORD.findall(query):
            is_negative = raw_token.startswith("-") and len(raw_token) > 1
            normalized = term_list(raw_token[1:] if is_negative else raw_token)
            for token in normalized:
                if is_negative:
                    negative.update(lexical_forms(token))
                elif token not in STOPWORDS:
                    positive.append(token)
        return positive, negative

    @staticmethod
    def _plan_facets(query: str, positive: list[str]) -> list[list[str]]:
        working = query
        if ":" in working:
            prefix, suffix = working.split(":", 1)
            if terms(prefix).intersection(FACET_NOISE):
                working = suffix
        facets: list[list[str]] = []
        for segment in FACET_SPLIT.split(working):
            facet = [
                token for token in term_list(segment)
                if token not in STOPWORDS and token not in FACET_NOISE
            ]
            if facet and facet not in facets:
                facets.append(facet)
        if not facets:
            fallback = [token for token in positive if token not in FACET_NOISE]
            facets.append(fallback or positive or term_list(query))
        return facets[:8]

    @staticmethod
    def _temporal_mode(query: str) -> str:
        query_terms = terms(query)
        if query_terms.intersection(CURRENT_TERMS):
            return "current"
        if query_terms.intersection(HISTORICAL_TERMS):
            return "historical"
        # Durable project memory should resolve a locus to its current allele
        # unless the user explicitly asks for history.
        return "current"

    @staticmethod
    def _temporal_state(gene: Gene) -> str:
        status = str(gene.metadata.get("status", "")).casefold()
        if status in {"historical", "deprecated", "superseded"}:
            return "historical"
        if status in {"current", "active"}:
            return "current"
        if gene.valid_to:
            try:
                valid_to = datetime.fromisoformat(gene.valid_to.replace("Z", "+00:00"))
                if valid_to.tzinfo is None:
                    valid_to = valid_to.replace(tzinfo=timezone.utc)
                if valid_to <= datetime.now(timezone.utc):
                    return "historical"
            except ValueError:
                return "historical"
        if gene.valid_from and not gene.valid_to:
            return "current"
        return "unknown"

    def _fallback_rank(self, query: str, limit: int) -> list[Gene]:
        query_terms = lexical_forms(query)
        scored = []
        for gene in self.store.all_genes():
            gene_terms = lexical_forms(f"{gene.label} {gene.summary} {gene.content}")
            overlap = len(query_terms.intersection(gene_terms))
            if overlap:
                union = len(query_terms.union(gene_terms))
                scored.append((overlap, overlap / max(1, union), gene.id, gene))
        return [gene for _, _, _, gene in sorted(scored, key=lambda item: (-item[0], -item[1], item[2]))[:limit]]

    @staticmethod
    def _render_gene(gene: Gene) -> str:
        citation = f"{gene.source_location} | {gene.source_id} | confidence={gene.confidence:.2f}"
        return f"[GENE {gene.id}] {gene.label}\n{gene.content}\n[CITATION {citation}]"

    @staticmethod
    def _jaccard(left: Gene, right: Gene) -> float:
        a = terms(left.content); b = terms(right.content)
        return len(a & b) / len(a | b) if a or b else 0.0

    def _select(
        self,
        candidates: list[Candidate],
        budget: int,
        use_splicing: bool,
        facet_count: int,
        query_terms: set[str],
    ) -> tuple[list[Candidate], list[dict[str, Any]]]:
        remaining = sorted(candidates, key=lambda item: (-item.score, item.estimated_tokens, item.gene.id))
        selected: list[Candidate] = []
        excluded: list[dict[str, Any]] = []
        covered_facets: set[int] = set()
        covered_core_facets: set[int] = set()
        covered_terms: set[str] = set()
        document_frequency = Counter(
            term for candidate in candidates for term in set(candidate.matched_terms)
        )
        term_weights = {
            term: math.log((1 + len(candidates)) / (1 + document_frequency[term])) + 1.0
            for term in query_terms
        }
        while remaining:
            rescored: list[tuple[float, float, int, str, Candidate, set[int], set[int], set[str]]] = []
            for candidate in remaining:
                novelty = max((self._jaccard(candidate.gene, chosen.gene) for chosen in selected), default=0.0)
                new_facets = set(candidate.facet_ids) - covered_facets
                new_core_facets = set(candidate.core_facet_ids) - covered_core_facets
                new_terms = set(candidate.matched_terms) - covered_terms
                if use_splicing:
                    relevance = candidate.score * (1.0 - 0.25 * novelty)
                    facet_gain = 0.010 * len(new_facets) / max(1, facet_count)
                    core_gain = 0.018 * len(new_core_facets)
                    lexical_gain = 0.004 * sum(term_weights.get(term, 1.0) for term in new_terms)
                    utility = relevance + facet_gain + core_gain + lexical_gain
                    utility /= 1.0 + 0.15 * candidate.estimated_tokens / max(1, budget)
                else:
                    utility = candidate.score
                rescored.append((
                    utility, candidate.score, candidate.estimated_tokens, candidate.gene.id,
                    candidate, new_facets, new_core_facets, new_terms,
                ))
            _, _, _, _, chosen, new_facets, new_core_facets, new_terms = sorted(
                rescored, key=lambda item: (-item[0], -item[1], item[2], item[3])
            )[0]
            remaining.remove(chosen)
            tentative = selected + [chosen]
            exact_cost = self.counter.count("\n\n".join(self._render_gene(item.gene) for item in tentative))
            if exact_cost <= budget:
                if use_splicing:
                    chosen.reasons.append(
                        "coverage-splice="
                        f"facets:{len(new_facets)},core:{len(new_core_facets)},terms:{len(new_terms)}"
                    )
                else:
                    chosen.reasons.append("score-order")
                selected.append(chosen)
                covered_facets.update(chosen.facet_ids)
                covered_core_facets.update(chosen.core_facet_ids)
                covered_terms.update(chosen.matched_terms)
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
            "facet_ids": [facet_id + 1 for facet_id in candidate.facet_ids],
            "core_facet_ids": [facet_id + 1 for facet_id in candidate.core_facet_ids],
            "matched_terms": candidate.matched_terms,
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
