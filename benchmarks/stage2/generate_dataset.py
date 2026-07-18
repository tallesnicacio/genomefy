"""Generate the locked, synthetic stage-2 retrieval corpus and 60-question suite.

The data is fictional by design: it can be published, hashed and reproduced without
leaking a real project. Questions are declared before the first benchmark run.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "stage2-corpus.jsonl"
SUITE = ROOT / "stage2-suite.json"


STABLE_GENES = [
    ("gene:gateway-port", "locus:gateway-port", "Atlas gateway port", "network", "The Atlas public gateway listens on TCP port 7443 and rejects plain HTTP.", "Which TCP port does the Atlas public gateway use?"),
    ("gene:database-engine", "locus:database", "Cobalt database engine", "infrastructure", "Cobalt persistence runs PostgreSQL 16 with synchronous commit enabled.", "Which database engine and major version power Cobalt persistence?"),
    ("gene:cache-engine", "locus:cache", "Ember cache engine", "infrastructure", "Ember caching uses Redis 7 with a five-minute default TTL.", "Which engine and version provide the Ember cache?"),
    ("gene:primary-region", "locus:region", "Iris primary region", "deployment", "The Iris production control plane is hosted in the sa-east-1 São Paulo region.", "Where is the Iris production control plane hosted?"),
    ("gene:backup-window", "locus:backup", "Luna backup window", "operations", "Luna creates an encrypted database backup every day at 02:30 UTC.", "At what UTC time does Luna create its daily backup?"),
    ("gene:signing-algorithm", "locus:signing", "Mira signing algorithm", "security", "Mira signs access tokens with Ed25519 keys stored in the local key vault.", "Which algorithm signs Mira access tokens?"),
    ("gene:refresh-policy", "locus:refresh", "Nexus refresh policy", "security", "Nexus rotates each refresh token after use and rejects token reuse.", "What does Nexus do with a refresh token after it is used?"),
    ("gene:rate-limit", "locus:rate-limit", "Orbit request limit", "network", "Orbit limits each authenticated client to 120 requests per minute.", "How many requests per minute may an authenticated Orbit client send?"),
    ("gene:trace-standard", "locus:tracing", "Prism trace standard", "observability", "Prism propagates distributed traces using the W3C Trace Context headers.", "Which standard does Prism use to propagate distributed traces?"),
    ("gene:alert-delay", "locus:alerts", "Quasar alert delay", "operations", "Quasar opens an alert after an SLO violation persists for five minutes.", "How long must an SLO violation persist before Quasar opens an alert?"),
    ("gene:object-storage", "locus:object-storage", "Rhea object storage", "infrastructure", "Rhea stores immutable artifacts in an S3-compatible object store.", "Where does Rhea store immutable artifacts?"),
    ("gene:search-engine", "locus:search", "Sol search engine", "infrastructure", "Sol indexes artifact metadata in OpenSearch 2.", "Which search engine indexes artifact metadata for Sol?"),
    ("gene:upload-limit", "locus:upload", "Titan upload limit", "constraint", "Titan accepts individual uploads up to 64 MiB.", "What is the maximum size of one Titan upload?"),
    ("gene:quarantine-duration", "locus:quarantine", "Umbra quarantine duration", "security", "Umbra quarantines every new upload for 24 hours before release.", "How long does Umbra quarantine a new upload?"),
    ("gene:health-endpoint", "locus:health", "Wave readiness endpoint", "operations", "Wave exposes deployment readiness at the /readyz endpoint.", "Which endpoint reports Wave deployment readiness?"),
    ("gene:schema-format", "locus:schema", "Xenon event schema", "integration", "Xenon serializes domain events with Apache Avro schemas.", "Which schema format does Xenon use for domain events?"),
    ("gene:log-redaction", "locus:redaction", "Zephyr log redaction", "security", "Zephyr redacts credential-like log values after the first 30 characters.", "After how many characters does Zephyr redact credential-like log values?"),
    ("gene:owner-team", "locus:ownership", "Platform owner team", "ownership", "The Aurora Platform team owns the production service and its runbooks.", "Which team owns the production service and runbooks?"),
    ("gene:latency-slo", "locus:latency", "API latency SLO", "requirement", "The public API p95 latency objective is 250 milliseconds.", "What is the public API p95 latency objective?"),
    ("gene:incident-channel", "locus:incident", "Incident coordination channel", "operations", "Production incidents are coordinated in the #ops-bridge channel.", "Which channel coordinates production incidents?"),
]


TEMPORAL_GENES = [
    ("gene:session-ttl-v1", "locus:session-ttl", "Deprecated session lifetime", "security", "Deprecated policy: interactive sessions lasted 60 minutes.", "2025-01-01", "2026-02-01"),
    ("gene:session-ttl-v2", "locus:session-ttl", "Current session lifetime", "security", "Current policy: interactive sessions last 15 minutes.", "2026-02-01", None),
    ("gene:retention-v1", "locus:retention", "Deprecated audit retention", "constraint", "Deprecated policy: audit records were retained for 30 days.", "2025-01-01", "2026-03-01"),
    ("gene:retention-v2", "locus:retention", "Current audit retention", "constraint", "Current policy: audit records are retained for 90 days.", "2026-03-01", None),
    ("gene:deploy-v1", "locus:deployment-strategy", "Deprecated deployment strategy", "deployment", "Deprecated strategy: production releases used rolling replacement.", "2025-01-01", "2026-04-01"),
    ("gene:deploy-v2", "locus:deployment-strategy", "Current deployment strategy", "deployment", "Current strategy: production releases use blue-green deployment.", "2026-04-01", None),
    ("gene:queue-v1", "locus:message-queue", "Deprecated message queue", "integration", "Deprecated transport: workers consumed jobs from RabbitMQ.", "2025-01-01", "2026-05-01"),
    ("gene:queue-v2", "locus:message-queue", "Current message queue", "integration", "Current transport: workers consume jobs from Apache Pulsar.", "2026-05-01", None),
    ("gene:checksum-v1", "locus:checksum", "Deprecated artifact checksum", "security", "Deprecated integrity check: artifacts used MD5 checksums.", "2025-01-01", "2026-06-01"),
    ("gene:checksum-v2", "locus:checksum", "Current artifact checksum", "security", "Current integrity check: artifacts use SHA-256 checksums.", "2026-06-01", None),
]


RELATIONS = [
    ("gene:gateway-port", "gene:database-engine", "depends_on"),
    ("gene:gateway-port", "gene:cache-engine", "depends_on"),
    ("gene:signing-algorithm", "gene:refresh-policy", "joint_control"),
    ("gene:upload-limit", "gene:quarantine-duration", "guarded_by"),
    ("gene:quarantine-duration", "gene:checksum-v2", "verified_by"),
    ("gene:alert-delay", "gene:latency-slo", "monitors"),
    ("gene:deploy-v2", "gene:health-endpoint", "validated_by"),
    ("gene:queue-v2", "gene:schema-format", "encodes_with"),
    ("gene:log-redaction", "gene:incident-channel", "protects"),
    ("gene:search-engine", "gene:object-storage", "indexes"),
    ("gene:owner-team", "gene:primary-region", "operates"),
    ("gene:backup-window", "gene:database-engine", "backs_up"),
    ("gene:rate-limit", "gene:gateway-port", "enforced_at"),
    ("gene:retention-v2", "gene:object-storage", "applies_to"),
]


RELATIONAL_QUESTIONS = [
    ("r01", "relational", "Which database and cache back the Atlas gateway?", ["gene:database-engine", "gene:cache-engine"]),
    ("r02", "relational", "Which two controls protect Mira and Nexus token authentication?", ["gene:signing-algorithm", "gene:refresh-policy"]),
    ("r03", "relational", "Which upload size, quarantine period and checksum protect artifacts?", ["gene:upload-limit", "gene:quarantine-duration", "gene:checksum-v2"]),
    ("r04", "relational", "What latency objective does Quasar monitor and after what delay does it alert?", ["gene:latency-slo", "gene:alert-delay"]),
    ("r05", "relational", "Which current deployment strategy is checked through which readiness endpoint?", ["gene:deploy-v2", "gene:health-endpoint"]),
    ("r06", "relational", "Which current worker transport carries events in which schema format?", ["gene:queue-v2", "gene:schema-format"]),
    ("r07", "relational", "Which redaction rule protects coordination in the production incident channel?", ["gene:log-redaction", "gene:incident-channel"]),
    ("r08", "relational", "Which engine makes metadata from the immutable artifact store searchable?", ["gene:search-engine", "gene:object-storage"]),
    ("r09", "relational", "Which team operates production and in which primary region?", ["gene:owner-team", "gene:primary-region"]),
    ("r10", "relational", "When is the database backed up and which engine is being protected?", ["gene:backup-window", "gene:database-engine"]),
    ("r11", "relational", "Which client rate is enforced at the public gateway and which port receives it?", ["gene:rate-limit", "gene:gateway-port"]),
    ("r12", "relational", "How long are current audit records retained and where are immutable artifacts stored?", ["gene:retention-v2", "gene:object-storage"]),
]


TEMPORAL_QUESTIONS = [
    ("t01", "temporal", "What is the current interactive session lifetime?", ["gene:session-ttl-v2"]),
    ("t02", "temporal", "After the February 2026 change, how long does an interactive session last?", ["gene:session-ttl-v2"]),
    ("t03", "temporal", "What is the current audit-record retention period?", ["gene:retention-v2"]),
    ("t04", "temporal", "Which audit retention policy replaced the old 30-day rule?", ["gene:retention-v2"]),
    ("t05", "temporal", "Which deployment strategy is current for production releases?", ["gene:deploy-v2"]),
    ("t06", "temporal", "What release strategy replaced rolling replacement?", ["gene:deploy-v2"]),
    ("t07", "temporal", "Which message queue do workers currently consume?", ["gene:queue-v2"]),
    ("t08", "temporal", "What transport replaced RabbitMQ for worker jobs?", ["gene:queue-v2"]),
    ("t09", "temporal", "Which checksum is currently required for artifact integrity?", ["gene:checksum-v2"]),
    ("t10", "temporal", "What integrity check replaced MD5?", ["gene:checksum-v2"]),
]


CONSTRAINT_QUESTIONS = [
    ("c01", "constraint", "Current session duration -deprecated", ["gene:session-ttl-v2"]),
    ("c02", "constraint", "Current audit retention -deprecated", ["gene:retention-v2"]),
    ("c03", "constraint", "Current production deployment strategy -deprecated", ["gene:deploy-v2"]),
    ("c04", "constraint", "Current worker message queue -deprecated", ["gene:queue-v2"]),
    ("c05", "constraint", "Current artifact checksum -deprecated", ["gene:checksum-v2"]),
    ("c06", "constraint", "Upload limit quarantine and current checksum -deprecated", ["gene:upload-limit", "gene:quarantine-duration", "gene:checksum-v2"]),
    ("c07", "constraint", "Current message transport and event schema -deprecated", ["gene:queue-v2", "gene:schema-format"]),
    ("c08", "constraint", "Current release strategy and readiness endpoint -deprecated", ["gene:deploy-v2", "gene:health-endpoint"]),
]


MULTIFACT_QUESTIONS = [
    ("m01", "multifact", "Summarize public ingress: gateway port, client rate and readiness endpoint.", ["gene:gateway-port", "gene:rate-limit", "gene:health-endpoint"]),
    ("m02", "multifact", "Name the database, cache, search engine and immutable object store.", ["gene:database-engine", "gene:cache-engine", "gene:search-engine", "gene:object-storage"]),
    ("m03", "multifact", "Summarize authentication: signing algorithm, refresh-token behavior and current session lifetime.", ["gene:signing-algorithm", "gene:refresh-policy", "gene:session-ttl-v2"]),
    ("m04", "multifact", "Give the backup time, alert delay and incident coordination channel.", ["gene:backup-window", "gene:alert-delay", "gene:incident-channel"]),
    ("m05", "multifact", "State the upload limit, quarantine duration and current integrity checksum.", ["gene:upload-limit", "gene:quarantine-duration", "gene:checksum-v2"]),
    ("m06", "multifact", "Name the current message queue, event schema and owning team.", ["gene:queue-v2", "gene:schema-format", "gene:owner-team"]),
    ("m07", "multifact", "State the tracing standard, latency objective and log-redaction threshold.", ["gene:trace-standard", "gene:latency-slo", "gene:log-redaction"]),
    ("m08", "multifact", "Give the primary region, current deployment strategy and readiness endpoint.", ["gene:primary-region", "gene:deploy-v2", "gene:health-endpoint"]),
    ("m09", "multifact", "How long are audits retained and when is the database backup created?", ["gene:retention-v2", "gene:backup-window"]),
    ("m10", "multifact", "Which search engine covers the artifact store and what retention applies to audits?", ["gene:search-engine", "gene:object-storage", "gene:retention-v2"]),
]


def sha256(path: Path) -> str:
    data = path.read_bytes()
    canonical = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(canonical).hexdigest()


def main() -> None:
    records: list[dict] = []
    direct_questions: list[tuple[str, str, str, list[str]]] = []
    for index, (gene_id, locus, label, kind, content, question) in enumerate(STABLE_GENES, 1):
        records.append({
            "id": gene_id, "locus_id": locus, "label": label, "kind": kind,
            "content": content, "summary": content, "confidence": 1.0,
            "metadata": {"dataset": "stage2-60-v1", "status": "current"},
        })
        direct_questions.append((f"d{index:02d}", "direct", question, [gene_id]))
    for gene_id, locus, label, kind, content, valid_from, valid_to in TEMPORAL_GENES:
        records.append({
            "id": gene_id, "locus_id": locus, "label": label, "kind": kind,
            "content": content, "summary": content, "confidence": 1.0,
            "valid_from": valid_from, "valid_to": valid_to,
            "metadata": {"dataset": "stage2-60-v1", "status": "historical" if valid_to else "current"},
        })

    lines: list[str] = []
    for line_number, record in enumerate(records, 1):
        record["source_location"] = f"stage2-corpus.jsonl:{line_number}"
        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    for source, target, relation in RELATIONS:
        lines.append(json.dumps({
            "record_type": "relation", "source_id": source, "target_id": target,
            "relation": relation, "confidence": 1.0,
            "metadata": {"dataset": "stage2-60-v1", "direction": "declared"},
        }, ensure_ascii=False, sort_keys=True))
    CORPUS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    declared = direct_questions + RELATIONAL_QUESTIONS + TEMPORAL_QUESTIONS + CONSTRAINT_QUESTIONS + MULTIFACT_QUESTIONS
    budgets = {"direct": 120, "relational": 210, "temporal": 130, "constraint": 210, "multifact": 280}
    questions = [
        {"id": qid, "category": category, "query": query, "expected_gene_ids": expected, "budget": budgets[category]}
        for qid, category, query, expected in declared
    ]
    category_counts = dict(sorted(Counter(question["category"] for question in questions).items()))
    assert len(questions) == 60
    assert category_counts == {"constraint": 8, "direct": 20, "multifact": 10, "relational": 12, "temporal": 10}
    assert len({question["id"] for question in questions}) == 60
    assert len({question["query"] for question in questions}) == 60

    suite = {
        "schema": "genomefy-benchmark-suite-v2",
        "name": "genomefy-stage2-controlled-retrieval-60-v1",
        "evaluation_scope": "retrieval-only",
        "description": "Fictional, deterministic project-memory corpus with direct, relational, temporal, constraint and multi-fact questions.",
        "expected_questions": 60,
        "category_counts": category_counts,
        "corpus_file": CORPUS.name,
        "corpus_sha256": sha256(CORPUS),
        "locked_gates": {
            "token_savings": 0.25,
            "quality_margin": -0.02,
            "citation_accuracy": 0.95,
            "minimum_questions_for_pass": 30,
            "category_quality_margin": -0.10,
            "deterministic_stability": 1.0
        },
        "stability": {
            "question_ids": ["d01", "d05", "d10", "d15", "r01", "r05", "r09", "t01", "t05", "c01", "c06", "m03"],
            "repetitions": 3,
        },
        "questions": questions,
    }
    SUITE.write_text(json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"corpus": str(CORPUS), "corpus_sha256": suite["corpus_sha256"], "questions": len(questions), "categories": category_counts}, indent=2))


if __name__ == "__main__":
    main()
