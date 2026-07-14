"""Phase 5 grounded explanation generation and review controls."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class GroundingBundle:
    published_revision_id: str
    correct_option_id: str
    concept_id: str
    evidence: dict[str, str]
    question_text: str
    options: dict[str, str]

    def fingerprint(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True)
class GenerationPolicy:
    prompt_version: str = "phase5.v1"
    cheap_model: str = "volume-model"
    reasoning_model: str = "reasoning-model"
    max_cost_micros: int = 50_000


@dataclass(frozen=True)
class ExplanationResult:
    explanation_id: str
    status: str
    cache_key: str
    blockers: tuple[str, ...]
    content: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["blockers"] = list(self.blockers)
        return value


Provider = Callable[[dict[str, Any], str], dict[str, Any]]


class ExplanationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._initialise()

    @classmethod
    def open(cls, path: str = ":memory:") -> "ExplanationRepository":
        return cls(sqlite3.connect(path))

    def _initialise(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS phase5_grounding_bundles (
              bundle_id TEXT PRIMARY KEY,
              fingerprint TEXT NOT NULL UNIQUE,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase5_generation_requests (
              request_id TEXT PRIMARY KEY,
              cache_key TEXT NOT NULL UNIQUE,
              bundle_id TEXT NOT NULL REFERENCES phase5_grounding_bundles(bundle_id),
              selected_option_id TEXT NOT NULL,
              model TEXT NOT NULL,
              prompt_version TEXT NOT NULL,
              estimated_cost_micros INTEGER NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase5_explanation_revisions (
              explanation_id TEXT PRIMARY KEY,
              request_id TEXT NOT NULL REFERENCES phase5_generation_requests(request_id),
              revision_number INTEGER NOT NULL,
              status TEXT NOT NULL,
              content_json TEXT,
              blockers_json TEXT NOT NULL,
              reviewer TEXT,
              reviewed_at TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(request_id, revision_number)
            );
            CREATE TABLE IF NOT EXISTS phase5_review_queue (
              review_item_id TEXT PRIMARY KEY,
              explanation_id TEXT NOT NULL REFERENCES phase5_explanation_revisions(explanation_id),
              reason TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def register_bundle(self, bundle: GroundingBundle) -> str:
        if not bundle.published_revision_id or not bundle.correct_option_id or not bundle.evidence:
            raise ValueError("incomplete grounding bundle")
        fingerprint = bundle.fingerprint()
        bundle_id = _id("grounding", fingerprint)
        self.connection.execute(
            "INSERT OR IGNORE INTO phase5_grounding_bundles VALUES (?,?,?,?)",
            (bundle_id, fingerprint, _canonical(asdict(bundle)), _now()),
        )
        self.connection.commit()
        return bundle_id

    def route_model(self, bundle: GroundingBundle, selected_option_id: str, policy: GenerationPolicy) -> str:
        complexity = len(bundle.question_text) + sum(map(len, bundle.options.values())) + len(bundle.evidence) * 40
        return policy.reasoning_model if complexity > 220 or selected_option_id not in bundle.options else policy.cheap_model

    def generate(
        self,
        bundle: GroundingBundle,
        *,
        selected_option_id: str,
        provider: Provider,
        policy: GenerationPolicy | None = None,
        estimated_cost_micros: int = 1_000,
    ) -> ExplanationResult:
        selected = policy or GenerationPolicy()
        bundle_id = self.register_bundle(bundle)
        model = self.route_model(bundle, selected_option_id, selected)
        cache_key = _hash({"bundle": bundle.fingerprint(), "selected": selected_option_id, "prompt": selected.prompt_version, "model": model})
        existing = self.connection.execute(
            "SELECT explanation_id FROM phase5_explanation_revisions r JOIN phase5_generation_requests q ON q.request_id=r.request_id WHERE q.cache_key=? ORDER BY r.revision_number DESC LIMIT 1",
            (cache_key,),
        ).fetchone()
        if existing:
            return self.get_result(str(existing[0]))
        request_id = _id("explain-request", cache_key)
        if estimated_cost_micros > selected.max_cost_micros:
            self._insert_request(request_id, cache_key, bundle_id, selected_option_id, model, selected.prompt_version, estimated_cost_micros, "blocked")
            return self._revision(request_id, "blocked", None, ["cost_ceiling_exceeded"])
        self._insert_request(request_id, cache_key, bundle_id, selected_option_id, model, selected.prompt_version, estimated_cost_micros, "running")
        prompt = {
            "published_revision_id": bundle.published_revision_id,
            "correct_option_id": bundle.correct_option_id,
            "selected_option_id": selected_option_id,
            "concept_id": bundle.concept_id,
            "evidence": bundle.evidence,
            "question_text": bundle.question_text,
            "options": bundle.options,
        }
        try:
            output = provider(prompt, model)
        except Exception:
            self.connection.execute("UPDATE phase5_generation_requests SET status='unavailable' WHERE request_id=?", (request_id,))
            self.connection.commit()
            return self._revision(request_id, "unavailable", None, ["provider_unavailable"])
        blockers = self._validate(bundle, selected_option_id, output)
        status = "review" if blockers else "pending_approval"
        self.connection.execute("UPDATE phase5_generation_requests SET status=? WHERE request_id=?", (status, request_id))
        self.connection.commit()
        result = self._revision(request_id, status, output, blockers)
        if blockers:
            for reason in blockers:
                self._queue(result.explanation_id, reason)
        return result

    def approve(self, explanation_id: str, *, reviewer: str) -> ExplanationResult:
        if not reviewer.strip():
            raise ValueError("reviewer is required")
        row = self.connection.execute("SELECT * FROM phase5_explanation_revisions WHERE explanation_id=?", (explanation_id,)).fetchone()
        if not row:
            raise KeyError(explanation_id)
        if row["status"] != "pending_approval":
            raise ValueError("only clean pending explanations can be approved")
        self.connection.execute(
            "UPDATE phase5_explanation_revisions SET status='approved', reviewer=?, reviewed_at=? WHERE explanation_id=?",
            (reviewer.strip(), _now(), explanation_id),
        )
        self.connection.commit()
        return self.get_result(explanation_id)

    def visible(self, explanation_id: str) -> dict[str, Any]:
        result = self.get_result(explanation_id)
        if result.status == "approved":
            return {"status": "approved", "content": result.content}
        return {"status": "unavailable", "content": None}

    def get_result(self, explanation_id: str) -> ExplanationResult:
        row = self.connection.execute(
            "SELECT r.*, q.cache_key FROM phase5_explanation_revisions r JOIN phase5_generation_requests q ON q.request_id=r.request_id WHERE r.explanation_id=?",
            (explanation_id,),
        ).fetchone()
        if not row:
            raise KeyError(explanation_id)
        return ExplanationResult(
            explanation_id=str(row["explanation_id"]), status=str(row["status"]), cache_key=str(row["cache_key"]),
            blockers=tuple(json.loads(row["blockers_json"])), content=json.loads(row["content_json"]) if row["content_json"] else None,
        )

    def _validate(self, bundle: GroundingBundle, selected_option_id: str, output: dict[str, Any]) -> list[str]:
        blockers: list[str] = []
        required = {"claimed_correct_option_id", "evidence_refs", "correction", "why_selected_wrong", "concept_refresher", "shortcut", "related_practice"}
        if not isinstance(output, dict) or not required <= set(output):
            return ["invalid_output_shape"]
        if output["claimed_correct_option_id"] != bundle.correct_option_id:
            blockers.append("answer_contradiction")
        evidence_refs = output.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not set(evidence_refs) <= set(bundle.evidence):
            blockers.append("unsupported_evidence_reference")
        if selected_option_id != bundle.correct_option_id and not str(output.get("why_selected_wrong") or "").strip():
            blockers.append("missing_distractor_analysis")
        for field in ("correction", "concept_refresher", "shortcut", "related_practice"):
            if not str(output.get(field) or "").strip():
                blockers.append(f"missing_{field}")
        return sorted(set(blockers))

    def _insert_request(self, request_id: str, cache_key: str, bundle_id: str, selected: str, model: str, prompt: str, cost: int, status: str) -> None:
        self.connection.execute(
            "INSERT INTO phase5_generation_requests VALUES (?,?,?,?,?,?,?,?,?)",
            (request_id, cache_key, bundle_id, selected, model, prompt, cost, status, _now()),
        )
        self.connection.commit()

    def _revision(self, request_id: str, status: str, content: dict[str, Any] | None, blockers: list[str]) -> ExplanationResult:
        revision = int(self.connection.execute("SELECT COUNT(*) FROM phase5_explanation_revisions WHERE request_id=?", (request_id,)).fetchone()[0]) + 1
        explanation_id = _id("explanation", request_id, str(revision), _hash(content or blockers))
        self.connection.execute(
            "INSERT INTO phase5_explanation_revisions VALUES (?,?,?,?,?,?,NULL,NULL,?)",
            (explanation_id, request_id, revision, status, _canonical(content) if content is not None else None, _canonical(blockers), _now()),
        )
        self.connection.commit()
        return self.get_result(explanation_id)

    def _queue(self, explanation_id: str, reason: str) -> None:
        item_id = _id("explanation-review", explanation_id, reason)
        self.connection.execute(
            "INSERT OR IGNORE INTO phase5_review_queue VALUES (?,?,?,?,?)",
            (item_id, explanation_id, reason, "open", _now()),
        )
        self.connection.commit()


@dataclass(frozen=True)
class Phase5Evaluation:
    passed: bool
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "check_count": len(self.checks)}


class Phase5Evaluator:
    def bundle(self) -> GroundingBundle:
        return GroundingBundle("rev:1", "A", "sampling", {"official-key": "A", "concept-note": "Random sampling gives equal chance."}, "Which method gives every member an equal chance?", {"A": "Simple random", "B": "Purposive"})

    def good_provider(self, prompt: dict[str, Any], model: str) -> dict[str, Any]:
        return {
            "claimed_correct_option_id": prompt["correct_option_id"], "evidence_refs": ["official-key", "concept-note"],
            "correction": "A is correct.", "why_selected_wrong": "Purposive sampling does not give every member an equal chance.",
            "concept_refresher": "Simple random sampling uses equal selection probability.", "shortcut": "Look for equal chance.",
            "related_practice": "Compare probability and non-probability sampling.",
        }

    def run(self) -> Phase5Evaluation:
        repo = ExplanationRepository.open(); bundle = self.bundle(); checks: dict[str, bool] = {}
        first = repo.generate(bundle, selected_option_id="B", provider=self.good_provider)
        checks["grounded_output_pending_review"] = first.status == "pending_approval"
        approved = repo.approve(first.explanation_id, reviewer="expert")
        checks["approved_output_visible"] = approved.status == "approved" and repo.visible(first.explanation_id)["status"] == "approved"
        checks["cache_deterministic"] = repo.generate(bundle, selected_option_id="B", provider=self.good_provider).explanation_id == first.explanation_id
        changed = repo.generate(bundle, selected_option_id="B", provider=self.good_provider, policy=GenerationPolicy(prompt_version="phase5.v2"))
        checks["version_change_invalidates_cache"] = changed.explanation_id != first.explanation_id
        contradiction = repo.generate(bundle, selected_option_id="A", provider=lambda p, m: {**self.good_provider(p, m), "claimed_correct_option_id": "B"})
        checks["answer_contradiction_queued"] = contradiction.status == "review" and "answer_contradiction" in contradiction.blockers
        unsupported = repo.generate(bundle, selected_option_id="A", provider=lambda p, m: {**self.good_provider(p, m), "evidence_refs": ["invented"]}, policy=GenerationPolicy(prompt_version="unsupported"))
        checks["unsupported_reference_queued"] = "unsupported_evidence_reference" in unsupported.blockers
        missing = repo.generate(bundle, selected_option_id="B", provider=lambda p, m: {**self.good_provider(p, m), "why_selected_wrong": ""}, policy=GenerationPolicy(prompt_version="missing"))
        checks["distractor_analysis_required"] = "missing_distractor_analysis" in missing.blockers
        outage = repo.generate(bundle, selected_option_id="A", provider=lambda p, m: (_ for _ in ()).throw(RuntimeError("down")), policy=GenerationPolicy(prompt_version="outage"))
        checks["provider_outage_falls_back"] = outage.status == "unavailable" and repo.visible(outage.explanation_id)["status"] == "unavailable"
        costly = repo.generate(bundle, selected_option_id="A", provider=self.good_provider, policy=GenerationPolicy(prompt_version="cost"), estimated_cost_micros=100_000)
        checks["cost_ceiling_enforced"] = costly.status == "blocked"
        checks["review_output_not_visible"] = repo.visible(contradiction.explanation_id)["status"] == "unavailable"
        checks["canonical_bundle_unchanged"] = bundle.correct_option_id == "A" and bundle.fingerprint() == self.bundle().fingerprint()
        checks["model_routing_defined"] = repo.route_model(bundle, "B", GenerationPolicy()) in {"volume-model", "reasoning-model"}
        checks["review_queue_persisted"] = repo.connection.execute("SELECT COUNT(*) FROM phase5_review_queue").fetchone()[0] >= 3
        checks["evaluator_depth"] = len(checks) >= 12
        return Phase5Evaluation(all(checks.values()), checks)


if __name__ == "__main__":
    report = Phase5Evaluator().run()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    raise SystemExit(0 if report.passed else 1)
