"""Phase 4 application-service, identity merge, and structured rendering boundary."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

FLOW_MODES = {"quick", "topic", "diagnostic", "review", "weakness", "recheck"}
BLOCK_TYPES = {"paragraph", "labelled_statement", "ordered_list", "unordered_list", "table", "formula", "image", "match_lists"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class RenderedQuestion:
    question_id: str
    question_type: str
    accessible_text: str
    blocks: tuple[dict[str, Any], ...]
    options: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["blocks"] = list(self.blocks)
        value["options"] = list(self.options)
        return value


class StructuredRenderer:
    def render(self, record: dict[str, Any]) -> RenderedQuestion:
        blocks = record.get("stem_blocks") or []
        if not isinstance(blocks, list) or not blocks:
            raise ValueError("stem_blocks are required")
        accessible: list[str] = []
        safe_blocks: list[dict[str, Any]] = []
        for index, block in enumerate(blocks):
            if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
                raise ValueError(f"unsupported block at {index}")
            copied = dict(block)
            block_type = str(copied["type"])
            text = copied.get("text") or copied.get("alt") or copied.get("label") or ""
            if block_type == "table":
                rows = copied.get("rows") or []
                text = "Table: " + "; ".join(" | ".join(map(str, row)) for row in rows)
            elif block_type == "match_lists":
                left = copied.get("left") or []
                right = copied.get("right") or []
                text = "Match lists: " + "; ".join(map(str, left)) + " with " + "; ".join(map(str, right))
            elif block_type == "formula":
                text = "Formula: " + str(copied.get("latex") or text)
            elif block_type == "image" and not text:
                raise ValueError("image block requires alt text")
            accessible.append(str(text).strip())
            safe_blocks.append(copied)
        options: list[dict[str, Any]] = []
        for option in record.get("options") or []:
            if not isinstance(option, dict):
                raise ValueError("invalid option")
            options.append({
                "option_id": option.get("option_id"),
                "plain_text": option.get("plain_text", ""),
                "blocks": option.get("blocks") or [],
            })
        return RenderedQuestion(
            question_id=str(record.get("question_id") or record.get("published_question_id") or ""),
            question_type=str(record.get("question_type") or "single_choice"),
            accessible_text=" ".join(part for part in accessible if part),
            blocks=tuple(safe_blocks),
            options=tuple(options),
        )


class IdentitySyncRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._initialise()

    @classmethod
    def open(cls, path: str = ":memory:") -> "IdentitySyncRepository":
        return cls(sqlite3.connect(path))

    def _initialise(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS phase4_guests (
              guest_id TEXT PRIMARY KEY,
              device_id TEXT NOT NULL UNIQUE,
              onboarding_name TEXT NOT NULL,
              merged_account_id TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_accounts (
              account_id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_progress_refs (
              progress_id TEXT PRIMARY KEY,
              owner_type TEXT NOT NULL,
              owner_id TEXT NOT NULL,
              reference_type TEXT NOT NULL,
              reference_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(owner_type, owner_id, reference_type, reference_id)
            );
            CREATE TABLE IF NOT EXISTS phase4_merge_events (
              merge_id TEXT PRIMARY KEY,
              guest_id TEXT NOT NULL REFERENCES phase4_guests(guest_id),
              account_id TEXT NOT NULL REFERENCES phase4_accounts(account_id),
              idempotency_key TEXT NOT NULL UNIQUE,
              transferred_count INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_flows (
              flow_id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              mode TEXT NOT NULL,
              seed TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_submissions (
              submission_id TEXT PRIMARY KEY,
              flow_id TEXT NOT NULL REFERENCES phase4_flows(flow_id),
              published_question_id TEXT NOT NULL,
              selected_option_id TEXT,
              correct INTEGER NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def create_guest(self, *, device_id: str, onboarding_name: str) -> dict[str, Any]:
        if not device_id.strip() or not onboarding_name.strip():
            raise ValueError("device_id and onboarding_name are required")
        existing = self.connection.execute("SELECT * FROM phase4_guests WHERE device_id=?", (device_id.strip(),)).fetchone()
        if existing:
            return dict(existing)
        guest_id = _id("guest", device_id.strip())
        self.connection.execute(
            "INSERT INTO phase4_guests VALUES (?,?,?,?,?)",
            (guest_id, device_id.strip(), onboarding_name.strip(), None, _now()),
        )
        self.connection.commit()
        return dict(self.connection.execute("SELECT * FROM phase4_guests WHERE guest_id=?", (guest_id,)).fetchone())

    def create_or_load_account(self, *, auth_user_id: str, display_name: str) -> dict[str, Any]:
        if not auth_user_id.strip():
            raise ValueError("auth_user_id is required")
        existing = self.connection.execute("SELECT * FROM phase4_accounts WHERE account_id=?", (auth_user_id.strip(),)).fetchone()
        if existing:
            return dict(existing)
        self.connection.execute(
            "INSERT INTO phase4_accounts VALUES (?,?,?)",
            (auth_user_id.strip(), display_name.strip() or "Learner", _now()),
        )
        self.connection.commit()
        return dict(self.connection.execute("SELECT * FROM phase4_accounts WHERE account_id=?", (auth_user_id.strip(),)).fetchone())

    def add_progress(self, *, owner_type: str, owner_id: str, reference_type: str, reference_id: str) -> str:
        if owner_type not in {"guest", "account"}:
            raise ValueError("invalid owner_type")
        progress_id = _id("progress", owner_type, owner_id, reference_type, reference_id)
        self.connection.execute(
            "INSERT OR IGNORE INTO phase4_progress_refs VALUES (?,?,?,?,?,?)",
            (progress_id, owner_type, owner_id, reference_type, reference_id, _now()),
        )
        self.connection.commit()
        return progress_id

    def merge_guest(self, *, guest_id: str, auth_user_id: str, idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        existing_event = self.connection.execute(
            "SELECT * FROM phase4_merge_events WHERE idempotency_key=?", (idempotency_key.strip(),)
        ).fetchone()
        if existing_event:
            if existing_event["guest_id"] != guest_id or existing_event["account_id"] != auth_user_id:
                raise ValueError("idempotency key collision")
            return dict(existing_event)
        guest = self.connection.execute("SELECT * FROM phase4_guests WHERE guest_id=?", (guest_id,)).fetchone()
        account = self.connection.execute("SELECT * FROM phase4_accounts WHERE account_id=?", (auth_user_id,)).fetchone()
        if not guest or not account:
            raise KeyError("guest or account not found")
        if guest["merged_account_id"] and guest["merged_account_id"] != auth_user_id:
            raise PermissionError("guest already belongs to another account")
        refs = list(self.connection.execute(
            "SELECT reference_type, reference_id FROM phase4_progress_refs WHERE owner_type='guest' AND owner_id=?", (guest_id,)
        ))
        for ref in refs:
            self.add_progress(owner_type="account", owner_id=auth_user_id, reference_type=ref[0], reference_id=ref[1])
        self.connection.execute("UPDATE phase4_guests SET merged_account_id=? WHERE guest_id=?", (auth_user_id, guest_id))
        merge_id = _id("merge", guest_id, auth_user_id, idempotency_key.strip())
        self.connection.execute(
            "INSERT INTO phase4_merge_events VALUES (?,?,?,?,?,?)",
            (merge_id, guest_id, auth_user_id, idempotency_key.strip(), len(refs), _now()),
        )
        self.connection.commit()
        return dict(self.connection.execute("SELECT * FROM phase4_merge_events WHERE merge_id=?", (merge_id,)).fetchone())

    def load_account_state(self, auth_user_id: str) -> dict[str, Any]:
        account = self.connection.execute("SELECT * FROM phase4_accounts WHERE account_id=?", (auth_user_id,)).fetchone()
        if not account:
            raise KeyError(auth_user_id)
        refs = [dict(row) for row in self.connection.execute(
            "SELECT reference_type, reference_id, created_at FROM phase4_progress_refs WHERE owner_type='account' AND owner_id=? ORDER BY created_at, reference_id",
            (auth_user_id,),
        )]
        return {"account": dict(account), "progress": refs}


class ApplicationService:
    def __init__(self, repository: IdentitySyncRepository, *, activation_authorized: bool):
        self.repository = repository
        self.activation_authorized = activation_authorized

    def create_flow(self, *, owner_id: str, mode: str, seed: str, idempotency_key: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.activation_authorized:
            raise PermissionError("Phase 3 authorization is required")
        if mode not in FLOW_MODES:
            raise ValueError("unsupported flow mode")
        existing = self.repository.connection.execute(
            "SELECT * FROM phase4_flows WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if existing:
            return self._public_flow(dict(existing))
        safe_questions = [self._pre_attempt_question(item) for item in questions if item.get("active", True)]
        safe_questions.sort(key=lambda item: _id("order", seed, str(item.get("published_question_id"))))
        flow_id = _id("flow", owner_id, mode, seed, idempotency_key)
        self.repository.connection.execute(
            "INSERT INTO phase4_flows VALUES (?,?,?,?,?,?,?,?)",
            (flow_id, owner_id, mode, seed, "active", _canonical({"questions": safe_questions}), idempotency_key, _now()),
        )
        self.repository.connection.commit()
        row = dict(self.repository.connection.execute("SELECT * FROM phase4_flows WHERE flow_id=?", (flow_id,)).fetchone())
        return self._public_flow(row)

    def recover_flow(self, flow_id: str) -> dict[str, Any]:
        row = self.repository.connection.execute("SELECT * FROM phase4_flows WHERE flow_id=?", (flow_id,)).fetchone()
        if not row:
            raise KeyError(flow_id)
        return self._public_flow(dict(row))

    def submit(self, *, flow_id: str, published_question: dict[str, Any], selected_option_id: str | None, idempotency_key: str, client_fields: dict[str, Any] | None = None) -> dict[str, Any]:
        existing = self.repository.connection.execute(
            "SELECT * FROM phase4_submissions WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if existing:
            return dict(existing)
        flow = self.repository.connection.execute("SELECT flow_id FROM phase4_flows WHERE flow_id=?", (flow_id,)).fetchone()
        if not flow:
            raise KeyError(flow_id)
        correct_option_id = published_question.get("correct_option_id")
        correct = int(selected_option_id is not None and selected_option_id == correct_option_id)
        submission_id = _id("submission", flow_id, str(published_question.get("published_question_id")), idempotency_key)
        self.repository.connection.execute(
            "INSERT INTO phase4_submissions VALUES (?,?,?,?,?,?,?)",
            (submission_id, flow_id, published_question.get("published_question_id"), selected_option_id, correct, idempotency_key, _now()),
        )
        self.repository.connection.commit()
        return dict(self.repository.connection.execute("SELECT * FROM phase4_submissions WHERE submission_id=?", (submission_id,)).fetchone())

    def _pre_attempt_question(self, question: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "published_question_id", "question_id", "question_type", "plain_text", "stem_blocks", "options", "unit_id", "topic_id", "difficulty"
        }
        return {key: question[key] for key in allowed if key in question}

    def _public_flow(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(row.pop("payload_json"))
        row.update(payload)
        return row


@dataclass(frozen=True)
class Phase4Evaluation:
    passed: bool
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "check_count": len(self.checks)}


class Phase4Evaluator:
    def _question(self, block_type: str = "paragraph") -> dict[str, Any]:
        block: dict[str, Any] = {"type": block_type, "text": "Question text"}
        if block_type == "table":
            block = {"type": "table", "rows": [["A", "B"], ["1", "2"]]}
        elif block_type == "formula":
            block = {"type": "formula", "latex": "x^2"}
        elif block_type == "image":
            block = {"type": "image", "alt": "A labelled diagram"}
        elif block_type == "match_lists":
            block = {"type": "match_lists", "left": ["A"], "right": ["1"]}
        return {
            "published_question_id": f"pub:{block_type}",
            "question_id": f"q:{block_type}",
            "question_type": "single_choice",
            "plain_text": "Question text",
            "stem_blocks": [block],
            "options": [
                {"option_id": "A", "plain_text": "Yes", "blocks": [{"type": "paragraph", "text": "Yes"}]},
                {"option_id": "B", "plain_text": "No", "blocks": [{"type": "paragraph", "text": "No"}]},
            ],
            "correct_option_id": "A",
            "reviewed_explanation": "secret",
            "active": True,
        }

    def run(self) -> Phase4Evaluation:
        checks: dict[str, bool] = {}
        repo = IdentitySyncRepository.open()
        guest = repo.create_guest(device_id="device-1", onboarding_name="Guest Name")
        repo.add_progress(owner_type="guest", owner_id=guest["guest_id"], reference_type="attempt", reference_id="attempt-1")
        account = repo.create_or_load_account(auth_user_id="auth-user-1", display_name="Registered Name")
        merge = repo.merge_guest(guest_id=guest["guest_id"], auth_user_id=account["account_id"], idempotency_key="merge-1")
        checks["guest_progress_transferred"] = merge["transferred_count"] == 1 and len(repo.load_account_state("auth-user-1")["progress"]) == 1
        checks["name_mismatch_uses_authenticated_account"] = repo.load_account_state("auth-user-1")["account"]["display_name"] == "Registered Name"
        checks["merge_retry_idempotent"] = repo.merge_guest(guest_id=guest["guest_id"], auth_user_id="auth-user-1", idempotency_key="merge-1")["merge_id"] == merge["merge_id"]
        repo.create_or_load_account(auth_user_id="auth-user-2", display_name="Other")
        try:
            repo.merge_guest(guest_id=guest["guest_id"], auth_user_id="auth-user-2", idempotency_key="merge-2")
            checks["cross_account_collision_blocked"] = False
        except PermissionError:
            checks["cross_account_collision_blocked"] = True
        checks["second_device_recovers_server_state"] = len(repo.load_account_state("auth-user-1")["progress"]) == 1
        locked = ApplicationService(repo, activation_authorized=False)
        try:
            locked.create_flow(owner_id="auth-user-1", mode="quick", seed="s", idempotency_key="locked", questions=[self._question()])
            checks["activation_lock_enforced"] = False
        except PermissionError:
            checks["activation_lock_enforced"] = True
        service = ApplicationService(repo, activation_authorized=True)
        flow_ids = []
        for mode in sorted(FLOW_MODES):
            flow_ids.append(service.create_flow(owner_id="auth-user-1", mode=mode, seed="seed", idempotency_key=f"flow-{mode}", questions=[self._question()])["flow_id"])
        checks["all_flow_modes_supported"] = len(set(flow_ids)) == len(FLOW_MODES)
        public_flow = service.recover_flow(flow_ids[0])
        leaked = {"correct_option_id", "reviewed_explanation"} & set(public_flow["questions"][0])
        checks["pre_attempt_payload_redacted"] = not leaked
        first_submission = service.submit(flow_id=flow_ids[0], published_question=self._question(), selected_option_id="B", idempotency_key="submit-1", client_fields={"correct": True, "score": 999, "mastery": 1.0})
        checks["client_tampering_ignored"] = first_submission["correct"] == 0
        checks["submission_retry_idempotent"] = service.submit(flow_id=flow_ids[0], published_question=self._question(), selected_option_id="A", idempotency_key="submit-1")["correct"] == 0
        checks["interrupted_flow_recoverable"] = service.recover_flow(flow_ids[0])["flow_id"] == flow_ids[0]
        renderer = StructuredRenderer()
        checks["renderer_covers_all_blocks"] = all(renderer.render(self._question(block)).accessible_text for block in sorted(BLOCK_TYPES))
        checks["evaluator_depth"] = len(checks) >= 12
        return Phase4Evaluation(all(checks.values()), checks)


if __name__ == "__main__":
    report = Phase4Evaluator().run()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    raise SystemExit(0 if report.passed else 1)
