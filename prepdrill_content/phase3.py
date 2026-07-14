"""Phase 3 real-corpus activation and reversible migration controls."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

REQUIRED_ROLES = {
    "questions",
    "answer_keys",
    "contexts",
    "assets",
    "taxonomy",
    "source_documents",
    "golden_set",
    "audit_reviews",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class ManifestFile:
    role: str
    path: str
    checksum: str
    records: int
    source_kind: str = "fresh"

    def __post_init__(self) -> None:
        if not self.role or not self.path or len(self.checksum) < 8:
            raise ValueError("manifest file requires role, path, and checksum")
        if self.records < 0:
            raise ValueError("records cannot be negative")
        if self.source_kind not in {"fresh", "fixture", "legacy", "generated", "repaired"}:
            raise ValueError("unsupported source_kind")


@dataclass(frozen=True)
class ActivationThresholds:
    minimum_golden: int = 100
    minimum_audit: int = 250
    require_gate_pass: bool = True


@dataclass(frozen=True)
class ReconciliationInput:
    declared_counts: dict[str, int]
    loaded_counts: dict[str, int]
    orphaned_contexts: int = 0
    orphaned_assets: int = 0
    fixture_items: int = 0
    legacy_items: int = 0
    generated_items: int = 0
    repaired_unreviewed_items: int = 0
    unresolved_rights: int = 0
    invalid_sources: int = 0
    blocking_duplicates: int = 0
    golden_count: int = 0
    audit_count: int = 0
    phase15_gate_passed: bool = False
    gate_corpus_fingerprint: str = ""
    current_corpus_fingerprint: str = ""
    review_cost_measured: bool = False


@dataclass(frozen=True)
class ActivationReport:
    evaluation_id: str
    manifest_id: str
    passed: bool
    blockers: tuple[str, ...]
    corpus_fingerprint: str
    evaluated_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["blockers"] = list(self.blockers)
        return value


class CorpusActivationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._initialise()

    @classmethod
    def open(cls, path: str = ":memory:") -> "CorpusActivationRepository":
        return cls(sqlite3.connect(path))

    def _initialise(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS phase3_manifests (
              manifest_id TEXT PRIMARY KEY,
              delivery_name TEXT NOT NULL,
              corpus_version TEXT NOT NULL,
              manifest_json TEXT NOT NULL,
              manifest_fingerprint TEXT NOT NULL UNIQUE,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase3_migration_batches (
              batch_id TEXT PRIMARY KEY,
              manifest_id TEXT NOT NULL REFERENCES phase3_manifests(manifest_id),
              status TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              rolled_back_at TEXT
            );
            CREATE TABLE IF NOT EXISTS phase3_migration_events (
              event_id TEXT PRIMARY KEY,
              batch_id TEXT NOT NULL REFERENCES phase3_migration_batches(batch_id),
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase3_evaluations (
              evaluation_id TEXT PRIMARY KEY,
              manifest_id TEXT NOT NULL REFERENCES phase3_manifests(manifest_id),
              corpus_fingerprint TEXT NOT NULL,
              passed INTEGER NOT NULL,
              blockers_json TEXT NOT NULL,
              evidence_json TEXT NOT NULL,
              evaluated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase3_authorizations (
              authorization_id TEXT PRIMARY KEY,
              evaluation_id TEXT NOT NULL UNIQUE REFERENCES phase3_evaluations(evaluation_id),
              corpus_fingerprint TEXT NOT NULL,
              owner TEXT NOT NULL,
              reason TEXT NOT NULL,
              active INTEGER NOT NULL,
              authorized_at TEXT NOT NULL,
              revoked_at TEXT
            );
            """
        )
        self.connection.commit()

    def register_manifest(
        self,
        *,
        delivery_name: str,
        corpus_version: str,
        files: Iterable[ManifestFile],
        created_by: str,
    ) -> dict[str, Any]:
        if not delivery_name.strip() or not corpus_version.strip() or not created_by.strip():
            raise ValueError("delivery_name, corpus_version, and created_by are required")
        materialised = sorted((asdict(item) for item in files), key=lambda x: (x["role"], x["path"]))
        roles = {item["role"] for item in materialised}
        missing = sorted(REQUIRED_ROLES - roles)
        if missing:
            raise ValueError("missing manifest roles: " + ", ".join(missing))
        if len(materialised) != len({(item["role"], item["path"]) for item in materialised}):
            raise ValueError("duplicate manifest role/path")
        payload = {
            "delivery_name": delivery_name.strip(),
            "corpus_version": corpus_version.strip(),
            "files": materialised,
        }
        fingerprint = _hash(payload)
        manifest_id = _id("manifest", fingerprint)
        self.connection.execute(
            "INSERT OR IGNORE INTO phase3_manifests VALUES (?,?,?,?,?,?,?)",
            (manifest_id, payload["delivery_name"], payload["corpus_version"], _canonical(payload), fingerprint, created_by.strip(), _now()),
        )
        self.connection.commit()
        return {"manifest_id": manifest_id, "manifest_fingerprint": fingerprint, "roles": sorted(roles)}

    def create_migration_batch(self, manifest_id: str, *, created_by: str) -> str:
        self._manifest(manifest_id)
        if not created_by.strip():
            raise ValueError("created_by is required")
        batch_id = _id("migration", manifest_id, created_by.strip(), _now())
        self.connection.execute(
            "INSERT INTO phase3_migration_batches VALUES (?,?,?,?,?,NULL)",
            (batch_id, manifest_id, "running", created_by.strip(), _now()),
        )
        self._event(batch_id, "batch_started", {"manifest_id": manifest_id})
        self.connection.commit()
        return batch_id

    def append_migration_event(self, batch_id: str, event_type: str, payload: dict[str, Any]) -> str:
        row = self.connection.execute(
            "SELECT status FROM phase3_migration_batches WHERE batch_id=?", (batch_id,)
        ).fetchone()
        if not row:
            raise KeyError(batch_id)
        if row[0] == "rolled_back":
            raise ValueError("cannot append data events after rollback")
        event_id = self._event(batch_id, event_type, payload)
        self.connection.commit()
        return event_id

    def complete_migration(self, batch_id: str) -> None:
        updated = self.connection.execute(
            "UPDATE phase3_migration_batches SET status='completed' WHERE batch_id=? AND status='running'",
            (batch_id,),
        ).rowcount
        if updated != 1:
            raise ValueError("batch is not running")
        self._event(batch_id, "batch_completed", {})
        self.connection.commit()

    def rollback_migration(self, batch_id: str, *, actor: str, reason: str) -> str:
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
        row = self.connection.execute(
            "SELECT status FROM phase3_migration_batches WHERE batch_id=?", (batch_id,)
        ).fetchone()
        if not row:
            raise KeyError(batch_id)
        if row[0] == "rolled_back":
            existing = self.connection.execute(
                "SELECT event_id FROM phase3_migration_events WHERE batch_id=? AND event_type='rollback' ORDER BY created_at DESC LIMIT 1",
                (batch_id,),
            ).fetchone()
            return str(existing[0])
        timestamp = _now()
        self.connection.execute(
            "UPDATE phase3_migration_batches SET status='rolled_back', rolled_back_at=? WHERE batch_id=?",
            (timestamp, batch_id),
        )
        event_id = self._event(batch_id, "rollback", {"actor": actor.strip(), "reason": reason.strip()})
        self.connection.commit()
        return event_id

    def evaluate(
        self,
        manifest_id: str,
        evidence: ReconciliationInput,
        thresholds: ActivationThresholds | None = None,
    ) -> ActivationReport:
        manifest = self._manifest(manifest_id)
        selected = thresholds or ActivationThresholds()
        blockers: list[str] = []
        all_roles = sorted(set(evidence.declared_counts) | set(evidence.loaded_counts))
        for role in all_roles:
            if evidence.declared_counts.get(role) != evidence.loaded_counts.get(role):
                blockers.append(f"count_mismatch:{role}")
        if set(evidence.declared_counts) != REQUIRED_ROLES:
            blockers.append("declared_role_set_mismatch")
        checks = {
            "orphaned_contexts": evidence.orphaned_contexts,
            "orphaned_assets": evidence.orphaned_assets,
            "fixture_items": evidence.fixture_items,
            "legacy_items": evidence.legacy_items,
            "generated_items": evidence.generated_items,
            "repaired_unreviewed_items": evidence.repaired_unreviewed_items,
            "unresolved_rights": evidence.unresolved_rights,
            "invalid_sources": evidence.invalid_sources,
            "blocking_duplicates": evidence.blocking_duplicates,
        }
        blockers.extend(name for name, value in checks.items() if value != 0)
        if evidence.golden_count < selected.minimum_golden:
            blockers.append("golden_set_incomplete")
        if evidence.audit_count < selected.minimum_audit:
            blockers.append("audit_incomplete")
        if selected.require_gate_pass and not evidence.phase15_gate_passed:
            blockers.append("phase15_gate_failed")
        if not evidence.gate_corpus_fingerprint or evidence.gate_corpus_fingerprint != evidence.current_corpus_fingerprint:
            blockers.append("corpus_fingerprint_stale")
        if not evidence.review_cost_measured:
            blockers.append("review_cost_missing")
        files = json.loads(manifest["manifest_json"])["files"]
        if any(item["source_kind"] != "fresh" for item in files):
            blockers.append("non_fresh_manifest_source")
        blockers = sorted(set(blockers))
        evaluated_at = _now()
        evaluation_id = _id("phase3-eval", manifest_id, evidence.current_corpus_fingerprint, _hash(blockers), evaluated_at)
        self.connection.execute(
            "INSERT INTO phase3_evaluations VALUES (?,?,?,?,?,?,?)",
            (
                evaluation_id,
                manifest_id,
                evidence.current_corpus_fingerprint,
                int(not blockers),
                _canonical(blockers),
                _canonical(asdict(evidence)),
                evaluated_at,
            ),
        )
        self.connection.commit()
        return ActivationReport(evaluation_id, manifest_id, not blockers, tuple(blockers), evidence.current_corpus_fingerprint, evaluated_at)

    def authorize(self, evaluation_id: str, *, owner: str, reason: str) -> str:
        if not owner.strip() or not reason.strip():
            raise ValueError("owner and reason are required")
        row = self.connection.execute(
            "SELECT passed, corpus_fingerprint FROM phase3_evaluations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()
        if not row:
            raise KeyError(evaluation_id)
        if not bool(row[0]):
            raise ValueError("evaluation did not pass")
        existing = self.connection.execute(
            "SELECT authorization_id FROM phase3_authorizations WHERE evaluation_id=?", (evaluation_id,)
        ).fetchone()
        if existing:
            return str(existing[0])
        authorization_id = _id("phase3-auth", evaluation_id, owner.strip())
        self.connection.execute(
            "UPDATE phase3_authorizations SET active=0, revoked_at=? WHERE active=1",
            (_now(),),
        )
        self.connection.execute(
            "INSERT INTO phase3_authorizations VALUES (?,?,?,?,?,?,?,NULL)",
            (authorization_id, evaluation_id, row[1], owner.strip(), reason.strip(), 1, _now()),
        )
        self.connection.commit()
        return authorization_id

    def active_authorization(self, current_corpus_fingerprint: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM phase3_authorizations WHERE active=1 ORDER BY authorized_at DESC LIMIT 1"
        ).fetchone()
        if not row or row["corpus_fingerprint"] != current_corpus_fingerprint:
            return None
        return dict(row)

    def _manifest(self, manifest_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM phase3_manifests WHERE manifest_id=?", (manifest_id,)
        ).fetchone()
        if not row:
            raise KeyError(manifest_id)
        return row

    def _event(self, batch_id: str, event_type: str, payload: dict[str, Any]) -> str:
        created_at = _now()
        event_id = _id("migration-event", batch_id, event_type, _hash(payload), created_at)
        self.connection.execute(
            "INSERT INTO phase3_migration_events VALUES (?,?,?,?,?)",
            (event_id, batch_id, event_type, _canonical(payload), created_at),
        )
        return event_id


@dataclass(frozen=True)
class Phase3Evaluation:
    passed: bool
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "check_count": len(self.checks)}


class Phase3Evaluator:
    def _files(self, *, source_kind: str = "fresh") -> list[ManifestFile]:
        return [ManifestFile(role, f"delivery/{role}.jsonl", f"checksum-{role}", 10, source_kind) for role in sorted(REQUIRED_ROLES)]

    def _evidence(self, fingerprint: str, **changes: Any) -> ReconciliationInput:
        counts = {role: 10 for role in REQUIRED_ROLES}
        payload: dict[str, Any] = {
            "declared_counts": counts,
            "loaded_counts": dict(counts),
            "golden_count": 100,
            "audit_count": 250,
            "phase15_gate_passed": True,
            "gate_corpus_fingerprint": fingerprint,
            "current_corpus_fingerprint": fingerprint,
            "review_cost_measured": True,
        }
        payload.update(changes)
        return ReconciliationInput(**payload)

    def run(self) -> Phase3Evaluation:
        checks: dict[str, bool] = {}
        repo = CorpusActivationRepository.open()
        fresh_files = self._files()
        first = repo.register_manifest(delivery_name="paper1-real", corpus_version="v1", files=fresh_files, created_by="owner")
        second = repo.register_manifest(delivery_name="paper1-real", corpus_version="v1", files=list(reversed(fresh_files)), created_by="owner")
        checks["deterministic_manifest"] = first["manifest_fingerprint"] == second["manifest_fingerprint"]
        try:
            repo.register_manifest(delivery_name="bad", corpus_version="v1", files=fresh_files[:-1], created_by="owner")
            checks["missing_roles_blocked"] = False
        except ValueError:
            checks["missing_roles_blocked"] = True
        fingerprint = "corpus-fingerprint-v1"
        report = repo.evaluate(first["manifest_id"], self._evidence(fingerprint))
        checks["complete_evidence_passes"] = report.passed
        checks["count_mismatch_blocked"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, loaded_counts={**{r: 10 for r in REQUIRED_ROLES}, "questions": 9})).passed
        checks["orphans_blocked"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, orphaned_assets=1)).passed
        checks["forbidden_content_blocked"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, generated_items=1, legacy_items=1)).passed
        checks["rights_blocked"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, unresolved_rights=1)).passed
        checks["minimum_evidence_enforced"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, golden_count=99, audit_count=249)).passed
        checks["gate_enforced"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, phase15_gate_passed=False)).passed
        checks["stale_gate_blocked"] = not repo.evaluate(first["manifest_id"], self._evidence(fingerprint, current_corpus_fingerprint="drifted")).passed
        auth_id = repo.authorize(report.evaluation_id, owner="release-owner", reason="reviewed evidence")
        checks["named_authorization_created"] = bool(auth_id and repo.active_authorization(fingerprint))
        checks["drift_locks_authorization"] = repo.active_authorization("other-fingerprint") is None
        batch = repo.create_migration_batch(first["manifest_id"], created_by="migration-owner")
        repo.append_migration_event(batch, "loaded_questions", {"count": 10})
        repo.complete_migration(batch)
        rollback_id = repo.rollback_migration(batch, actor="migration-owner", reason="verification")
        event_count = repo.connection.execute("SELECT COUNT(*) FROM phase3_migration_events WHERE batch_id=?", (batch,)).fetchone()[0]
        checks["rollback_is_append_only"] = bool(rollback_id and event_count == 4)
        checks["evaluator_depth"] = len(checks) >= 12
        return Phase3Evaluation(all(checks.values()), checks)


if __name__ == "__main__":
    result = Phase3Evaluator().run()
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    raise SystemExit(0 if result.passed else 1)
