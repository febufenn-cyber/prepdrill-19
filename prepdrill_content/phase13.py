"""Phase 13 generated-question quarantine, promotion, and stop controls."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any


def _canonical(value:Any)->str: return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def _id(prefix:str,*parts:str)->str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class GeneratedCandidate:
    source_revision_id:str
    concept_id:str
    generation_request_id:str
    prompt_version:str
    model_version:str
    question_text:str
    options:dict[str,str]
    claimed_answer_id:str
    target_difficulty:float
    estimated_difficulty:float
    maximum_similarity:float
    ambiguous:bool=False
    concept_match:bool=True
    generation_cost_micros:int=0
    generation_latency_ms:int=0

@dataclass(frozen=True)
class QuarantineEvaluation:
    candidate_id:str
    passed:bool
    blockers:tuple[str,...]


class GeneratedContentRepository:
    def __init__(self,connection:sqlite3.Connection): self.connection=connection; self.connection.row_factory=sqlite3.Row; self._init()
    @classmethod
    def open(cls,path:str=":memory:")->"GeneratedContentRepository": return cls(sqlite3.connect(path))
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase13_candidates(candidate_id TEXT PRIMARY KEY,lineage_json TEXT NOT NULL,payload_json TEXT NOT NULL,status TEXT NOT NULL,provenance_category TEXT NOT NULL,created_seq INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase13_solver_claims(candidate_id TEXT NOT NULL,solver_id TEXT NOT NULL,answer_id TEXT NOT NULL,evidence TEXT NOT NULL,independent INTEGER NOT NULL,PRIMARY KEY(candidate_id,solver_id));
        CREATE TABLE IF NOT EXISTS phase13_evaluations(evaluation_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,passed INTEGER NOT NULL,blockers_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase13_promotions(promotion_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,reviewer TEXT NOT NULL,reason TEXT NOT NULL,policy_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase13_shadow_metrics(candidate_id TEXT PRIMARY KEY,attempts INTEGER NOT NULL,correct INTEGER NOT NULL,complaints INTEGER NOT NULL,active INTEGER NOT NULL,retired INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase13_complaints(complaint_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,reason TEXT NOT NULL,severity TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS phase13_events(event_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,event_type TEXT NOT NULL,payload_json TEXT NOT NULL);
        """); self.connection.commit()
    def register(self,candidate:GeneratedCandidate)->str:
        if not candidate.source_revision_id or not candidate.concept_id or len(candidate.options)<2: raise ValueError("incomplete candidate lineage")
        lineage={"source_revision_id":candidate.source_revision_id,"concept_id":candidate.concept_id,"generation_request_id":candidate.generation_request_id,"prompt_version":candidate.prompt_version,"model_version":candidate.model_version}
        candidate_id=_id("generated",hashlib.sha256(_canonical({"lineage":lineage,"payload":asdict(candidate)}).encode()).hexdigest()); seq=self.connection.execute("SELECT COUNT(*) FROM phase13_candidates").fetchone()[0]+1
        self.connection.execute("INSERT OR IGNORE INTO phase13_candidates VALUES (?,?,?,?,?,?)",(candidate_id,_canonical(lineage),_canonical(asdict(candidate)),"quarantined","ai_generated_experimental",seq)); self.connection.execute("INSERT OR IGNORE INTO phase13_shadow_metrics VALUES (?,0,0,0,0,0)",(candidate_id,)); self._event(candidate_id,"registered",lineage); self.connection.commit(); return candidate_id
    def add_solver_claim(self,*,candidate_id:str,solver_id:str,answer_id:str,evidence:str,independent:bool=True)->None:
        self._candidate(candidate_id)
        if not solver_id.strip() or not evidence.strip(): raise ValueError("solver and evidence required")
        self.connection.execute("INSERT OR REPLACE INTO phase13_solver_claims VALUES (?,?,?,?,?)",(candidate_id,solver_id,answer_id,evidence,int(independent))); self.connection.commit()
    def evaluate(self,candidate_id:str,*,similarity_limit:float=.86,difficulty_tolerance:float=.20)->QuarantineEvaluation:
        row=self._candidate(candidate_id); candidate=GeneratedCandidate(**json.loads(row["payload_json"])); blockers:list[str]=[]
        claims=list(self.connection.execute("SELECT * FROM phase13_solver_claims WHERE candidate_id=? AND independent=1",(candidate_id,)))
        if len(claims)<2: blockers.append("insufficient_independent_solvers")
        elif len({claim["answer_id"] for claim in claims})!=1: blockers.append("solver_disagreement")
        else:
            agreed=str(claims[0]["answer_id"])
            if agreed!=candidate.claimed_answer_id: blockers.append("solver_claimed_answer_mismatch")
        if candidate.claimed_answer_id not in candidate.options: blockers.append("answer_not_in_options")
        if candidate.ambiguous: blockers.append("ambiguous_candidate")
        if not candidate.concept_match: blockers.append("concept_drift")
        if candidate.maximum_similarity>similarity_limit: blockers.append("near_duplicate")
        if abs(candidate.estimated_difficulty-candidate.target_difficulty)>difficulty_tolerance: blockers.append("difficulty_out_of_range")
        blockers=sorted(set(blockers)); evaluation_id=_id("generated-eval",candidate_id,hashlib.sha256(_canonical(blockers).encode()).hexdigest()); self.connection.execute("INSERT OR REPLACE INTO phase13_evaluations VALUES (?,?,?,?)",(evaluation_id,candidate_id,int(not blockers),_canonical(blockers))); self.connection.execute("UPDATE phase13_candidates SET status=? WHERE candidate_id=?",("review_ready" if not blockers else "blocked",candidate_id)); self._event(candidate_id,"evaluated",{"blockers":blockers}); self.connection.commit(); return QuarantineEvaluation(candidate_id,not blockers,tuple(blockers))
    def promote(self,candidate_id:str,*,reviewer:str,reason:str)->str:
        row=self._candidate(candidate_id)
        if row["status"]!="review_ready": raise PermissionError("candidate is not review ready")
        if not reviewer.strip() or not reason.strip(): raise ValueError("named reviewer and reason required")
        policy={"official_archive":False,"full_mock":False,"mastery_default":False,"public_previous_year":False,"shadow_practice":True,"provenance":"ai_generated_experimental"}; promotion_id=_id("generated-promotion",candidate_id,reviewer)
        self.connection.execute("INSERT INTO phase13_promotions VALUES (?,?,?,?,?)",(promotion_id,candidate_id,reviewer,reason,_canonical(policy))); self.connection.execute("UPDATE phase13_candidates SET status='shadow_promoted' WHERE candidate_id=?",(candidate_id,)); self.connection.execute("UPDATE phase13_shadow_metrics SET active=1 WHERE candidate_id=?",(candidate_id,)); self._event(candidate_id,"promoted",{"reviewer":reviewer,"reason":reason,"policy":policy}); self.connection.commit(); return promotion_id
    def policy(self,candidate_id:str)->dict[str,Any]:
        row=self.connection.execute("SELECT policy_json FROM phase13_promotions WHERE candidate_id=?",(candidate_id,)).fetchone()
        if not row: return {"official_archive":False,"full_mock":False,"mastery_default":False,"public_previous_year":False,"shadow_practice":False}
        return json.loads(row[0])
    def record_shadow(self,candidate_id:str,*,correct:bool)->None:
        row=self.connection.execute("SELECT active,retired FROM phase13_shadow_metrics WHERE candidate_id=?",(candidate_id,)).fetchone()
        if not row or not row[0] or row[1]: raise PermissionError("candidate is not active in shadow")
        self.connection.execute("UPDATE phase13_shadow_metrics SET attempts=attempts+1,correct=correct+? WHERE candidate_id=?",(int(correct),candidate_id)); self.connection.commit()
    def complain(self,candidate_id:str,*,reason:str,severity:str)->str:
        if severity not in {"low","medium","high","critical"}: raise ValueError("invalid severity")
        complaint_id=_id("generated-complaint",candidate_id,reason,str(self.connection.execute("SELECT COUNT(*) FROM phase13_complaints WHERE candidate_id=?",(candidate_id,)).fetchone()[0])); self.connection.execute("INSERT INTO phase13_complaints VALUES (?,?,?,?)",(complaint_id,candidate_id,reason,severity)); self.connection.execute("UPDATE phase13_shadow_metrics SET complaints=complaints+1 WHERE candidate_id=?",(candidate_id,)); self._event(candidate_id,"complaint",{"severity":severity,"reason":reason}); self.connection.commit(); return complaint_id
    def apply_stop_rules(self,candidate_id:str,*,minimum_attempts:int=10,minimum_accuracy:float=.20,max_complaints:int=2)->bool:
        row=self.connection.execute("SELECT * FROM phase13_shadow_metrics WHERE candidate_id=?",(candidate_id,)).fetchone()
        critical=bool(self.connection.execute("SELECT 1 FROM phase13_complaints WHERE candidate_id=? AND severity='critical'",(candidate_id,)).fetchone()); accuracy=row["correct"]/row["attempts"] if row["attempts"] else None
        stop=critical or row["complaints"]>=max_complaints or (row["attempts"]>=minimum_attempts and accuracy is not None and accuracy<minimum_accuracy)
        if stop:
            self.connection.execute("UPDATE phase13_shadow_metrics SET active=0,retired=1 WHERE candidate_id=?",(candidate_id,)); self.connection.execute("UPDATE phase13_candidates SET status='retired' WHERE candidate_id=?",(candidate_id,)); self._event(candidate_id,"automatic_retirement",{"accuracy":accuracy,"complaints":row["complaints"],"critical":critical}); self.connection.commit()
        return stop
    def economics(self)->dict[str,Any]:
        candidates=[GeneratedCandidate(**json.loads(row[0])) for row in self.connection.execute("SELECT payload_json FROM phase13_candidates")]; total=sum(item.generation_cost_micros for item in candidates); approved=self.connection.execute("SELECT COUNT(*) FROM phase13_promotions").fetchone()[0]
        return {"generated":len(candidates),"approved":approved,"total_generation_cost_micros":total,"cost_per_approved_micros":round(total/approved,2) if approved else None}
    def _candidate(self,candidate_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase13_candidates WHERE candidate_id=?",(candidate_id,)).fetchone()
        if not row: raise KeyError(candidate_id)
        return row
    def _event(self,candidate_id:str,event_type:str,payload:dict[str,Any])->None:
        count=self.connection.execute("SELECT COUNT(*) FROM phase13_events WHERE candidate_id=?",(candidate_id,)).fetchone()[0]; event_id=_id("generated-event",candidate_id,event_type,str(count)); self.connection.execute("INSERT INTO phase13_events VALUES (?,?,?,?)",(event_id,candidate_id,event_type,_canonical(payload)))


@dataclass(frozen=True)
class Phase13Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase13Evaluator:
    def candidate(self,**changes:Any)->GeneratedCandidate:
        value=dict(source_revision_id="rev:1",concept_id="sampling",generation_request_id="g1",prompt_version="p1",model_version="m1",question_text="Which method gives equal selection chance?",options={"A":"Simple random","B":"Purposive"},claimed_answer_id="A",target_difficulty=.5,estimated_difficulty=.55,maximum_similarity=.5,generation_cost_micros=1000,generation_latency_ms=100); value.update(changes); return GeneratedCandidate(**value)
    def claims(self,repo:GeneratedContentRepository,candidate_id:str,a:str="A",b:str="A")->None:
        repo.add_solver_claim(candidate_id=candidate_id,solver_id="solver1",answer_id=a,evidence="independent solve 1"); repo.add_solver_claim(candidate_id=candidate_id,solver_id="solver2",answer_id=b,evidence="independent solve 2")
    def run(self)->Phase13Evaluation:
        repo=GeneratedContentRepository.open(); checks:dict[str,bool]={}; clean=repo.register(self.candidate()); checks["starts_quarantined"]=repo._candidate(clean)["status"]=="quarantined"; checks["insufficient_solver_blocked"]="insufficient_independent_solvers" in repo.evaluate(clean).blockers
        disagreement=repo.register(self.candidate(generation_request_id="g2")); self.claims(repo,disagreement,"A","B"); checks["solver_disagreement_blocked"]="solver_disagreement" in repo.evaluate(disagreement).blockers
        duplicate=repo.register(self.candidate(generation_request_id="g3",maximum_similarity=.95)); self.claims(repo,duplicate); checks["duplicate_blocked"]="near_duplicate" in repo.evaluate(duplicate).blockers
        drift=repo.register(self.candidate(generation_request_id="g4",concept_match=False)); self.claims(repo,drift); checks["concept_drift_blocked"]="concept_drift" in repo.evaluate(drift).blockers
        ambiguous=repo.register(self.candidate(generation_request_id="g5",ambiguous=True)); self.claims(repo,ambiguous); checks["ambiguity_blocked"]="ambiguous_candidate" in repo.evaluate(ambiguous).blockers
        difficulty=repo.register(self.candidate(generation_request_id="g6",estimated_difficulty=.9)); self.claims(repo,difficulty); checks["difficulty_range_enforced"]="difficulty_out_of_range" in repo.evaluate(difficulty).blockers
        approved=repo.register(self.candidate(generation_request_id="g7")); self.claims(repo,approved); checks["clean_still_requires_human"]=repo.evaluate(approved).passed and repo.policy(approved)["shadow_practice"] is False; promotion=repo.promote(approved,reviewer="expert",reason="reviewed")
        policy=repo.policy(approved); checks["human_promotion_preserves_quarantine_policy"]=bool(promotion) and policy["shadow_practice"] and not policy["official_archive"] and not policy["full_mock"] and not policy["mastery_default"] and policy["provenance"]=="ai_generated_experimental"
        for i in range(10): repo.record_shadow(approved,correct=i<8)
        checks["healthy_shadow_remains_active"]=not repo.apply_stop_rules(approved)
        repo.complain(approved,reason="ambiguous in context",severity="critical"); checks["critical_complaint_auto_retires"]=repo.apply_stop_rules(approved) and repo._candidate(approved)["status"]=="retired"
        econ=repo.economics(); checks["generation_economics_include_rejections"]=econ["generated"]==7 and econ["approved"]==1 and econ["total_generation_cost_micros"]==7000 and econ["cost_per_approved_micros"]==7000
        checks["immutable_lineage_retained"]="source_revision_id" in json.loads(repo._candidate(approved)["lineage_json"])
        checks["evaluator_depth"]=len(checks)>=12
        return Phase13Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase13Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
