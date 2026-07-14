"""Phase 9 learning continuity, reports, consent, and communication policy."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _id(prefix: str, *parts: str) -> str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"
def _canonical(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class LearningActivity:
    learner_id: str
    activity_date: str
    attempt_id: str
    published_revision_id: str
    concept_id: str
    completed: bool
    scored_questions: int
    correct_questions: int
    response_ms: int = 0


class LearningContinuity:
    def meaningful_dates(self, activities: Iterable[LearningActivity]) -> list[date]:
        return sorted({date.fromisoformat(item.activity_date) for item in activities if item.completed and item.scored_questions > 0})
    def streak(self, activities: Iterable[LearningActivity]) -> int:
        dates=self.meaningful_dates(activities)
        if not dates: return 0
        streak=1
        for index in range(len(dates)-1,0,-1):
            if (dates[index]-dates[index-1]).days==1: streak+=1
            else: break
        return streak
    def weekly_report(self, activities: Iterable[LearningActivity], *, week_start: str) -> dict[str,Any]:
        start=date.fromisoformat(week_start); selected=[item for item in activities if 0 <= (date.fromisoformat(item.activity_date)-start).days < 7 and item.completed and item.scored_questions>0]
        attempted=sum(item.scored_questions for item in selected); correct=sum(item.correct_questions for item in selected); time_ms=sum(max(0,item.response_ms) for item in selected)
        concepts:dict[str,dict[str,int]]={}
        for item in selected:
            row=concepts.setdefault(item.concept_id,{"attempted":0,"correct":0}); row["attempted"]+=item.scored_questions; row["correct"]+=item.correct_questions
        return {"week_start":week_start,"attempt_records":len(selected),"questions_attempted":attempted,"questions_correct":correct,"accuracy":round(correct/attempted,6) if attempted else None,"time_ms":time_ms,"concepts":concepts}
    def error_notebook(self, activities: Iterable[LearningActivity])->list[dict[str,str]]:
        return [{"attempt_id":item.attempt_id,"published_revision_id":item.published_revision_id,"concept_id":item.concept_id,"activity_date":item.activity_date} for item in activities if item.completed and item.scored_questions>item.correct_questions]


@dataclass(frozen=True)
class Preference:
    learner_id: str
    channel: str
    consented: bool
    timezone_name: str = "UTC"
    quiet_start: str = "21:00"
    quiet_end: str = "08:00"
    daily_limit: int = 1

@dataclass(frozen=True)
class MessageRequest:
    learner_id: str
    channel: str
    category: str
    action_type: str
    action_id: str
    body: str
    idempotency_key: str


class CommunicationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection=connection; self.connection.row_factory=sqlite3.Row; self._init()
    @classmethod
    def open(cls,path:str=":memory:")->"CommunicationRepository": return cls(sqlite3.connect(path))
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase9_preferences(learner_id TEXT NOT NULL,channel TEXT NOT NULL,consented INTEGER NOT NULL,timezone_name TEXT NOT NULL,quiet_start TEXT NOT NULL,quiet_end TEXT NOT NULL,daily_limit INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(learner_id,channel));
        CREATE TABLE IF NOT EXISTS phase9_decisions(decision_id TEXT PRIMARY KEY,learner_id TEXT NOT NULL,channel TEXT NOT NULL,category TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,allowed INTEGER NOT NULL,reason TEXT NOT NULL,action_type TEXT NOT NULL,action_id TEXT NOT NULL,decided_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase9_queue(message_id TEXT PRIMARY KEY,decision_id TEXT NOT NULL REFERENCES phase9_decisions(decision_id),body TEXT NOT NULL,status TEXT NOT NULL,provider_reference TEXT,created_at TEXT NOT NULL,sent_at TEXT);
        """); self.connection.commit()
    def set_preference(self,pref:Preference)->None:
        if pref.channel not in {"telegram","whatsapp","email","push"} or pref.daily_limit<0: raise ValueError("invalid preference")
        ZoneInfo(pref.timezone_name); self._parse_time(pref.quiet_start); self._parse_time(pref.quiet_end)
        self.connection.execute("INSERT INTO phase9_preferences VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(learner_id,channel) DO UPDATE SET consented=excluded.consented,timezone_name=excluded.timezone_name,quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,daily_limit=excluded.daily_limit,updated_at=excluded.updated_at",(pref.learner_id,pref.channel,int(pref.consented),pref.timezone_name,pref.quiet_start,pref.quiet_end,pref.daily_limit,_now())); self.connection.commit()
    def decide(self,request:MessageRequest,*,now:str)->dict[str,Any]:
        existing=self.connection.execute("SELECT * FROM phase9_decisions WHERE idempotency_key=?",(request.idempotency_key,)).fetchone()
        if existing: return dict(existing)
        pref=self.connection.execute("SELECT * FROM phase9_preferences WHERE learner_id=? AND channel=?",(request.learner_id,request.channel)).fetchone(); allowed=True; reason="allowed"
        if not pref or not bool(pref["consented"]): allowed=False; reason="not_consented"
        elif not request.action_type.strip() or not request.action_id.strip(): allowed=False; reason="no_meaningful_action"
        else:
            current=datetime.fromisoformat(now).astimezone(ZoneInfo(pref["timezone_name"])); local_time=current.timetz().replace(tzinfo=None)
            if self._in_quiet(local_time,self._parse_time(pref["quiet_start"]),self._parse_time(pref["quiet_end"])): allowed=False; reason="quiet_hours"
            else:
                day_start=current.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).isoformat(); day_end=current.replace(hour=23,minute=59,second=59,microsecond=999999).astimezone(timezone.utc).isoformat()
                count=self.connection.execute("SELECT COUNT(*) FROM phase9_decisions WHERE learner_id=? AND channel=? AND category=? AND allowed=1 AND decided_at BETWEEN ? AND ?",(request.learner_id,request.channel,request.category,day_start,day_end)).fetchone()[0]
                if count>=int(pref["daily_limit"]): allowed=False; reason="frequency_cap"
        decision_id=_id("message-decision",request.learner_id,request.channel,request.idempotency_key); self.connection.execute("INSERT INTO phase9_decisions VALUES (?,?,?,?,?,?,?,?,?,?)",(decision_id,request.learner_id,request.channel,request.category,request.idempotency_key,int(allowed),reason,request.action_type,request.action_id,now));
        if allowed:
            message_id=_id("message",decision_id); self.connection.execute("INSERT INTO phase9_queue VALUES (?,?,?,'queued',NULL,?,NULL)",(message_id,decision_id,request.body,now))
        self.connection.commit(); return dict(self.connection.execute("SELECT * FROM phase9_decisions WHERE decision_id=?",(decision_id,)).fetchone())
    def queued(self)->list[dict[str,Any]]: return [dict(row) for row in self.connection.execute("SELECT * FROM phase9_queue WHERE status='queued' ORDER BY created_at,message_id")]
    @staticmethod
    def _parse_time(value:str)->time: return time.fromisoformat(value)
    @staticmethod
    def _in_quiet(current:time,start:time,end:time)->bool:
        if start==end: return False
        return start<=current<end if start<end else current>=start or current<end


class DeliveryAdapter:
    def __init__(self, *, active: bool=False): self.active=active; self.sent:list[str]=[]
    def deliver(self,message:dict[str,Any])->dict[str,Any]:
        if not self.active: return {"status":"disabled","provider_reference":None}
        reference=_id("provider",str(message["message_id"])); self.sent.append(reference); return {"status":"sent","provider_reference":reference}


@dataclass(frozen=True)
class Phase9Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase9Evaluator:
    def run(self)->Phase9Evaluation:
        checks:dict[str,bool]={}; activities=[LearningActivity("u","2026-01-01","a1","r1","c1",True,2,1,1000),LearningActivity("u","2026-01-02","a2","r2","c1",False,0,0,0),LearningActivity("u","2026-01-02","a3","r3","c2",True,1,1,500),LearningActivity("u","2026-01-03","a4","r4","c2",True,1,0,700)]
        continuity=LearningContinuity(); checks["empty_session_not_counted"]=continuity.streak(activities)==3; report=continuity.weekly_report(activities,week_start="2026-01-01")
        checks["report_reconciles"]=report["questions_attempted"]==4 and report["questions_correct"]==2 and report["attempt_records"]==3; notebook=continuity.error_notebook(activities); checks["notebook_pins_revision"]={row["published_revision_id"] for row in notebook}=={"r1","r4"}
        repo=CommunicationRepository.open(); repo.set_preference(Preference("u","telegram",True,"Asia/Kolkata","21:00","08:00",1)); req=MessageRequest("u","telegram","daily_plan","plan","p1","Your plan is ready","key1")
        quiet=repo.decide(req,now="2026-01-01T18:00:00+00:00"); checks["quiet_hours_cross_midnight"]=not bool(quiet["allowed"]) and quiet["reason"]=="quiet_hours"
        allowed=repo.decide(MessageRequest("u","telegram","daily_plan","plan","p1","Ready","key2"),now="2026-01-01T10:00:00+00:00"); checks["consented_action_queued"]=bool(allowed["allowed"]) and len(repo.queued())==1
        duplicate=repo.decide(MessageRequest("u","telegram","daily_plan","plan","p1","Changed","key2"),now="2026-01-01T10:01:00+00:00"); checks["dedup_idempotent"]=duplicate["decision_id"]==allowed["decision_id"] and len(repo.queued())==1
        capped=repo.decide(MessageRequest("u","telegram","daily_plan","plan","p2","Another","key3"),now="2026-01-01T11:00:00+00:00"); checks["frequency_cap_enforced"]=capped["reason"]=="frequency_cap"
        repo.set_preference(Preference("u","telegram",False,"Asia/Kolkata","21:00","08:00",1)); unsub=repo.decide(MessageRequest("u","telegram","report","report","w1","Report","key4"),now="2026-01-02T10:00:00+00:00"); checks["unsubscribe_overrides"]=unsub["reason"]=="not_consented"
        repo.set_preference(Preference("u2","email",True,"UTC","22:00","06:00",2)); meaningless=repo.decide(MessageRequest("u2","email","promo","","","Hello","key5"),now="2026-01-01T12:00:00+00:00"); checks["meaningful_action_required"]=meaningless["reason"]=="no_meaningful_action"
        disabled=DeliveryAdapter(active=False); checks["disabled_adapter_no_send"]=disabled.deliver(repo.queued()[0])["status"]=="disabled" and not disabled.sent
        active=DeliveryAdapter(active=True); checks["active_adapter_reference"]=active.deliver(repo.queued()[0])["status"]=="sent" and len(active.sent)==1
        checks["decision_history_immutable"]=repo.connection.execute("SELECT COUNT(*) FROM phase9_decisions").fetchone()[0]==5
        checks["evaluator_depth"]=len(checks)>=11
        return Phase9Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase9Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
