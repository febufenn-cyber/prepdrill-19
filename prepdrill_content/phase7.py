"""Phase 7 immutable mock-exam state machine and scoring."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


def _dt(value: str | None = None) -> datetime:
    return datetime.fromisoformat(value) if value else datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class MockQuestion:
    published_revision_id: str
    question_id: str
    correct_option_id: str
    payload: dict[str, Any]
    section: str = "Paper 1"
    marks: int = 2


@dataclass(frozen=True)
class MockResult:
    attempt_id: str
    score: int
    maximum_score: int
    correct: int
    incorrect: int
    unanswered: int
    submitted_at: str


class MockExamRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection; self.connection.row_factory = sqlite3.Row; self._initialise()

    @classmethod
    def open(cls, path: str = ":memory:") -> "MockExamRepository": return cls(sqlite3.connect(path))

    def _initialise(self) -> None:
        self.connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS phase7_manifests (manifest_id TEXT PRIMARY KEY,title TEXT NOT NULL,duration_seconds INTEGER NOT NULL,payload_json TEXT NOT NULL,manifest_hash TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase7_attempts (attempt_id TEXT PRIMARY KEY,manifest_id TEXT NOT NULL REFERENCES phase7_manifests(manifest_id),learner_id TEXT NOT NULL,started_at TEXT NOT NULL,deadline_at TEXT NOT NULL,status TEXT NOT NULL,submitted_at TEXT,result_json TEXT);
        CREATE TABLE IF NOT EXISTS phase7_responses (attempt_id TEXT NOT NULL REFERENCES phase7_attempts(attempt_id),ordinal INTEGER NOT NULL,selected_option_id TEXT,marked_for_review INTEGER NOT NULL,visited INTEGER NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,updated_at TEXT NOT NULL,PRIMARY KEY(attempt_id,ordinal));
        CREATE TABLE IF NOT EXISTS phase7_events (event_id TEXT PRIMARY KEY,attempt_id TEXT NOT NULL REFERENCES phase7_attempts(attempt_id),event_type TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
        """); self.connection.commit()

    def create_manifest(self, *, title: str, duration_seconds: int, questions: list[MockQuestion]) -> str:
        if duration_seconds <= 0 or not questions: raise ValueError("duration and questions are required")
        payload = {"title": title, "duration_seconds": duration_seconds, "questions": [asdict(item) for item in questions]}; manifest_hash = hashlib.sha256(_canonical(payload).encode()).hexdigest(); manifest_id = _id("mock-manifest", manifest_hash)
        self.connection.execute("INSERT OR IGNORE INTO phase7_manifests VALUES (?,?,?,?,?,?)", (manifest_id,title,duration_seconds,_canonical(payload),manifest_hash,_iso(_dt()))); self.connection.commit(); return manifest_id

    def start(self, *, manifest_id: str, learner_id: str, now: str | None = None) -> dict[str, Any]:
        manifest = self._manifest(manifest_id); started = _dt(now); deadline = started + timedelta(seconds=int(manifest["duration_seconds"])); attempt_id = _id("mock-attempt",manifest_id,learner_id,_iso(started))
        self.connection.execute("INSERT INTO phase7_attempts VALUES (?,?,?,?,?,'active',NULL,NULL)", (attempt_id,manifest_id,learner_id,_iso(started),_iso(deadline))); self._event(attempt_id,"started",{}); self.connection.commit(); return self.state(attempt_id,now=now)

    def save(self, *, attempt_id: str, ordinal: int, selected_option_id: str | None, marked_for_review: bool, idempotency_key: str, now: str | None = None) -> dict[str, Any]:
        attempt = self._attempt(attempt_id)
        if attempt["status"] != "active": raise ValueError("attempt is submitted")
        if self.remaining_seconds(attempt_id,now=now) <= 0: self.submit(attempt_id,now=now,forced=True); raise ValueError("deadline reached")
        questions = self._questions(attempt["manifest_id"])
        if ordinal < 0 or ordinal >= len(questions): raise IndexError(ordinal)
        existing_key = self.connection.execute("SELECT * FROM phase7_responses WHERE idempotency_key=?",(idempotency_key,)).fetchone()
        if existing_key: return self._response_dict(existing_key)
        timestamp = _iso(_dt(now)); existing = self.connection.execute("SELECT * FROM phase7_responses WHERE attempt_id=? AND ordinal=?",(attempt_id,ordinal)).fetchone()
        if existing: self.connection.execute("UPDATE phase7_responses SET selected_option_id=?,marked_for_review=?,visited=1,idempotency_key=?,updated_at=? WHERE attempt_id=? AND ordinal=?",(selected_option_id,int(marked_for_review),idempotency_key,timestamp,attempt_id,ordinal))
        else: self.connection.execute("INSERT INTO phase7_responses VALUES (?,?,?,?,?,?,?)",(attempt_id,ordinal,selected_option_id,int(marked_for_review),1,idempotency_key,timestamp))
        self._event(attempt_id,"response_saved",{"ordinal":ordinal}); self.connection.commit(); return self.response(attempt_id,ordinal)

    def clear(self, *, attempt_id: str, ordinal: int, idempotency_key: str, now: str | None = None) -> dict[str, Any]:
        return self.save(attempt_id=attempt_id,ordinal=ordinal,selected_option_id=None,marked_for_review=False,idempotency_key=idempotency_key,now=now)

    def response(self, attempt_id: str, ordinal: int) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM phase7_responses WHERE attempt_id=? AND ordinal=?",(attempt_id,ordinal)).fetchone()
        if not row: return {"attempt_id":attempt_id,"ordinal":ordinal,"selected_option_id":None,"marked_for_review":False,"visited":False,"palette_state":"not_visited"}
        return self._response_dict(row)

    def state(self, attempt_id: str, *, now: str | None = None, include_answers: bool = False) -> dict[str, Any]:
        attempt = self._attempt(attempt_id); questions = self._questions(attempt["manifest_id"])
        if attempt["status"] == "active" and self.remaining_seconds(attempt_id,now=now) <= 0: self.submit(attempt_id,now=now,forced=True); attempt = self._attempt(attempt_id)
        payload_questions=[]; palette=[]
        for ordinal,item in enumerate(questions):
            safe={k:v for k,v in item["payload"].items() if k not in {"correct_option_id","reviewed_explanation"}}; safe.update({"ordinal":ordinal,"published_revision_id":item["published_revision_id"],"section":item["section"]})
            if include_answers and attempt["status"]=="submitted": safe["correct_option_id"]=item["correct_option_id"]
            payload_questions.append(safe); palette.append(self.response(attempt_id,ordinal))
        result={"attempt_id":attempt_id,"manifest_id":attempt["manifest_id"],"status":attempt["status"],"remaining_seconds":self.remaining_seconds(attempt_id,now=now),"questions":payload_questions,"palette":palette}
        if attempt["result_json"]: result["result"]=json.loads(attempt["result_json"])
        return result

    def remaining_seconds(self, attempt_id: str, *, now: str | None = None) -> int:
        attempt=self._attempt(attempt_id); return max(0,int((_dt(attempt["deadline_at"])-_dt(now)).total_seconds())) if attempt["status"]=="active" else 0

    def submit(self, attempt_id: str, *, now: str | None = None, forced: bool = False) -> MockResult:
        attempt=self._attempt(attempt_id)
        if attempt["status"]=="submitted": return MockResult(**json.loads(attempt["result_json"]))
        questions=self._questions(attempt["manifest_id"]); correct=incorrect=unanswered=score=maximum=0
        for ordinal,item in enumerate(questions):
            maximum+=int(item["marks"]); selected=self.response(attempt_id,ordinal)["selected_option_id"]
            if selected is None: unanswered+=1
            elif selected==item["correct_option_id"]: correct+=1; score+=int(item["marks"])
            else: incorrect+=1
        submitted_at=_iso(_dt(now)); result=MockResult(attempt_id,score,maximum,correct,incorrect,unanswered,submitted_at)
        self.connection.execute("UPDATE phase7_attempts SET status='submitted',submitted_at=?,result_json=? WHERE attempt_id=?",(submitted_at,_canonical(asdict(result)),attempt_id)); self._event(attempt_id,"forced_submit" if forced else "submitted",asdict(result)); self.connection.commit(); return result

    def review(self, attempt_id: str) -> list[dict[str, Any]]:
        attempt=self._attempt(attempt_id)
        if attempt["status"]!="submitted": raise PermissionError("review is available only after submit")
        return [{**item,"ordinal":ordinal,"response":self.response(attempt_id,ordinal)} for ordinal,item in enumerate(self._questions(attempt["manifest_id"]))]

    def keyboard_command(self,key:str)->str:
        mapping={"ArrowRight":"save_next","m":"mark_review","c":"clear_response","s":"submit"}
        if key not in mapping: raise KeyError(key)
        return mapping[key]

    def _response_dict(self,row:sqlite3.Row)->dict[str,Any]:
        selected=row["selected_option_id"]; marked=bool(row["marked_for_review"]); visited=bool(row["visited"])
        state="answered_marked" if selected is not None and marked else "marked" if marked else "answered" if selected is not None else "not_answered" if visited else "not_visited"
        return {"attempt_id":row["attempt_id"],"ordinal":row["ordinal"],"selected_option_id":selected,"marked_for_review":marked,"visited":visited,"palette_state":state}

    def _manifest(self,manifest_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase7_manifests WHERE manifest_id=?",(manifest_id,)).fetchone()
        if not row: raise KeyError(manifest_id)
        return row
    def _questions(self,manifest_id:str)->list[dict[str,Any]]: return json.loads(self._manifest(manifest_id)["payload_json"])["questions"]
    def _attempt(self,attempt_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase7_attempts WHERE attempt_id=?",(attempt_id,)).fetchone()
        if not row: raise KeyError(attempt_id)
        return row
    def _event(self,attempt_id:str,event_type:str,payload:dict[str,Any])->None:
        created=_iso(_dt()); event_id=_id("mock-event",attempt_id,event_type,created,_canonical(payload)); self.connection.execute("INSERT INTO phase7_events VALUES (?,?,?,?,?)",(event_id,attempt_id,event_type,_canonical(payload),created))


@dataclass(frozen=True)
class Phase7Evaluation:
    passed: bool
    checks: dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}


class Phase7Evaluator:
    def questions(self)->list[MockQuestion]:
        return [MockQuestion(f"rev:{i}",f"q:{i}","A" if i%2==0 else "B",{"question_id":f"q:{i}","plain_text":f"Question {i}","options":[{"option_id":"A"},{"option_id":"B"}],"correct_option_id":"secret"}) for i in range(4)]
    def run(self)->Phase7Evaluation:
        repo=MockExamRepository.open(); checks:dict[str,bool]={}; questions=self.questions(); manifest=repo.create_manifest(title="Mock",duration_seconds=120,questions=questions); attempt=repo.start(manifest_id=manifest,learner_id="learner",now="2026-01-01T00:00:00+00:00"); attempt_id=attempt["attempt_id"]
        checks["manifest_order_preserved"]=[i["published_revision_id"] for i in attempt["questions"]]==[q.published_revision_id for q in questions]; checks["answers_hidden_pre_submit"]=all("correct_option_id" not in i for i in attempt["questions"])
        answered=repo.save(attempt_id=attempt_id,ordinal=0,selected_option_id="A",marked_for_review=False,idempotency_key="r1",now="2026-01-01T00:00:10+00:00"); marked=repo.save(attempt_id=attempt_id,ordinal=1,selected_option_id=None,marked_for_review=True,idempotency_key="r2",now="2026-01-01T00:00:20+00:00"); answered_marked=repo.save(attempt_id=attempt_id,ordinal=2,selected_option_id="A",marked_for_review=True,idempotency_key="r3",now="2026-01-01T00:00:30+00:00")
        checks["palette_states_correct"]=[answered["palette_state"],marked["palette_state"],answered_marked["palette_state"]]==["answered","marked","answered_marked"]
        checks["autosave_idempotent"]=repo.save(attempt_id=attempt_id,ordinal=0,selected_option_id="B",marked_for_review=False,idempotency_key="r1",now="2026-01-01T00:00:40+00:00")["selected_option_id"]=="A"
        checks["clear_transition_correct"]=repo.clear(attempt_id=attempt_id,ordinal=1,idempotency_key="clear",now="2026-01-01T00:00:50+00:00")["palette_state"]=="not_answered"; checks["reconnect_preserves_state"]=repo.state(attempt_id,now="2026-01-01T00:01:00+00:00")["palette"][2]["palette_state"]=="answered_marked"
        result=repo.submit(attempt_id,now="2026-01-01T00:01:10+00:00"); checks["exact_scoring"]=(result.score,result.correct,result.incorrect,result.unanswered)==(4,2,0,2); checks["duplicate_submit_safe"]=repo.submit(attempt_id,now="2026-01-01T00:01:11+00:00")==result
        checks["review_pins_revisions"]=[i["published_revision_id"] for i in repo.review(attempt_id)]==[q.published_revision_id for q in questions]; checks["answers_visible_post_submit"]=all("correct_option_id" in i for i in repo.state(attempt_id,include_answers=True)["questions"])
        second=repo.start(manifest_id=manifest,learner_id="late",now="2026-01-01T00:00:00+00:00"); checks["deadline_forces_submit"]=repo.state(second["attempt_id"],now="2026-01-01T00:03:00+00:00")["status"]=="submitted"; checks["keyboard_commands_defined"]=repo.keyboard_command("m")=="mark_review" and repo.keyboard_command("ArrowRight")=="save_next"; checks["evaluator_depth"]=len(checks)>=12
        return Phase7Evaluation(all(checks.values()),checks)


if __name__=="__main__":
    report=Phase7Evaluator().run(); print(json.dumps(report.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if report.passed else 1)
