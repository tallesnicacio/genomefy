from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genomefy.adapters import Ingestor
from genomefy.audit import AuditLog
from genomefy.benchmark import run_benchmark, validate_suite
from genomefy.retrieval import GenomeRetriever, infer_task
from genomefy.skill_install import install_skill
from genomefy.store import GenomeStore
from genomefy.tokens import RegexTokenCounter, get_counter


REPO = Path(__file__).resolve().parents[1]


class GenomefyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = GenomeStore(self.root)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fixture(self) -> None:
        target = self.root / "knowledge.jsonl"
        target.write_text((REPO / "benchmarks/fixtures/knowledge.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        result = Ingestor(self.store).jsonl(target)
        self.assertEqual(result["genes"], 6)
        self.assertEqual(result["relations"], 3)

    def test_token_counter_falls_back_when_optional_backend_is_offline(self) -> None:
        with patch("genomefy.tokens.TiktokenCounter", side_effect=RuntimeError("offline")):
            counter = get_counter()
        self.assertIsInstance(counter, RegexTokenCounter)
        self.assertEqual(counter.name, "regex-estimate-v1")

    def test_init_ingest_query_budget_and_citations(self) -> None:
        self.fixture()
        result = GenomeRetriever(self.store).query("refresh authentication tokens", budget=85)
        self.assertLessEqual(result.metrics["context_tokens"], 85)
        self.assertEqual(result.selected[0]["gene_id"], "gene:auth-decision")
        self.assertTrue(result.selected[0]["citation"]["source_location"])
        explanation = GenomeRetriever(self.store).explain(result.run_id)
        self.assertEqual(explanation["transcript"]["selected"][0]["gene_id"], "gene:auth-decision")
        self.assertEqual(result.metrics["candidate_count"], len(result.selected) + len(result.excluded))

    def test_task_classifier_does_not_treat_classification_as_class(self) -> None:
        self.assertEqual(infer_task("Qual é a classificação do resultado do benchmark?"), "docs")

    def test_feedback_is_explicit_bounded_and_replayable(self) -> None:
        self.fixture()
        run = GenomeRetriever(self.store).query("explicit feedback silence", budget=90)
        events = AuditLog(self.store).feedback(run.run_id, True, "user explicitly accepted")
        self.assertTrue(events)
        marks = self.store.marks()
        self.assertGreater(marks["gene:feedback-rule"]["boost"], 0)
        self.assertLessEqual(marks["gene:feedback-rule"]["boost"], 0.10)
        replayed = AuditLog(self.store).replay()
        self.assertEqual(replayed["gene:feedback-rule"]["successes"], 1)

    def test_hash_chain_detects_tampering(self) -> None:
        self.fixture()
        self.assertTrue(AuditLog(self.store).verify()["valid"])
        with self.store.connect() as db:
            db.execute("UPDATE events SET reason='tampered' WHERE seq=1")
        self.assertFalse(AuditLog(self.store).verify()["valid"])

    def test_audit_detects_gene_and_transcript_tampering(self) -> None:
        self.fixture()
        run = GenomeRetriever(self.store).query("authentication refresh tokens", budget=90)
        with self.store.connect() as db:
            db.execute("UPDATE runs SET transcript_json='{}' WHERE id=?", (run.run_id,))
            db.execute("UPDATE genes SET content='changed' WHERE id='gene:auth-decision'")
        report = AuditLog(self.store).verify()
        self.assertFalse(report["valid"])
        self.assertTrue(any("transcript hash mismatch" in error for error in report["errors"]))
        self.assertTrue(any("gene gene:auth-decision" in error for error in report["errors"]))

    def test_docs_versions_and_path_escape(self) -> None:
        docs = self.root / "docs"; docs.mkdir(); page = docs / "guide.md"
        page.write_text("# Rule\nFirst version", encoding="utf-8")
        first = Ingestor(self.store).docs(docs)
        page.write_text("# Rule\nSecond contradictory version", encoding="utf-8")
        second = Ingestor(self.store).docs(docs)
        self.assertEqual(first["genes"], 1); self.assertEqual(second["genes"], 1)
        self.assertEqual(len(self.store.all_genes()), 2)
        with self.assertRaises(ValueError):
            Ingestor(self.store).docs(self.root.parent)

    def test_empty_heading_does_not_become_a_gene(self) -> None:
        page = self.root / "headings.md"
        page.write_text("# Title only\n## Useful\nActual evidence", encoding="utf-8")
        result = Ingestor(self.store).docs(page)
        self.assertEqual(result["genes"], 1)
        self.assertEqual(self.store.all_genes()[0].label, "Useful")

    def test_sensitive_document_name_is_skipped(self) -> None:
        page = self.root / "credentials.md"
        page.write_text("# Password\nNever ingest this", encoding="utf-8")
        result = Ingestor(self.store).docs(page)
        self.assertEqual(result["genes"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_graphify_adapter_preserves_direction_and_community(self) -> None:
        graph = {"nodes":[
            {"id":"a","label":"Alpha","content":"alpha context","community":3},
            {"id":"b","label":"Beta","content":"beta context","community":3}],
            "links":[{"source":"a","target":"b","type":"calls","directed":True,"confidence":0.8}]}
        path = self.root / "graph.json"; path.write_text(json.dumps(graph), encoding="utf-8")
        result = Ingestor(self.store).graphify(path)
        self.assertEqual(result["genes"], 2); self.assertEqual(result["relations"], 1)
        self.assertEqual({gene.community for gene in self.store.all_genes()}, {"3"})

    def test_skill_installer_refuses_unmanaged_overwrite(self) -> None:
        unmanaged = self.root / "skill"; unmanaged.mkdir(); (unmanaged / "mine.txt").write_text("x")
        with self.assertRaises(FileExistsError):
            install_skill(REPO / "skills/genomefy", unmanaged)
        managed = self.root / "managed"
        report = install_skill(REPO / "skills/genomefy", managed)
        self.assertTrue((managed / ".genomefy-install.json").is_file())
        self.assertGreater(report["files"], 1)

    def test_smoke_benchmark_is_never_pass(self) -> None:
        self.fixture()
        suite = REPO / "benchmarks/fixtures/smoke-suite.json"
        report = run_benchmark(self.store, suite)
        self.assertEqual(report["questions"], 8)
        self.assertIn(report["outcome"], {"INCONCLUSIVE", "FAIL"})
        self.assertEqual(report["paired_bootstrap"]["quality_delta"]["iterations"], 10_000)

    def test_stage2_suite_is_locked_and_references_real_genes(self) -> None:
        stage2 = REPO / "benchmarks/stage2"
        corpus = stage2 / "stage2-corpus.jsonl"
        local_corpus = self.root / corpus.name
        local_corpus.write_bytes(corpus.read_bytes())
        result = Ingestor(self.store).jsonl(local_corpus)
        self.assertEqual(result["genes"], 30)
        self.assertEqual(result["relations"], 14)
        integrity = validate_suite(self.store, stage2 / "stage2-suite.json")
        self.assertEqual(sum(integrity["categories"].values()), 60)
        self.assertEqual(integrity["categories"]["direct"], 20)
        self.assertEqual(integrity["categories"]["relational"], 12)
        self.assertEqual(len(integrity["corpus_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
