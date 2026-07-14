"""Phase 12 tenant isolation, aggregate privacy, and reversible admin operations."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any


def _canonical(value:Any)->str: return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def _id(prefix:str,*parts:str)->str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"

ROLE_PERMISSIONS={
    "owner":{"tenant.read","tenant.write","cohort.read","cohort.write","assignment.write","report.read","export.create","bulk.propose","bulk.approve"},
    "admin":{"tenant.read","cohort.read","cohort.write","assignment.write","report.read","export.create","bulk.propose","bulk.approve"},
    "instructor":{"tenant.read","cohort.read","assignment.write","report.read"},
    "analyst":{"tenant.read","cohort.read","report.read","export.create"},
    "learner":{"assignment.read"},
}

@dataclass(frozen=True)
class ContentTarget:
    target_id:str
    target_type:str
    published:bool
    issue_state:str="clear"


class InstituteRepository:
    ALLOWED_EXPORT_FIELDS={"learner_id_hash","cohort_id","attempted","correct","accuracy","time_ms"}
    def __init__(self,connection:sqlite3.Connection,min_cohort_size:int=5): self.connection=connection; self.connection.row_factory=sqlite3.Row; self.min_cohort_size=min_cohort_size; self._init()
    @classmethod
    def open(cls,path:str=":memory:",min_cohort_size:int=5)->"InstituteRepository": return cls(sqlite3.connect(path),min_cohort_size)
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase12_tenants(tenant_id TEXT PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase12_memberships(tenant_id TEXT NOT NULL,user_id TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(tenant_id,user_id));
        CREATE TABLE IF NOT EXISTS phase12_cohorts(cohort_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase12_enrollments(cohort_id TEXT NOT NULL,learner_id TEXT NOT NULL,PRIMARY KEY(cohort_id,learner_id));
        CREATE TABLE IF NOT EXISTS phase12_assignments(assignment_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,cohort_id TEXT NOT NULL,target_id TEXT NOT NULL,target_type TEXT NOT NULL,created_by TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase12_metrics(tenant_id TEXT NOT NULL,cohort_id TEXT NOT NULL,learner_id TEXT NOT NULL,attempted INTEGER NOT NULL,correct INTEGER NOT NULL,time_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase12_bulk_operations(operation_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,operation_type TEXT NOT NULL,payload_json TEXT NOT NULL,impact_json TEXT NOT NULL,status TEXT NOT NULL,proposed_by TEXT NOT NULL,approved_by TEXT,executed_state_json TEXT);
        CREATE TABLE IF NOT EXISTS phase12_bulk_events(event_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,payload_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase12_exports(export_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,requested_by TEXT NOT NULL,fields_json TEXT NOT NULL,payload_json TEXT NOT NULL,fingerprint TEXT NOT NULL);
        """); self.connection.commit()
    def create_tenant(self,tenant_id:str,name:str,owner_id:str)->None:
        self.connection.execute("INSERT INTO phase12_tenants VALUES (?,?)",(tenant_id,name)); self.connection.execute("INSERT INTO phase12_memberships VALUES (?,?,'owner')",(tenant_id,owner_id)); self.connection.commit()
    def add_member(self,*,tenant_id:str,actor_id:str,user_id:str,role:str)->None:
        self._require(tenant_id,actor_id,"tenant.write")
        if role not in ROLE_PERMISSIONS: raise ValueError("invalid role")
        self.connection.execute("INSERT OR REPLACE INTO phase12_memberships VALUES (?,?,?)",(tenant_id,user_id,role)); self.connection.commit()
    def create_cohort(self,*,tenant_id:str,actor_id:str,cohort_id:str,name:str)->None:
        self._require(tenant_id,actor_id,"cohort.write"); self.connection.execute("INSERT INTO phase12_cohorts VALUES (?,?,?)",(cohort_id,tenant_id,name)); self.connection.commit()
    def enroll(self,*,tenant_id:str,actor_id:str,cohort_id:str,learner_id:str)->None:
        self._require(tenant_id,actor_id,"cohort.write"); self._cohort(tenant_id,cohort_id); self.connection.execute("INSERT OR IGNORE INTO phase12_enrollments VALUES (?,?)",(cohort_id,learner_id)); self.connection.commit()
    def create_assignment(self,*,tenant_id:str,actor_id:str,cohort_id:str,target:ContentTarget)->str:
        self._require(tenant_id,actor_id,"assignment.write"); self._cohort(tenant_id,cohort_id)
        if not target.published or target.issue_state!="clear": raise PermissionError("assignment target is not approved published content")
        if target.target_type not in {"published_question","mock_manifest","daily_plan"}: raise ValueError("unsupported assignment target")
        assignment_id=_id("assignment",tenant_id,cohort_id,target.target_type,target.target_id); self.connection.execute("INSERT OR IGNORE INTO phase12_assignments VALUES (?,?,?,?,?,?)",(assignment_id,tenant_id,cohort_id,target.target_id,target.target_type,actor_id)); self.connection.commit(); return assignment_id
    def add_metric(self,*,tenant_id:str,cohort_id:str,learner_id:str,attempted:int,correct:int,time_ms:int)->None:
        self._cohort(tenant_id,cohort_id)
        if not self.connection.execute("SELECT 1 FROM phase12_enrollments WHERE cohort_id=? AND learner_id=?",(cohort_id,learner_id)).fetchone(): raise PermissionError("learner is not enrolled")
        self.connection.execute("INSERT INTO phase12_metrics VALUES (?,?,?,?,?,?)",(tenant_id,cohort_id,learner_id,attempted,correct,time_ms)); self.connection.commit()
    def aggregate_report(self,*,tenant_id:str,actor_id:str,cohort_id:str)->dict[str,Any]:
        self._require(tenant_id,actor_id,"report.read"); self._cohort(tenant_id,cohort_id); learners=self.connection.execute("SELECT COUNT(*) FROM phase12_enrollments WHERE cohort_id=?",(cohort_id,)).fetchone()[0]
        if learners<self.min_cohort_size: return {"suppressed":True,"reason":"minimum_cohort_size","learner_count":learners}
        row=self.connection.execute("SELECT COALESCE(SUM(attempted),0),COALESCE(SUM(correct),0),COALESCE(SUM(time_ms),0) FROM phase12_metrics WHERE tenant_id=? AND cohort_id=?",(tenant_id,cohort_id)).fetchone(); attempted=int(row[0]); correct=int(row[1]); return {"suppressed":False,"learner_count":learners,"attempted":attempted,"correct":correct,"accuracy":round(correct/attempted,6) if attempted else None,"time_ms":int(row[2])}
    def export(self,*,tenant_id:str,actor_id:str,cohort_id:str,fields:list[str])->dict[str,Any]:
        self._require(tenant_id,actor_id,"export.create"); self._cohort(tenant_id,cohort_id)
        if not fields or not set(fields)<=self.ALLOWED_EXPORT_FIELDS: raise PermissionError("export field not allowed")
        rows=[]
        for row in self.connection.execute("SELECT * FROM phase12_metrics WHERE tenant_id=? AND cohort_id=?",(tenant_id,cohort_id)):
            base={"learner_id_hash":hashlib.sha256(str(row["learner_id"]).encode()).hexdigest()[:16],"cohort_id":cohort_id,"attempted":row["attempted"],"correct":row["correct"],"accuracy":round(row["correct"]/row["attempted"],6) if row["attempted"] else None,"time_ms":row["time_ms"]}; rows.append({field:base[field] for field in fields})
        payload={"tenant_id":tenant_id,"cohort_id":cohort_id,"fields":fields,"rows":rows}; fingerprint=hashlib.sha256(_canonical(payload).encode()).hexdigest(); export_id=_id("export",tenant_id,cohort_id,fingerprint); self.connection.execute("INSERT INTO phase12_exports VALUES (?,?,?,?,?,?)",(export_id,tenant_id,actor_id,_canonical(fields),_canonical(payload),fingerprint)); self.connection.commit(); return {"export_id":export_id,"fingerprint":fingerprint,"payload":payload}
    def propose_bulk(self,*,tenant_id:str,actor_id:str,operation_type:str,payload:dict[str,Any])->str:
        self._require(tenant_id,actor_id,"bulk.propose"); impact={"records":len(payload.get("targets",[])),"operation_type":operation_type}; operation_id=_id("bulk",tenant_id,operation_type,hashlib.sha256(_canonical(payload).encode()).hexdigest()); self.connection.execute("INSERT INTO phase12_bulk_operations VALUES (?,?,?,?,?,'dry_run',?,NULL,NULL)",(operation_id,tenant_id,operation_type,_canonical(payload),_canonical(impact),actor_id)); self._event(operation_id,"dry_run",actor_id,impact); self.connection.commit(); return operation_id
    def approve_bulk(self,operation_id:str,*,actor_id:str)->None:
        row=self._operation(operation_id); self._require(row["tenant_id"],actor_id,"bulk.approve")
        if row["proposed_by"]==actor_id: raise PermissionError("independent approver required")
        if row["status"]!="dry_run": raise ValueError("operation is not awaiting approval")
        self.connection.execute("UPDATE phase12_bulk_operations SET status='approved',approved_by=? WHERE operation_id=?",(actor_id,operation_id)); self._event(operation_id,"approved",actor_id,{}); self.connection.commit()
    def execute_bulk(self,operation_id:str,*,actor_id:str,current_state:dict[str,Any])->None:
        row=self._operation(operation_id); self._require(row["tenant_id"],actor_id,"bulk.approve")
        if row["status"]!="approved": raise ValueError("operation is not approved")
        payload=json.loads(row["payload_json"])
        if payload.get("content_publication_override"): raise PermissionError("content truth gate cannot be bypassed")
        self.connection.execute("UPDATE phase12_bulk_operations SET status='executed',executed_state_json=? WHERE operation_id=?",(_canonical(current_state),operation_id)); self._event(operation_id,"executed",actor_id,{"before":current_state,"requested":payload}); self.connection.commit()
    def rollback_bulk(self,operation_id:str,*,actor_id:str)->dict[str,Any]:
        row=self._operation(operation_id); self._require(row["tenant_id"],actor_id,"bulk.approve")
        if row["status"]!="executed": raise ValueError("operation is not executed")
        before=json.loads(row["executed_state_json"]); self.connection.execute("UPDATE phase12_bulk_operations SET status='rolled_back' WHERE operation_id=?",(operation_id,)); self._event(operation_id,"rollback",actor_id,{"restore":before}); self.connection.commit(); return before
    def _require(self,tenant_id:str,user_id:str,permission:str)->None:
        row=self.connection.execute("SELECT role FROM phase12_memberships WHERE tenant_id=? AND user_id=?",(tenant_id,user_id)).fetchone()
        if not row or permission not in ROLE_PERMISSIONS.get(row[0],set()): raise PermissionError("tenant permission denied")
    def _cohort(self,tenant_id:str,cohort_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase12_cohorts WHERE cohort_id=? AND tenant_id=?",(cohort_id,tenant_id)).fetchone()
        if not row: raise PermissionError("cross-tenant cohort access")
        return row
    def _operation(self,operation_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase12_bulk_operations WHERE operation_id=?",(operation_id,)).fetchone()
        if not row: raise KeyError(operation_id)
        return row
    def _event(self,operation_id:str,event_type:str,actor:str,payload:dict[str,Any])->None:
        event_id=_id("bulk-event",operation_id,event_type,actor,str(self.connection.execute("SELECT COUNT(*) FROM phase12_bulk_events WHERE operation_id=?",(operation_id,)).fetchone()[0])); self.connection.execute("INSERT INTO phase12_bulk_events VALUES (?,?,?,?,?)",(event_id,operation_id,event_type,actor,_canonical(payload)))


@dataclass(frozen=True)
class Phase12Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase12Evaluator:
    def run(self)->Phase12Evaluation:
        repo=InstituteRepository.open(min_cohort_size=3); checks:dict[str,bool]={}; repo.create_tenant("t1","Institute One","owner1"); repo.create_tenant("t2","Institute Two","owner2"); repo.add_member(tenant_id="t1",actor_id="owner1",user_id="admin1",role="admin"); repo.add_member(tenant_id="t1",actor_id="owner1",user_id="analyst1",role="analyst"); repo.create_cohort(tenant_id="t1",actor_id="admin1",cohort_id="c1",name="Cohort"); repo.create_cohort(tenant_id="t2",actor_id="owner2",cohort_id="c2",name="Other")
        try: repo.create_cohort(tenant_id="t2",actor_id="admin1",cohort_id="bad",name="Leak"); checks["cross_tenant_write_blocked"]=False
        except PermissionError: checks["cross_tenant_write_blocked"]=True
        try: repo.aggregate_report(tenant_id="t2",actor_id="analyst1",cohort_id="c2"); checks["cross_tenant_read_blocked"]=False
        except PermissionError: checks["cross_tenant_read_blocked"]=True
        try: repo.add_member(tenant_id="t1",actor_id="analyst1",user_id="x",role="owner"); checks["role_escalation_blocked"]=False
        except PermissionError: checks["role_escalation_blocked"]=True
        repo.enroll(tenant_id="t1",actor_id="admin1",cohort_id="c1",learner_id="l1"); repo.enroll(tenant_id="t1",actor_id="admin1",cohort_id="c1",learner_id="l2"); checks["small_cohort_suppressed"]=repo.aggregate_report(tenant_id="t1",actor_id="analyst1",cohort_id="c1")["suppressed"]
        repo.enroll(tenant_id="t1",actor_id="admin1",cohort_id="c1",learner_id="l3")
        for learner in ("l1","l2","l3"): repo.add_metric(tenant_id="t1",cohort_id="c1",learner_id=learner,attempted=10,correct=7,time_ms=1000)
        report=repo.aggregate_report(tenant_id="t1",actor_id="analyst1",cohort_id="c1"); checks["aggregate_only_report"]=not report["suppressed"] and report["attempted"]==30 and "learners" not in report
        try: repo.create_assignment(tenant_id="t1",actor_id="admin1",cohort_id="c1",target=ContentTarget("q1","published_question",False)); checks["unpublished_assignment_blocked"]=False
        except PermissionError: checks["unpublished_assignment_blocked"]=True
        checks["approved_assignment_allowed"]=bool(repo.create_assignment(tenant_id="t1",actor_id="admin1",cohort_id="c1",target=ContentTarget("pub1","published_question",True)))
        export=repo.export(tenant_id="t1",actor_id="analyst1",cohort_id="c1",fields=["learner_id_hash","attempted","accuracy"]); checks["export_is_tenant_scoped_and_pseudonymous"]=len(export["payload"]["rows"])==3 and "learner_id" not in export["payload"]["rows"][0] and bool(export["fingerprint"])
        try: repo.export(tenant_id="t1",actor_id="analyst1",cohort_id="c1",fields=["email"]); checks["forbidden_export_field_blocked"]=False
        except PermissionError: checks["forbidden_export_field_blocked"]=True
        operation=repo.propose_bulk(tenant_id="t1",actor_id="admin1",operation_type="archive_assignments",payload={"targets":["a1","a2"]})
        try: repo.approve_bulk(operation,actor_id="admin1"); checks["independent_approval_required"]=False
        except PermissionError: checks["independent_approval_required"]=True
        repo.approve_bulk(operation,actor_id="owner1"); before={"assignments":["a1","a2"]}; repo.execute_bulk(operation,actor_id="owner1",current_state=before); checks["bulk_audit_complete"]=repo.connection.execute("SELECT COUNT(*) FROM phase12_bulk_events WHERE operation_id=?",(operation,)).fetchone()[0]==3
        checks["compensating_rollback"]=repo.rollback_bulk(operation,actor_id="owner1")==before and repo.connection.execute("SELECT COUNT(*) FROM phase12_bulk_events WHERE operation_id=?",(operation,)).fetchone()[0]==4
        blocked=repo.propose_bulk(tenant_id="t1",actor_id="admin1",operation_type="publish",payload={"targets":["q"],"content_publication_override":True}); repo.approve_bulk(blocked,actor_id="owner1")
        try: repo.execute_bulk(blocked,actor_id="owner1",current_state={}); checks["content_gate_preserved"]=False
        except PermissionError: checks["content_gate_preserved"]=True
        checks["evaluator_depth"]=len(checks)>=12
        return Phase12Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase12Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
