from __future__ import annotations

from pathlib import Path

from .audit import AuditLog
from .retrieval import GenomeRetriever
from .store import GenomeStore


def serve(root: str | Path = ".") -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("MCP support is optional. Install with: pip install 'genomefy[mcp]'") from exc

    store = GenomeStore(root)
    retriever = GenomeRetriever(store)
    audit = AuditLog(store)
    mcp = FastMCP("Genomefy")

    @mcp.tool()
    def genomefy_query(query: str, task: str = "auto", budget: int = 1200) -> dict:
        """Retrieve bounded local context with citations and an audit transcript."""
        return retriever.query(query, task=task, budget=budget).to_dict()

    @mcp.tool()
    def genomefy_explain(run_id: str) -> dict:
        """Explain why each context gene was selected or excluded."""
        return retriever.explain(run_id)

    @mcp.tool()
    def genomefy_feedback(run_id: str, accepted: bool, reason: str = "explicit user feedback") -> dict:
        """Record explicit feedback; never infer feedback from silence."""
        return {"event_ids": audit.feedback(run_id, accepted, reason)}

    @mcp.tool()
    def genomefy_status() -> dict:
        """Return store counts, state hash and audit-chain integrity."""
        return status(store)

    mcp.run()


def status(store: GenomeStore) -> dict:
    with store.connect() as db:
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("sources", "genes", "relations", "events", "runs")}
    return {"root": str(store.root), "state_hash": store.state_hash(), "counts": counts, "audit": AuditLog(store).verify()}
