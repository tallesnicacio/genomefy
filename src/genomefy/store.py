from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Gene, Relation


SCHEMA_VERSION = "1"
FTS_WORD = re.compile(r"\w+", re.UNICODE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GenomeStore:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.state_dir = self.root / ".genomefy"
        self.db_path = self.state_dir / "genomefy.db"

    def initialize(self) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources(
                    id TEXT PRIMARY KEY, path TEXT NOT NULL, content_hash TEXT NOT NULL,
                    version INTEGER NOT NULL, created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS loci(id TEXT PRIMARY KEY, label TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS genes(
                    id TEXT PRIMARY KEY, locus_id TEXT NOT NULL, label TEXT NOT NULL, kind TEXT NOT NULL,
                    content TEXT NOT NULL, summary TEXT NOT NULL, source_id TEXT NOT NULL,
                    source_location TEXT NOT NULL, community TEXT NOT NULL, confidence REAL NOT NULL,
                    valid_from TEXT, valid_to TEXT, metadata_json TEXT NOT NULL, content_hash TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
                    FOREIGN KEY(locus_id) REFERENCES loci(id)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS genes_fts USING fts5(
                    gene_id UNINDEXED, label, summary, content, tokenize='unicode61'
                );
                CREATE TABLE IF NOT EXISTS relations(
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
                    relation TEXT NOT NULL, confidence REAL NOT NULL, evidence_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL,
                    gene_id TEXT, run_id TEXT, value REAL, reason TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS marks(
                    gene_id TEXT PRIMARY KEY, successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0, boost REAL NOT NULL DEFAULT 0,
                    suppressed INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, query TEXT NOT NULL, task TEXT NOT NULL, budget INTEGER NOT NULL,
                    token_counter TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
                    state_hash TEXT NOT NULL, transcript_json TEXT NOT NULL, metrics_json TEXT NOT NULL
                );
                """
            )
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,))
        return self.db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.state_dir.exists():
            raise FileNotFoundError(f"Genomefy not initialized at {self.root}")
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def add_source(self, path: str, content: str, metadata: dict[str, Any] | None = None) -> tuple[str, bool]:
        content_hash = digest_text(content)
        base = digest_text(str(Path(path).as_posix()))[:16]
        with self.connect() as db:
            previous = db.execute(
                "SELECT * FROM sources WHERE path=? ORDER BY version DESC LIMIT 1", (path,)
            ).fetchone()
            if previous and previous["content_hash"] == content_hash:
                return str(previous["id"]), False
            version = int(previous["version"]) + 1 if previous else 1
            source_id = f"src:{base}:v{version}"
            if previous:
                db.execute("UPDATE sources SET active=0 WHERE path=?", (path,))
            db.execute(
                "INSERT INTO sources VALUES(?,?,?,?,?,1,?)",
                (source_id, path, content_hash, version, utc_now(), stable_json(metadata or {})),
            )
        return source_id, True

    def add_gene(self, gene: Gene) -> bool:
        content_hash = digest_text(gene.content)
        with self.connect() as db:
            existing = db.execute("SELECT content_hash FROM genes WHERE id=?", (gene.id,)).fetchone()
            if existing and existing["content_hash"] == content_hash:
                return False
            db.execute("INSERT OR IGNORE INTO loci(id,label) VALUES(?,?)", (gene.locus_id, gene.label))
            if existing:
                db.execute("DELETE FROM genes_fts WHERE gene_id=?", (gene.id,))
                db.execute("DELETE FROM genes WHERE id=?", (gene.id,))
            db.execute(
                """INSERT INTO genes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                (
                    gene.id, gene.locus_id, gene.label, gene.kind, gene.content, gene.summary,
                    gene.source_id, gene.source_location, gene.community, gene.confidence,
                    gene.valid_from, gene.valid_to, stable_json(gene.metadata), content_hash, utc_now(),
                ),
            )
            db.execute(
                "INSERT INTO genes_fts(gene_id,label,summary,content) VALUES(?,?,?,?)",
                (gene.id, gene.label, gene.summary, gene.content),
            )
        return True

    def add_relation(self, relation: Relation) -> bool:
        rid = digest_text(stable_json({
            "s": relation.source_id, "t": relation.target_id, "r": relation.relation,
            "e": relation.evidence,
        }))[:24]
        with self.connect() as db:
            before = db.total_changes
            db.execute(
                "INSERT OR IGNORE INTO relations VALUES(?,?,?,?,?,?,?)",
                (rid, relation.source_id, relation.target_id, relation.relation, relation.confidence,
                 stable_json(relation.evidence), stable_json(relation.metadata)),
            )
            return db.total_changes > before

    @staticmethod
    def _gene(row: sqlite3.Row) -> Gene:
        return Gene(
            id=row["id"], locus_id=row["locus_id"], label=row["label"], kind=row["kind"],
            content=row["content"], summary=row["summary"], source_id=row["source_id"],
            source_location=row["source_location"], community=row["community"],
            confidence=float(row["confidence"]), valid_from=row["valid_from"], valid_to=row["valid_to"],
            metadata=json.loads(row["metadata_json"]),
        )

    def get_gene(self, gene_id: str) -> Gene | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM genes WHERE id=? AND active=1", (gene_id,)).fetchone()
        return self._gene(row) if row else None

    def all_genes(self) -> list[Gene]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM genes WHERE active=1 ORDER BY id").fetchall()
        return [self._gene(row) for row in rows]

    def fts(self, query: str, limit: int = 50) -> list[tuple[Gene, float]]:
        # Build the FTS expression from normalized words instead of whitespace
        # chunks. This keeps punctuation out of MATCH syntax and makes forms such
        # as ``log-redaction`` discover both ``log`` and ``redaction``.
        normalized = [term.casefold() for term in FTS_WORD.findall(query) if len(term) > 1]
        safe = " OR ".join(f'"{term}"' for term in dict.fromkeys(normalized))
        if not safe:
            return []
        with self.connect() as db:
            try:
                rows = db.execute(
                    """SELECT g.*, bm25(genes_fts) AS rank FROM genes_fts
                    JOIN genes g ON g.id=genes_fts.gene_id
                    WHERE genes_fts MATCH ? AND g.active=1 ORDER BY rank LIMIT ?""",
                    (safe, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [(self._gene(row), float(row["rank"])) for row in rows]

    def exact(self, query: str, limit: int = 50) -> list[Gene]:
        pattern = f"%{query.casefold()}%"
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM genes WHERE active=1 AND (lower(label) LIKE ? OR lower(id) LIKE ?) LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()
        return [self._gene(row) for row in rows]

    def neighbors(self, ids: list[str]) -> list[tuple[str, str, float, str]]:
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT * FROM relations WHERE source_id IN ({marks}) OR target_id IN ({marks})", ids + ids
            ).fetchall()
        return [(row["source_id"], row["target_id"], float(row["confidence"]), row["relation"]) for row in rows]

    def marks(self) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM marks").fetchall()
        return {row["gene_id"]: dict(row) for row in rows}

    def sources(self) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sources").fetchall()
        return {row["id"]: dict(row) for row in rows}

    def state_hash(self) -> str:
        with self.connect() as db:
            pieces = []
            for table in ("sources", "genes", "relations", "events"):
                rows = db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                pieces.append([dict(row) for row in rows])
        return digest_text(stable_json(pieces))
