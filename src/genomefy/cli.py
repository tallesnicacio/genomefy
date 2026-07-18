from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .adapters import Ingestor
from .audit import AuditLog
from .benchmark import compare_reports, run_benchmark
from .mcp_server import serve, status
from .retrieval import GenomeRetriever
from .skill_install import install_skill
from .store import GenomeStore


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="genomefy", description="Local, selective and auditable context memory")
    command.add_argument("--root", default=".", help="Project root containing .genomefy")
    sub = command.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize .genomefy in the project root")

    ingest = sub.add_parser("ingest", help="Ingest a supported source")
    ingest.add_argument("adapter", choices=("docs", "jsonl", "graphify")); ingest.add_argument("path")
    query = sub.add_parser("query", help="Retrieve a bounded context transcript")
    query.add_argument("query"); query.add_argument("--task", default="auto"); query.add_argument("--budget", type=int, default=1200); query.add_argument("--json", action="store_true")
    feedback = sub.add_parser("feedback", help="Record explicit feedback for a run")
    feedback.add_argument("run_id"); choice = feedback.add_mutually_exclusive_group(required=True)
    choice.add_argument("--accepted", action="store_true"); choice.add_argument("--rejected", action="store_true"); feedback.add_argument("--reason", default="explicit user feedback")
    audit = sub.add_parser("audit", help="Explain a run or verify the hash chain"); audit.add_argument("target", help="run id or 'verify'")
    replay = sub.add_parser("replay", help="Rebuild epigenetic marks from events"); replay.add_argument("--to", help="event id or sequence")
    sub.add_parser("status", help="Show local store state and integrity")

    benchmark = sub.add_parser("benchmark", help="Run or compare auditable benchmarks")
    bench_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    run = bench_sub.add_parser("run"); run.add_argument("suite"); run.add_argument("--output")
    compare = bench_sub.add_parser("compare"); compare.add_argument("left"); compare.add_argument("right")
    skill = sub.add_parser("skill", help="Manage the Codex skill"); skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    install = skill_sub.add_parser("install"); install.add_argument("--source"); install.add_argument("--target"); install.add_argument("--global", dest="global_install", action="store_true")
    mcp = sub.add_parser("mcp", help="Run the optional local MCP server"); mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True); mcp_sub.add_parser("serve")
    return command


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    command_parser = parser(); args = command_parser.parse_args(argv); store = GenomeStore(args.root)
    try:
        if args.command == "init": emit({"initialized": str(store.initialize()), "schema": 1})
        elif args.command == "ingest": emit(getattr(Ingestor(store), args.adapter)(args.path))
        elif args.command == "query":
            result = GenomeRetriever(store).query(args.query, task=args.task, budget=args.budget)
            if args.json: emit(result.to_dict())
            else:
                print(result.context)
                print(f"\n[AUDIT run={result.run_id} tokens={result.metrics['context_tokens']}/{result.budget} counter={result.metrics['token_counter']}]")
        elif args.command == "feedback": emit({"event_ids": AuditLog(store).feedback(args.run_id, args.accepted, args.reason)})
        elif args.command == "audit": emit(AuditLog(store).verify() if args.target == "verify" else GenomeRetriever(store).explain(args.target))
        elif args.command == "replay":
            target: str | int | None = args.to
            if target and target.isdigit(): target = int(target)
            emit({"marks": AuditLog(store).replay(target)})
        elif args.command == "status": emit(status(store))
        elif args.command == "benchmark":
            emit(run_benchmark(store, args.suite, args.output) if args.benchmark_command == "run" else compare_reports(args.left, args.right))
        elif args.command == "skill":
            project = Path(__file__).resolve().parents[2]
            source = Path(args.source).resolve() if args.source else project / "skills" / "genomefy"
            if args.target: target = Path(args.target)
            elif args.global_install:
                target = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills" / "genomefy"
            else: target = store.root / ".agents" / "skills" / "genomefy"
            emit(install_skill(source, target))
        elif args.command == "mcp" and args.mcp_command == "serve": serve(store.root)
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        command_parser.exit(2, f"genomefy: error: {exc}\n")
    return 2
