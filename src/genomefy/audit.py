from __future__ import annotations

import json
import uuid
from typing import Any

from .store import GenomeStore, digest_text, stable_json, utc_now


class AuditLog:
    def __init__(self, store: GenomeStore) -> None:
        self.store = store

    def append(
        self,
        event_type: str,
        *,
        gene_id: str | None = None,
        run_id: str | None = None,
        value: float | None = None,
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        event_id = f"evt:{uuid.uuid4().hex}"
        created_at = utc_now()
        payload_json = stable_json(payload or {})
        with self.store.connect() as db:
            previous = db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = previous["event_hash"] if previous else "GENESIS"
            material = stable_json({
                "id": event_id, "event_type": event_type, "gene_id": gene_id, "run_id": run_id,
                "value": value, "reason": reason, "payload": json.loads(payload_json),
                "created_at": created_at, "prev_hash": prev_hash,
            })
            event_hash = digest_text(material)
            db.execute(
                """INSERT INTO events(id,event_type,gene_id,run_id,value,reason,payload_json,created_at,prev_hash,event_hash)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (event_id, event_type, gene_id, run_id, value, reason, payload_json, created_at, prev_hash, event_hash),
            )
        return event_id

    def feedback(self, run_id: str, accepted: bool, reason: str = "explicit user feedback") -> list[str]:
        with self.store.connect() as db:
            run = db.execute("SELECT transcript_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise KeyError(f"Unknown run: {run_id}")
        transcript = json.loads(run["transcript_json"])
        event_ids: list[str] = []
        for item in transcript["selected"]:
            gene_id = item["gene_id"]
            event_ids.append(self.append(
                "feedback.accepted" if accepted else "feedback.rejected",
                gene_id=gene_id, run_id=run_id, value=1.0 if accepted else -1.0, reason=reason,
            ))
        self.replay()
        return event_ids

    def suppress(self, gene_id: str, suppressed: bool, reason: str) -> str:
        event_id = self.append(
            "mark.suppressed" if suppressed else "mark.unsuppressed",
            gene_id=gene_id, value=1.0 if suppressed else 0.0, reason=reason,
        )
        self.replay()
        return event_id

    def replay(self, to: str | int | None = None) -> dict[str, dict[str, Any]]:
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            marks: dict[str, dict[str, Any]] = {}
            for row in rows:
                if isinstance(to, int) and int(row["seq"]) > to:
                    break
                gene_id = row["gene_id"]
                if gene_id:
                    mark = marks.setdefault(gene_id, {"successes": 0, "failures": 0, "suppressed": 0})
                    if row["event_type"] == "feedback.accepted":
                        mark["successes"] += 1
                    elif row["event_type"] == "feedback.rejected":
                        mark["failures"] += 1
                    elif row["event_type"] == "mark.suppressed":
                        mark["suppressed"] = 1
                    elif row["event_type"] == "mark.unsuppressed":
                        mark["suppressed"] = 0
                if isinstance(to, str) and row["id"] == to:
                    break
            db.execute("DELETE FROM marks")
            for gene_id, mark in marks.items():
                total = mark["successes"] + mark["failures"]
                utility = (mark["successes"] + 1) / (total + 2)
                boost = max(-0.10, min(0.10, (utility - 0.5) * 0.20))
                db.execute(
                    "INSERT INTO marks VALUES(?,?,?,?,?,?)",
                    (gene_id, mark["successes"], mark["failures"], boost, mark["suppressed"], utc_now()),
                )
        return self.store.marks()

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        previous = "GENESIS"
        with self.store.connect() as db:
            gene_rows = db.execute("SELECT id,content,content_hash FROM genes").fetchall()
            for gene in gene_rows:
                if digest_text(gene["content"]) != gene["content_hash"]:
                    errors.append(f"gene {gene['id']}: content hash mismatch")
            rows = db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            for row in rows:
                if row["prev_hash"] != previous:
                    errors.append(f"event {row['id']}: previous hash mismatch")
                payload = json.loads(row["payload_json"])
                material = stable_json({
                    "id": row["id"], "event_type": row["event_type"], "gene_id": row["gene_id"],
                    "run_id": row["run_id"], "value": row["value"], "reason": row["reason"],
                    "payload": payload, "created_at": row["created_at"],
                    "prev_hash": row["prev_hash"],
                })
                computed = digest_text(material)
                if computed != row["event_hash"]:
                    errors.append(f"event {row['id']}: content hash mismatch")
                if row["event_type"] == "query.transcribed" and payload.get("transcript_hash"):
                    run = db.execute("SELECT transcript_json,metrics_json FROM runs WHERE id=?", (row["run_id"],)).fetchone()
                    if not run:
                        errors.append(f"event {row['id']}: missing run {row['run_id']}")
                    else:
                        if digest_text(run["transcript_json"]) != payload["transcript_hash"]:
                            errors.append(f"run {row['run_id']}: transcript hash mismatch")
                        if digest_text(run["metrics_json"]) != payload.get("metrics_hash"):
                            errors.append(f"run {row['run_id']}: metrics hash mismatch")
                previous = row["event_hash"]
        return {"valid": not errors, "events": len(rows), "genes": len(gene_rows), "head": previous, "errors": errors}
