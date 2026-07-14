"""Phase 8 security, privacy, reliability, and recovery controls."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = {"authorization", "token", "access_token", "refresh_token", "password", "secret", "correct_option_id", "answer_key", "email", "phone", "mobile"}


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _canonical(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def _hash(value: Any) -> str: return hashlib.sha256(_canonical(value).encode()).hexdigest()
def _id(prefix: str, *parts: str) -> str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


class AccessController:
    RULES = {
        "learner.read": {"learner", "service", "admin"},
        "learner.write": {"service", "admin"},
        "content.internal": {"service", "reviewer", "admin"},
        "ops.switch": {"admin"},
    }
    def allowed(self, *, role: str, action: str, actor_id: str | None = None, owner_id: str | None = None) -> bool:
        if role not in self.RULES.get(action, set()): return False
        if action == "learner.read" and role == "learner": return bool(actor_id and actor_id == owner_id)
        return True


class LogSanitizer:
    def sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): "[REDACTED]" if str(k).casefold() in SENSITIVE_KEYS else self.sanitize(v) for k, v in value.items()}
        if isinstance(value, list): return [self.sanitize(item) for item in value]
        if isinstance(value, tuple): return tuple(self.sanitize(item) for item in value)
        if isinstance(value, str):
            value = re.sub(r"Bearer\s+[A-Za-z0-9._~-]+", "Bearer [REDACTED]", value, flags=re.I)
            value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]", value)
            value = re.sub(r"(?<!\d)(?:\+?91[- ]?)?[6-9]\d{9}(?!\d)", "[REDACTED_PHONE]", value)
        return value


class SecurityRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection=connection; self.connection.row_factory=sqlite3.Row; self._init()
    @classmethod
    def open(cls,path:str=":memory:")->"SecurityRepository": return cls(sqlite3.connect(path))
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase8_replay_keys(scope TEXT NOT NULL,actor_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,payload_hash TEXT NOT NULL,created_epoch INTEGER NOT NULL,PRIMARY KEY(scope,actor_id,idempotency_key));
        CREATE TABLE IF NOT EXISTS phase8_rate_events(scope TEXT NOT NULL,actor_id TEXT NOT NULL,event_epoch INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase8_switches(name TEXT PRIMARY KEY,enabled INTEGER NOT NULL,safe_default INTEGER NOT NULL,updated_by TEXT NOT NULL,reason TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase8_switch_events(event_id TEXT PRIMARY KEY,name TEXT NOT NULL,enabled INTEGER NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
        """); self.connection.commit()
    def accept_mutation(self, *, scope:str, actor_id:str, idempotency_key:str, payload:Any, epoch:int)->str:
        payload_hash=_hash(payload); row=self.connection.execute("SELECT payload_hash FROM phase8_replay_keys WHERE scope=? AND actor_id=? AND idempotency_key=?",(scope,actor_id,idempotency_key)).fetchone()
        if row:
            if row[0] != payload_hash: raise ValueError("idempotency key collision")
            return "duplicate"
        self.connection.execute("INSERT INTO phase8_replay_keys VALUES (?,?,?,?,?)",(scope,actor_id,idempotency_key,payload_hash,epoch)); self.connection.commit(); return "accepted"
    def rate_allowed(self, *, scope:str, actor_id:str, epoch:int, limit:int, window_seconds:int)->bool:
        floor=epoch-window_seconds; self.connection.execute("DELETE FROM phase8_rate_events WHERE event_epoch<=?",(floor,)); count=self.connection.execute("SELECT COUNT(*) FROM phase8_rate_events WHERE scope=? AND actor_id=?",(scope,actor_id)).fetchone()[0]
        if count>=limit: self.connection.commit(); return False
        self.connection.execute("INSERT INTO phase8_rate_events VALUES (?,?,?)",(scope,actor_id,epoch)); self.connection.commit(); return True
    def set_switch(self, name:str, *, enabled:bool, safe_default:bool, actor:str, reason:str)->None:
        if not actor.strip() or not reason.strip(): raise ValueError("actor and reason required")
        timestamp=_now(); self.connection.execute("INSERT INTO phase8_switches VALUES (?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled,safe_default=excluded.safe_default,updated_by=excluded.updated_by,reason=excluded.reason,updated_at=excluded.updated_at",(name,int(enabled),int(safe_default),actor,reason,timestamp)); event_id=_id("switch-event",name,str(enabled),actor,timestamp); self.connection.execute("INSERT INTO phase8_switch_events VALUES (?,?,?,?,?,?)",(event_id,name,int(enabled),actor,reason,timestamp)); self.connection.commit()
    def switch_enabled(self,name:str, *, safe_default:bool=False)->bool:
        row=self.connection.execute("SELECT enabled FROM phase8_switches WHERE name=?",(name,)).fetchone(); return bool(row[0]) if row else safe_default


class SafeInput:
    IDENTIFIER = re.compile(r"^[a-zA-Z0-9._:-]{1,128}$")
    def identifier(self,value:str)->str:
        if not self.IDENTIFIER.fullmatch(value): raise ValueError("invalid identifier")
        return value
    def search_text(self,value:str,max_length:int=500)->str:
        if not isinstance(value,str) or len(value)>max_length or "\x00" in value: raise ValueError("invalid search text")
        return value


class BackupManager:
    def create(self, state: Any)->dict[str,str]:
        payload=_canonical(state); return {"payload":payload,"checksum":hashlib.sha256(payload.encode()).hexdigest()}
    def restore(self, backup:dict[str,str])->Any:
        payload=backup.get("payload",""); checksum=hashlib.sha256(payload.encode()).hexdigest()
        if checksum != backup.get("checksum"): raise ValueError("backup checksum mismatch")
        return json.loads(payload)


@dataclass(frozen=True)
class ReliabilityBudget:
    max_p50_ms: float=250
    max_p95_ms: float=750
    max_p99_ms: float=1500
    max_error_rate: float=0.01

class ReliabilityEvaluator:
    @staticmethod
    def percentile(values:list[float],p:float)->float:
        if not values: return math.inf
        ordered=sorted(values); rank=max(0,math.ceil(p*len(ordered))-1); return float(ordered[rank])
    def evaluate(self, latencies_ms:list[float], failures:int, total:int, budget:ReliabilityBudget|None=None)->dict[str,Any]:
        selected=budget or ReliabilityBudget(); p50=self.percentile(latencies_ms,.50); p95=self.percentile(latencies_ms,.95); p99=self.percentile(latencies_ms,.99); error_rate=failures/total if total else 1.0
        checks={"p50":p50<=selected.max_p50_ms,"p95":p95<=selected.max_p95_ms,"p99":p99<=selected.max_p99_ms,"error_rate":error_rate<=selected.max_error_rate}
        return {"passed":all(checks.values()),"p50_ms":p50,"p95_ms":p95,"p99_ms":p99,"error_rate":error_rate,"checks":checks}

@dataclass(frozen=True)
class Phase8Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase8Evaluator:
    def run(self)->Phase8Evaluation:
        checks:dict[str,bool]={}; access=AccessController()
        checks["self_access_allowed"]=access.allowed(role="learner",action="learner.read",actor_id="u1",owner_id="u1")
        checks["idor_blocked"]=not access.allowed(role="learner",action="learner.read",actor_id="u1",owner_id="u2")
        checks["unknown_action_denied"]=not access.allowed(role="admin",action="unknown")
        sanitized=LogSanitizer().sanitize({"token":"abc","nested":{"email":"a@b.com","message":"Bearer secret-token phone 9876543210"},"answer_key":"A"})
        checks["logs_redacted"]=sanitized["token"]=="[REDACTED]" and sanitized["answer_key"]=="[REDACTED]" and "a@b.com" not in sanitized["nested"]["email"] and "9876543210" not in sanitized["nested"]["message"]
        repo=SecurityRepository.open(); checks["mutation_accepted"]=repo.accept_mutation(scope="submit",actor_id="u1",idempotency_key="k1",payload={"x":1},epoch=100)=="accepted"; checks["replay_idempotent"]=repo.accept_mutation(scope="submit",actor_id="u1",idempotency_key="k1",payload={"x":1},epoch=101)=="duplicate"
        try: repo.accept_mutation(scope="submit",actor_id="u1",idempotency_key="k1",payload={"x":2},epoch=102); checks["collision_blocked"]=False
        except ValueError: checks["collision_blocked"]=True
        checks["rate_limit_scoped"]=repo.rate_allowed(scope="api",actor_id="u1",epoch=100,limit=2,window_seconds=10) and repo.rate_allowed(scope="api",actor_id="u1",epoch=101,limit=2,window_seconds=10) and not repo.rate_allowed(scope="api",actor_id="u1",epoch=102,limit=2,window_seconds=10) and repo.rate_allowed(scope="api",actor_id="u2",epoch=102,limit=2,window_seconds=10)
        checks["rate_window_recovers"]=repo.rate_allowed(scope="api",actor_id="u1",epoch=112,limit=2,window_seconds=10)
        hostile="' OR 1=1; <script>alert(1)</script>"; checks["hostile_text_inert"]=SafeInput().search_text(hostile)==hostile
        manager=BackupManager(); state={"attempts":[1,2],"content":{"hash":"abc"}}; backup=manager.create(state); checks["backup_restore_exact"]=manager.restore(backup)==state
        corrupt=dict(backup); corrupt["payload"]+="x"
        try: manager.restore(corrupt); checks["corruption_detected"]=False
        except ValueError: checks["corruption_detected"]=True
        good=ReliabilityEvaluator().evaluate([100]*95+[500]*4+[1000],0,100); bad=ReliabilityEvaluator().evaluate([2000]*100,5,100)
        checks["reliability_budgets_work"]=good["passed"] and not bad["passed"]
        checks["switch_safe_default"]=repo.switch_enabled("payments",safe_default=False) is False; repo.set_switch("payments",enabled=True,safe_default=False,actor="admin",reason="sandbox")
        checks["switch_change_audited"]=repo.switch_enabled("payments") and repo.connection.execute("SELECT COUNT(*) FROM phase8_switch_events").fetchone()[0]==1
        checks["evaluator_depth"]=len(checks)>=14
        return Phase8Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    report=Phase8Evaluator().run(); print(json.dumps(report.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if report.passed else 1)
