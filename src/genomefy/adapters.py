from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .audit import AuditLog
from .models import Gene, Relation
from .store import GenomeStore, digest_text


ALLOWED_DOCS = {".md", ".markdown", ".txt", ".rst"}
SENSITIVE_NAMES = {".env", "credentials", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
SENSITIVE_PARTS = {".git", ".genomefy", ".venv", "node_modules"}


def _within(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"Path escapes project root: {path}")
    return resolved


def _sensitive(path: Path) -> bool:
    lowered = path.name.casefold()
    return (
        lowered in SENSITIVE_NAMES
        or path.stem.casefold() in {"credentials", "credential", "secrets", "secret", "tokens"}
        or any(part.casefold() in SENSITIVE_PARTS for part in path.parts)
    )


def _sections(text: str, fallback: str) -> Iterable[tuple[str, str, int]]:
    heading = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading.finditer(text))
    if not matches:
        if text.strip():
            yield fallback, text.strip(), 1
        return
    if text[: matches[0].start()].strip():
        yield fallback, text[: matches[0].start()].strip(), 1
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        line = text.count("\n", 0, match.start()) + 1
        if body:
            yield match.group(2).strip(), body, line


class Ingestor:
    def __init__(self, store: GenomeStore) -> None:
        self.store = store
        self.audit = AuditLog(store)

    def docs(self, input_path: str | Path) -> dict[str, int]:
        root = self.store.root
        path = _within(root, Path(input_path) if Path(input_path).is_absolute() else root / input_path)
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        result = {"sources": 0, "genes": 0, "skipped": 0}
        for file_path in files:
            relative = file_path.relative_to(root).as_posix()
            if file_path.suffix.lower() not in ALLOWED_DOCS or _sensitive(file_path):
                result["skipped"] += 1
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            source_id, changed = self.store.add_source(relative, text, {"adapter": "docs"})
            if not changed:
                result["skipped"] += 1
                continue
            result["sources"] += 1
            for ordinal, (label, content, line) in enumerate(_sections(text, file_path.stem), 1):
                locus = f"locus:{digest_text(relative + ':' + label)[:20]}"
                version = source_id.rsplit(":", 1)[-1]
                gene_id = f"gene:{digest_text(locus + ':' + version + ':' + str(ordinal))[:24]}"
                if self.store.add_gene(Gene(
                    id=gene_id, locus_id=locus, label=label, content=content,
                    summary=content.split("\n", 1)[0][:240], kind="documentation",
                    source_id=source_id, source_location=f"{relative}:{line}",
                    metadata={"adapter": "docs", "ordinal": ordinal},
                )):
                    result["genes"] += 1
                    self.audit.append("gene.ingested", gene_id=gene_id, reason="docs adapter", payload={"source_id": source_id})
        return result

    def jsonl(self, input_path: str | Path) -> dict[str, int]:
        path = _within(self.store.root, Path(input_path) if Path(input_path).is_absolute() else self.store.root / input_path)
        result = {"genes": 0, "relations": 0, "skipped": 0}
        file_text = path.read_text(encoding="utf-8")
        default_source_path = path.relative_to(self.store.root).as_posix()
        default_source_id, _ = self.store.add_source(default_source_path, file_text, {"adapter": "jsonl"})
        for line_number, raw in enumerate(file_text.splitlines(), 1):
            if not raw.strip():
                continue
            record = json.loads(raw)
            kind = record.get("record_type", "gene")
            if kind == "relation":
                if self.store.add_relation(Relation(
                    source_id=str(record["source_id"]), target_id=str(record["target_id"]),
                    relation=str(record.get("relation", "related_to")),
                    confidence=float(record.get("confidence", 1.0)), evidence=list(record.get("evidence", [])),
                    metadata=dict(record.get("metadata", {})),
                )):
                    result["relations"] += 1
                continue
            content = str(record["content"])
            source_path = str(record.get("source", default_source_path))
            source_id = default_source_id
            if source_path != default_source_path:
                source_id, _ = self.store.add_source(source_path, content, {"adapter": "jsonl", "line": line_number})
            locus = str(record.get("locus_id") or f"locus:{digest_text(str(record.get('label', '')) + source_path)[:20]}")
            gene_id = str(record.get("id") or f"gene:{digest_text(locus + source_id + content)[:24]}")
            gene = Gene(
                id=gene_id, locus_id=locus, label=str(record.get("label", gene_id)), content=content,
                summary=str(record.get("summary", content[:240])), kind=str(record.get("kind", "knowledge")),
                source_id=source_id, source_location=str(record.get("source_location", f"{source_path}:{line_number}")),
                community=str(record.get("community", "")), confidence=float(record.get("confidence", 1.0)),
                valid_from=record.get("valid_from"), valid_to=record.get("valid_to"),
                metadata=dict(record.get("metadata", {})),
            )
            if self.store.add_gene(gene):
                result["genes"] += 1
                self.audit.append("gene.ingested", gene_id=gene_id, reason="jsonl adapter", payload={"source_id": source_id})
            else:
                result["skipped"] += 1
        return result

    def graphify(self, input_path: str | Path) -> dict[str, int]:
        path = _within(self.store.root, Path(input_path) if Path(input_path).is_absolute() else self.store.root / input_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])
        links = data.get("links", data.get("edges", []))
        result = {"genes": 0, "relations": 0, "hyperedges": 0, "skipped": 0}
        id_map: dict[str, str] = {}
        source_id, _ = self.store.add_source(path.relative_to(self.store.root).as_posix(), json.dumps(data, sort_keys=True), {
            "adapter": "graphify", "graphify_schema": data.get("version", "unversioned")
        })
        for node in nodes:
            original_id = str(node.get("id", node.get("name", "")))
            if not original_id:
                result["skipped"] += 1
                continue
            gene_id = f"gene:graphify:{digest_text(original_id)[:20]}"
            id_map[original_id] = gene_id
            label = str(node.get("label", node.get("name", original_id)))
            content = str(node.get("content", node.get("description", label)))
            locus = f"locus:graphify:{digest_text(str(node.get('locus', original_id)))[:16]}"
            if self.store.add_gene(Gene(
                id=gene_id, locus_id=locus, label=label, content=content,
                summary=str(node.get("summary", content[:240])), kind=str(node.get("type", node.get("kind", "graph_node"))),
                source_id=source_id, source_location=str(node.get("source_location", node.get("source_file", path.name))),
                community=str(node.get("community", node.get("community_id", ""))),
                confidence=float(node.get("confidence", 1.0)), metadata={"adapter": "graphify", "original": node},
            )):
                result["genes"] += 1
        for link in links:
            source = str(link.get("source", "")); target = str(link.get("target", ""))
            if source in id_map and target in id_map and self.store.add_relation(Relation(
                source_id=id_map[source], target_id=id_map[target], relation=str(link.get("type", link.get("relation", "related_to"))),
                confidence=float(link.get("confidence", 1.0)), evidence=list(link.get("evidence", [])),
                metadata={"directed": bool(link.get("directed", True)), "adapter": "graphify", "original": link},
            )):
                result["relations"] += 1
        for edge in data.get("hyperedges", []):
            members = [id_map[str(member)] for member in edge.get("members", []) if str(member) in id_map]
            for left, right in zip(members, members[1:]):
                if self.store.add_relation(Relation(
                    source_id=left, target_id=right, relation=str(edge.get("type", "hyperedge_member")),
                    confidence=float(edge.get("confidence", 1.0)), metadata={"hyperedge": edge.get("id")},
                )):
                    result["relations"] += 1
            result["hyperedges"] += 1
        self.audit.append("source.graphify_ingested", reason="graphify adapter", payload={"source_id": source_id, **result})
        return result
