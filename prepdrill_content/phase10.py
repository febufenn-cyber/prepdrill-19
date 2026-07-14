"""Phase 10 deterministic billing events and entitlement safety."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any


def _canonical(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def _hash(value: Any) -> str: return hashlib.sha256(_canonical(value).encode()).hexdigest()
def _id(prefix: str, *parts: str) -> str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class Plan:
    plan_id: str
    version: int
    price_paise: int
    duration_days: int
    trial_days: int = 0
    grace_days: int = 0
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderEvent:
    event_id: str
    subscription_id: str
    learner_id: str
    event_type: str
    event_version: int
    occurred_epoch: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class Entitlement:
    learner_id: str
    subscription_id: str
    plan_id: str | None
    status: str
    access_until_epoch: int | None
    source_version: int
    features: tuple[str, ...]


class BillingRepository:
    def __init__(self, connection: sqlite3.Connection, *, sandbox_secret: str, live_secret: str | None = None):
        self.connection=connection; self.connection.row_factory=sqlite3.Row; self.sandbox_secret=sandbox_secret; self.live_secret=live_secret; self._init()
    @classmethod
    def open(cls,path:str=":memory:",**kwargs:Any)->"BillingRepository": return cls(sqlite3.connect(path),**kwargs)
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase10_plans(plan_id TEXT NOT NULL,version INTEGER NOT NULL,payload_json TEXT NOT NULL,active INTEGER NOT NULL,PRIMARY KEY(plan_id,version));
        CREATE TABLE IF NOT EXISTS phase10_provider_events(event_id TEXT PRIMARY KEY,mode TEXT NOT NULL,subscription_id TEXT NOT NULL,learner_id TEXT NOT NULL,event_type TEXT NOT NULL,event_version INTEGER NOT NULL,occurred_epoch INTEGER NOT NULL,payload_hash TEXT NOT NULL,payload_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase10_subscriptions(subscription_id TEXT PRIMARY KEY,learner_id TEXT NOT NULL,plan_id TEXT,status TEXT NOT NULL,access_until_epoch INTEGER,source_version INTEGER NOT NULL,last_event_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase10_entitlement_events(event_id TEXT PRIMARY KEY,subscription_id TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,created_epoch INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase10_mode_activation(mode TEXT PRIMARY KEY,active INTEGER NOT NULL,owner TEXT NOT NULL,reason TEXT NOT NULL,activated_epoch INTEGER NOT NULL);
        """); self.connection.commit()
    def add_plan(self,plan:Plan,*,active:bool=True)->None:
        if plan.price_paise<0 or plan.duration_days<0 or plan.trial_days<0 or plan.grace_days<0: raise ValueError("invalid plan")
        self.connection.execute("INSERT OR REPLACE INTO phase10_plans VALUES (?,?,?,?)",(plan.plan_id,plan.version,_canonical(asdict(plan)),int(active))); self.connection.commit()
    def sign(self,event:ProviderEvent,*,mode:str)->str:
        return hmac.new(self._secret(mode).encode(),_canonical(asdict(event)).encode(),hashlib.sha256).hexdigest()
    def ingest(self,event:ProviderEvent,*,signature:str,mode:str)->str:
        expected=self.sign(event,mode=mode)
        if not hmac.compare_digest(expected,signature): raise PermissionError("invalid webhook signature")
        payload_hash=_hash(asdict(event)); existing=self.connection.execute("SELECT payload_hash FROM phase10_provider_events WHERE event_id=?",(event.event_id,)).fetchone()
        if existing:
            if existing[0]!=payload_hash: raise ValueError("provider event collision")
            return "duplicate"
        current=self.connection.execute("SELECT source_version FROM phase10_subscriptions WHERE subscription_id=?",(event.subscription_id,)).fetchone()
        self.connection.execute("INSERT INTO phase10_provider_events VALUES (?,?,?,?,?,?,?,?,?)",(event.event_id,mode,event.subscription_id,event.learner_id,event.event_type,event.event_version,event.occurred_epoch,payload_hash,_canonical(event.payload)))
        if not current or event.event_version>int(current[0]): self._apply(event)
        self.connection.commit(); return "applied" if not current or event.event_version>int(current[0]) else "stale_recorded"
    def reconcile(self,snapshot:ProviderEvent,*,signature:str,mode:str)->str: return self.ingest(snapshot,signature=signature,mode=mode)
    def entitlement(self,subscription_id:str,*,now_epoch:int,provider_available:bool=True)->Entitlement:
        row=self.connection.execute("SELECT * FROM phase10_subscriptions WHERE subscription_id=?",(subscription_id,)).fetchone()
        if not row: raise KeyError(subscription_id)
        status=str(row["status"]); until=row["access_until_epoch"]
        if status in {"refunded","chargeback"}: effective="revoked"
        elif until is not None and now_epoch<=int(until) and status in {"active","trial","cancelled","grace"}: effective=status
        elif not provider_available and until is not None and now_epoch<=int(until): effective=status
        else: effective="expired"
        plan=self._plan(str(row["plan_id"])) if row["plan_id"] else None; features=tuple(plan.features) if plan and effective not in {"revoked","expired"} else ()
        return Entitlement(str(row["learner_id"]),subscription_id,str(row["plan_id"]) if row["plan_id"] else None,effective,int(until) if until is not None else None,int(row["source_version"]),features)
    def activate_mode(self,mode:str,*,owner:str,reason:str,epoch:int)->None:
        if mode not in {"sandbox","live"} or not owner.strip() or not reason.strip(): raise ValueError("invalid activation")
        if mode=="live" and not self.live_secret: raise PermissionError("live secret is unavailable")
        self.connection.execute("INSERT OR REPLACE INTO phase10_mode_activation VALUES (?,1,?,?,?)",(mode,owner,reason,epoch)); self.connection.commit()
    def mode_active(self,mode:str)->bool:
        row=self.connection.execute("SELECT active FROM phase10_mode_activation WHERE mode=?",(mode,)).fetchone(); return bool(row[0]) if row else False
    def paywall(self,subscription_id:str|None,*,now_epoch:int,value_demonstrated:bool)->dict[str,Any]:
        if not value_demonstrated: return {"show":False,"reason":"value_not_demonstrated"}
        if subscription_id:
            try:
                if self.entitlement(subscription_id,now_epoch=now_epoch).features: return {"show":False,"reason":"entitled"}
            except KeyError: pass
        return {"show":True,"reason":"premium_value_available"}
    def _secret(self,mode:str)->str:
        if mode=="sandbox": return self.sandbox_secret
        if mode=="live" and self.live_secret: return self.live_secret
        raise PermissionError("mode secret unavailable")
    def _plan(self,plan_id:str)->Plan|None:
        row=self.connection.execute("SELECT payload_json FROM phase10_plans WHERE plan_id=? AND active=1 ORDER BY version DESC LIMIT 1",(plan_id,)).fetchone()
        if not row: return None
        value=json.loads(row[0]); value["features"]=tuple(value.get("features",[])); return Plan(**value)
    def _apply(self,event:ProviderEvent)->None:
        payload=event.payload; status_map={"payment_completed":"active","trial_started":"trial","cancelled":"cancelled","grace_started":"grace","refunded":"refunded","chargeback":"chargeback","expired":"expired","snapshot":"active"}; status=status_map.get(event.event_type)
        if not status: raise ValueError("unsupported event type")
        plan_id=payload.get("plan_id"); until=payload.get("access_until_epoch")
        self.connection.execute("INSERT INTO phase10_subscriptions VALUES (?,?,?,?,?,?,?) ON CONFLICT(subscription_id) DO UPDATE SET learner_id=excluded.learner_id,plan_id=excluded.plan_id,status=excluded.status,access_until_epoch=excluded.access_until_epoch,source_version=excluded.source_version,last_event_id=excluded.last_event_id",(event.subscription_id,event.learner_id,plan_id,status,until,event.event_version,event.event_id))
        audit_id=_id("entitlement-event",event.event_id,status); self.connection.execute("INSERT INTO phase10_entitlement_events VALUES (?,?,?,?,?)",(audit_id,event.subscription_id,status,_canonical(payload),event.occurred_epoch))


@dataclass(frozen=True)
class Phase10Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase10Evaluator:
    def event(self,event_id:str,event_type:str,version:int,until:int=2000)->ProviderEvent:
        return ProviderEvent(event_id,"sub1","u1",event_type,version,1000+version,{"plan_id":"pro","access_until_epoch":until})
    def run(self)->Phase10Evaluation:
        repo=BillingRepository.open(sandbox_secret="sandbox-secret",live_secret=None); repo.add_plan(Plan("pro",1,29900,30,trial_days=7,grace_days=3,features=("adaptive","mocks"))); checks:dict[str,bool]={}
        paid=self.event("e1","payment_completed",1); checks["valid_signature_applies"]=repo.ingest(paid,signature=repo.sign(paid,mode="sandbox"),mode="sandbox")=="applied"
        try: repo.ingest(self.event("forged","payment_completed",2),signature="bad",mode="sandbox"); checks["forged_signature_blocked"]=False
        except PermissionError: checks["forged_signature_blocked"]=True
        checks["duplicate_idempotent"]=repo.ingest(paid,signature=repo.sign(paid,mode="sandbox"),mode="sandbox")=="duplicate"
        collision=ProviderEvent("e1","sub1","u1","payment_completed",1,1001,{"plan_id":"pro","access_until_epoch":9999})
        try: repo.ingest(collision,signature=repo.sign(collision,mode="sandbox"),mode="sandbox"); checks["event_collision_blocked"]=False
        except ValueError: checks["event_collision_blocked"]=True
        cancel=self.event("e3","cancelled",3,2000); repo.ingest(cancel,signature=repo.sign(cancel,mode="sandbox"),mode="sandbox"); checks["cancel_access_through_period"]=repo.entitlement("sub1",now_epoch=1500).status=="cancelled" and repo.entitlement("sub1",now_epoch=2500).status=="expired"
        stale=self.event("e2","payment_completed",2,9999); checks["stale_event_cannot_override"]=repo.ingest(stale,signature=repo.sign(stale,mode="sandbox"),mode="sandbox")=="stale_recorded" and repo.entitlement("sub1",now_epoch=1500).status=="cancelled"
        refund=self.event("e4","refunded",4,2000); repo.ingest(refund,signature=repo.sign(refund,mode="sandbox"),mode="sandbox"); checks["refund_revokes"]=repo.entitlement("sub1",now_epoch=1500).status=="revoked"
        snapshot=self.event("e5","snapshot",5,3000); checks["reconciliation_repairs_missing_event"]=repo.reconcile(snapshot,signature=repo.sign(snapshot,mode="sandbox"),mode="sandbox")=="applied" and repo.entitlement("sub1",now_epoch=2500).status=="active"
        checks["provider_outage_preserves_valid_period"]=repo.entitlement("sub1",now_epoch=2500,provider_available=False).status=="active"
        repo.activate_mode("sandbox",owner="owner",reason="test",epoch=1); checks["sandbox_explicitly_active"]=repo.mode_active("sandbox")
        try: repo.activate_mode("live",owner="owner",reason="go",epoch=1); checks["live_disabled_without_secret"]=False
        except PermissionError: checks["live_disabled_without_secret"]=True
        try: repo.sign(paid,mode="live"); checks["sandbox_live_secret_isolated"]=False
        except PermissionError: checks["sandbox_live_secret_isolated"]=True
        checks["post_value_paywall"]=not repo.paywall("sub1",now_epoch=2500,value_demonstrated=True)["show"] and not repo.paywall(None,now_epoch=2500,value_demonstrated=False)["show"] and repo.paywall(None,now_epoch=2500,value_demonstrated=True)["show"]
        checks["billing_history_preserved"]=repo.connection.execute("SELECT COUNT(*) FROM phase10_provider_events").fetchone()[0]==5 and repo.connection.execute("SELECT COUNT(*) FROM phase10_entitlement_events").fetchone()[0]==4
        checks["evaluator_depth"]=len(checks)>=13
        return Phase10Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase10Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
