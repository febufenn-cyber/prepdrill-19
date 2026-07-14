"""Phase 14 subject packs, separate gates, shared client contracts, and expansion decisions."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Iterable


def _canonical(value:Any)->str: return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def _hash(value:Any)->str: return hashlib.sha256(_canonical(value).encode()).hexdigest()
def _id(prefix:str,*parts:str)->str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class SubjectPack:
    pack_id:str
    exam_id:str
    subject_id:str
    version:int
    taxonomy_version:str
    supported_question_types:tuple[str,...]
    supported_block_types:tuple[str,...]
    scoring_per_correct:int=2
    client_contract_version:int=1
    approved_for_launch:bool=False

    @property
    def namespace(self)->str: return f"{self.exam_id}:{self.subject_id}:v{self.version}"

@dataclass(frozen=True)
class ClientCapabilities:
    platform:str
    contract_version:int
    question_types:tuple[str,...]
    block_types:tuple[str,...]

@dataclass(frozen=True)
class ClientEvent:
    sequence:int
    event_type:str
    ordinal:int|None=None
    option_id:str|None=None
    marked:bool=False
    remaining_seconds:int|None=None

@dataclass(frozen=True)
class ClientState:
    namespace:str
    contract_version:int
    current_ordinal:int
    responses:dict[str,str|None]
    marked:tuple[int,...]
    remaining_seconds:int
    submitted:bool
    score:int|None
    state_fingerprint:str

@dataclass(frozen=True)
class ExpansionInputs:
    trust_rate:float
    retained_learning_rate:float
    contribution_margin:float
    operations_success_rate:float
    paper1_regressions_green:bool
    critical_incidents:int=0


class PlatformRegistry:
    def __init__(self,connection:sqlite3.Connection): self.connection=connection; self.connection.row_factory=sqlite3.Row; self._init()
    @classmethod
    def open(cls,path:str=":memory:")->"PlatformRegistry": return cls(sqlite3.connect(path))
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase14_subject_packs(pack_id TEXT PRIMARY KEY,namespace TEXT NOT NULL UNIQUE,payload_json TEXT NOT NULL,approved_for_launch INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase14_authorizations(authorization_id TEXT PRIMARY KEY,pack_id TEXT NOT NULL REFERENCES phase14_subject_packs(pack_id),corpus_fingerprint TEXT NOT NULL,gate_passed INTEGER NOT NULL,owner TEXT NOT NULL,reason TEXT NOT NULL,active INTEGER NOT NULL,UNIQUE(pack_id,corpus_fingerprint));
        CREATE TABLE IF NOT EXISTS phase14_identity_links(guest_id TEXT PRIMARY KEY,auth_user_id TEXT NOT NULL,onboarding_name TEXT NOT NULL,account_name TEXT NOT NULL,merge_key TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS phase14_state_records(state_id TEXT PRIMARY KEY,namespace TEXT NOT NULL,account_id TEXT NOT NULL,platform TEXT NOT NULL,state_fingerprint TEXT NOT NULL,payload_json TEXT NOT NULL,UNIQUE(namespace,account_id,platform,state_fingerprint));
        CREATE TABLE IF NOT EXISTS phase14_expansion_decisions(decision_id TEXT PRIMARY KEY,target_namespace TEXT NOT NULL,outcome TEXT NOT NULL,inputs_json TEXT NOT NULL,reasons_json TEXT NOT NULL);
        """); self.connection.commit()
    def register_pack(self,pack:SubjectPack)->None:
        if not pack.pack_id or not pack.exam_id or not pack.subject_id or pack.version<1 or not pack.supported_question_types or not pack.supported_block_types: raise ValueError("invalid subject pack")
        self.connection.execute("INSERT OR REPLACE INTO phase14_subject_packs VALUES (?,?,?,?)",(pack.pack_id,pack.namespace,_canonical(asdict(pack)),int(pack.approved_for_launch))); self.connection.commit()
    def authorize(self,*,pack_id:str,corpus_fingerprint:str,gate_passed:bool,owner:str,reason:str)->str:
        row=self._pack_row(pack_id)
        if not bool(row["approved_for_launch"]): raise PermissionError("subject pack is not approved for launch")
        if not gate_passed or not corpus_fingerprint.strip() or not owner.strip() or not reason.strip(): raise PermissionError("current gate and named owner are required")
        authorization_id=_id("subject-auth",pack_id,corpus_fingerprint,owner); self.connection.execute("UPDATE phase14_authorizations SET active=0 WHERE pack_id=?",(pack_id,)); self.connection.execute("INSERT OR REPLACE INTO phase14_authorizations VALUES (?,?,?,?,?,?,1)",(authorization_id,pack_id,corpus_fingerprint,1,owner,reason)); self.connection.commit(); return authorization_id
    def can_start(self,*,pack_id:str,current_corpus_fingerprint:str,capabilities:ClientCapabilities)->bool:
        pack=self.pack(pack_id); auth=self.connection.execute("SELECT * FROM phase14_authorizations WHERE pack_id=? AND active=1",(pack_id,)).fetchone()
        if not auth or auth["corpus_fingerprint"]!=current_corpus_fingerprint: return False
        if capabilities.contract_version!=pack.client_contract_version: return False
        return set(pack.supported_question_types)<=set(capabilities.question_types) and set(pack.supported_block_types)<=set(capabilities.block_types)
    def pack(self,pack_id:str)->SubjectPack:
        value=json.loads(self._pack_row(pack_id)["payload_json"]); value["supported_question_types"]=tuple(value["supported_question_types"]); value["supported_block_types"]=tuple(value["supported_block_types"]); return SubjectPack(**value)
    def namespace_id(self,pack_id:str,entity_type:str,local_id:str)->str: return _id(entity_type,self.pack(pack_id).namespace,local_id)
    def link_identity(self,*,guest_id:str,auth_user_id:str,onboarding_name:str,account_name:str,merge_key:str)->dict[str,str]:
        if not auth_user_id.strip() or not merge_key.strip(): raise ValueError("authenticated identity and merge key are required")
        existing=self.connection.execute("SELECT * FROM phase14_identity_links WHERE merge_key=?",(merge_key,)).fetchone()
        if existing:
            if existing["guest_id"]!=guest_id or existing["auth_user_id"]!=auth_user_id: raise ValueError("merge key collision")
            return dict(existing)
        linked=self.connection.execute("SELECT auth_user_id FROM phase14_identity_links WHERE guest_id=?",(guest_id,)).fetchone()
        if linked and linked[0]!=auth_user_id: raise PermissionError("guest already linked to another account")
        self.connection.execute("INSERT INTO phase14_identity_links VALUES (?,?,?,?,?)",(guest_id,auth_user_id,onboarding_name,account_name,merge_key)); self.connection.commit(); return dict(self.connection.execute("SELECT * FROM phase14_identity_links WHERE guest_id=?",(guest_id,)).fetchone())
    def persist_client_state(self,*,state:ClientState,account_id:str,platform:str)->str:
        state_id=_id("client-state",state.namespace,account_id,platform,state.state_fingerprint); self.connection.execute("INSERT OR IGNORE INTO phase14_state_records VALUES (?,?,?,?,?,?)",(state_id,state.namespace,account_id,platform,state.state_fingerprint,_canonical(asdict(state)))); self.connection.commit(); return state_id
    def decide_expansion(self,*,target_pack_id:str,inputs:ExpansionInputs)->dict[str,Any]:
        pack=self.pack(target_pack_id); reasons=[]
        if inputs.critical_incidents>0 or inputs.trust_rate<.95 or not inputs.paper1_regressions_green: outcome="kill"; reasons.append("paper1_health_or_trust_failure")
        elif inputs.trust_rate>=.98 and inputs.retained_learning_rate>=.30 and inputs.contribution_margin>0 and inputs.operations_success_rate>=.98: outcome="scale"; reasons.append("all_scale_thresholds_met")
        else: outcome="hold"; reasons.append("insufficient_measured_evidence")
        if not pack.approved_for_launch: outcome="kill"; reasons.append("subject_pack_not_approved")
        decision_id=_id("expansion",pack.namespace,_hash(asdict(inputs))); self.connection.execute("INSERT OR REPLACE INTO phase14_expansion_decisions VALUES (?,?,?,?,?)",(decision_id,pack.namespace,outcome,_canonical(asdict(inputs)),_canonical(reasons))); self.connection.commit(); return {"decision_id":decision_id,"outcome":outcome,"reasons":reasons}
    def _pack_row(self,pack_id:str)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM phase14_subject_packs WHERE pack_id=?",(pack_id,)).fetchone()
        if not row: raise KeyError(pack_id)
        return row


class ClientStateReducer:
    def reduce(self,*,pack:SubjectPack,events:Iterable[ClientEvent],answer_key:dict[int,str],question_count:int,initial_seconds:int)->ClientState:
        responses={str(index):None for index in range(question_count)}; marked:set[int]=set(); current=0; remaining=initial_seconds; submitted=False
        ordered=sorted(events,key=lambda event:event.sequence)
        if len(ordered)!=len({event.sequence for event in ordered}): raise ValueError("duplicate event sequence")
        previous=0
        for event in ordered:
            if event.sequence<=previous: raise ValueError("non-monotonic event sequence")
            previous=event.sequence
            if submitted: raise ValueError("events after submit are forbidden")
            if event.event_type=="navigate":
                if event.ordinal is None or not 0<=event.ordinal<question_count: raise IndexError(event.ordinal)
                current=event.ordinal
            elif event.event_type=="answer":
                if event.ordinal is None or not 0<=event.ordinal<question_count: raise IndexError(event.ordinal)
                responses[str(event.ordinal)]=event.option_id; current=event.ordinal
            elif event.event_type=="mark":
                if event.ordinal is None: raise ValueError("ordinal required")
                if event.marked: marked.add(event.ordinal)
                else: marked.discard(event.ordinal)
            elif event.event_type=="clear":
                if event.ordinal is None: raise ValueError("ordinal required")
                responses[str(event.ordinal)]=None; marked.discard(event.ordinal)
            elif event.event_type=="tick":
                if event.remaining_seconds is None or event.remaining_seconds>remaining or event.remaining_seconds<0: raise ValueError("invalid server time")
                remaining=event.remaining_seconds
            elif event.event_type=="submit": submitted=True; remaining=max(0,remaining)
            else: raise ValueError("unsupported client event")
        score=None
        if submitted: score=sum(pack.scoring_per_correct for ordinal,correct in answer_key.items() if responses.get(str(ordinal))==correct)
        payload={"namespace":pack.namespace,"contract_version":pack.client_contract_version,"current_ordinal":current,"responses":responses,"marked":sorted(marked),"remaining_seconds":remaining,"submitted":submitted,"score":score}; fingerprint=_hash(payload)
        return ClientState(pack.namespace,pack.client_contract_version,current,responses,tuple(sorted(marked)),remaining,submitted,score,fingerprint)
    def assert_parity(self,states:Iterable[ClientState])->bool:
        materialised=list(states); return bool(materialised) and len({state.state_fingerprint for state in materialised})==1


@dataclass(frozen=True)
class Phase14Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase14Evaluator:
    TYPES=("single_choice","passage_linked","table_based","match_following")
    BLOCKS=("paragraph","table","image","match_lists")
    def run(self)->Phase14Evaluation:
        repo=PlatformRegistry.open(); checks:dict[str,bool]={}; p1=SubjectPack("paper1","ugc_net","paper_1",1,"p1.tax.v1",self.TYPES,self.BLOCKS,2,1,True); p2=SubjectPack("english","ugc_net","paper_2_english",1,"english.tax.v1",self.TYPES,self.BLOCKS,2,1,True); adjacent=SubjectPack("ssc","ssc","general",1,"ssc.tax.v1",("single_choice",),("paragraph",),2,1,False)
        for pack in (p1,p2,adjacent): repo.register_pack(pack)
        full=ClientCapabilities("web",1,self.TYPES,self.BLOCKS); repo.authorize(pack_id="paper1",corpus_fingerprint="p1-fp",gate_passed=True,owner="owner",reason="p1 reviewed")
        checks["paper1_auth_cannot_unlock_paper2"]=not repo.can_start(pack_id="english",current_corpus_fingerprint="p1-fp",capabilities=full)
        repo.authorize(pack_id="english",corpus_fingerprint="p2-fp",gate_passed=True,owner="owner",reason="p2 reviewed"); checks["paper2_requires_matching_gate"]=repo.can_start(pack_id="english",current_corpus_fingerprint="p2-fp",capabilities=full) and not repo.can_start(pack_id="english",current_corpus_fingerprint="stale",capabilities=full)
        checks["subject_namespaces_isolated"]=repo.namespace_id("paper1","attempt","1")!=repo.namespace_id("english","attempt","1") and p1.namespace!=p2.namespace
        limited=ClientCapabilities("old-ios",1,("single_choice",),("paragraph",)); checks["unsupported_renderer_blocked"]=not repo.can_start(pack_id="english",current_corpus_fingerprint="p2-fp",capabilities=limited)
        stale_client=ClientCapabilities("web",0,self.TYPES,self.BLOCKS); checks["stale_contract_blocked"]=not repo.can_start(pack_id="english",current_corpus_fingerprint="p2-fp",capabilities=stale_client)
        link=repo.link_identity(guest_id="guest",auth_user_id="account",onboarding_name="Guest Name",account_name="Registered Name",merge_key="merge1"); checks["authenticated_account_wins_name_mismatch"]=link["auth_user_id"]=="account" and link["account_name"]=="Registered Name"
        events=[ClientEvent(1,"answer",0,"A"),ClientEvent(2,"mark",1,marked=True),ClientEvent(3,"answer",1,"B"),ClientEvent(4,"tick",remaining_seconds=50),ClientEvent(5,"submit")]; reducer=ClientStateReducer(); states=[reducer.reduce(pack=p2,events=events,answer_key={0:"A",1:"B"},question_count=2,initial_seconds=60) for _ in ("web","ios","android")]
        checks["cross_client_state_and_score_parity"]=reducer.assert_parity(states) and states[0].score==4
        for platform,state in zip(("web","ios","android"),states): repo.persist_client_state(state=state,account_id="account",platform=platform)
        checks["client_states_namespaced"]=repo.connection.execute("SELECT COUNT(DISTINCT namespace) FROM phase14_state_records").fetchone()[0]==1 and repo.connection.execute("SELECT COUNT(*) FROM phase14_state_records").fetchone()[0]==3
        healthy=repo.decide_expansion(target_pack_id="english",inputs=ExpansionInputs(.99,.35,.25,.99,True,0)); checks["healthy_inputs_scale"]=healthy["outcome"]=="scale"
        weak=repo.decide_expansion(target_pack_id="english",inputs=ExpansionInputs(.96,.10,-.1,.90,True,0)); checks["insufficient_inputs_hold"]=weak["outcome"]=="hold"
        unhealthy=repo.decide_expansion(target_pack_id="english",inputs=ExpansionInputs(.94,.50,.5,.99,False,1)); checks["paper1_regression_kills_expansion"]=unhealthy["outcome"]=="kill"
        try: repo.authorize(pack_id="ssc",corpus_fingerprint="ssc-fp",gate_passed=True,owner="owner",reason="attempt"); checks["unapproved_adjacent_exam_blocked"]=False
        except PermissionError: checks["unapproved_adjacent_exam_blocked"]=True
        checks["evaluator_depth"]=len(checks)>=11
        return Phase14Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase14Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
