from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Gene:
    id: str
    locus_id: str
    label: str
    content: str
    summary: str = ""
    kind: str = "knowledge"
    source_id: str = ""
    source_location: str = ""
    community: str = ""
    confidence: float = 1.0
    valid_from: str | None = None
    valid_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Relation:
    source_id: str
    target_id: str
    relation: str = "related_to"
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Candidate:
    gene: Gene
    score: float
    channels: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    facet_ids: list[int] = field(default_factory=list)
    core_facet_ids: list[int] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    protected: bool = False


@dataclass(slots=True)
class QueryResult:
    run_id: str
    query: str
    task: str
    budget: int
    context: str
    selected: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
