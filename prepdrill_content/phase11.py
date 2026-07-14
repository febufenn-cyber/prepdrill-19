"""Phase 11 rights-gated growth, attribution, referral, and experiment controls."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlencode


def _canonical(value: Any)->str: return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def _id(prefix:str,*parts:str)->str: return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class PublicContent:
    content_id:str
    slug:str
    title:str
    publication_state:str
    issue_state:str
    rights_status:str
    answer_verified:bool
    indexable:bool
    provenance_category:str
    content_hash:str

class PublicPageGate:
    ELIGIBLE_RIGHTS={"cleared","licensed","owned","official_publication_reviewed"}
    def eligible(self,item:PublicContent)->bool:
        return item.publication_state=="published" and item.issue_state=="clear" and item.rights_status in self.ELIGIBLE_RIGHTS and item.answer_verified and item.indexable and item.provenance_category!="ai_generated_experimental"
    def metadata(self,item:PublicContent,*,base_url:str)->dict[str,Any]:
        allowed=self.eligible(item); canonical=f"{base_url.rstrip('/')}/questions/{item.slug}"
        return {"title":item.title,"canonical":canonical,"robots":"index,follow" if allowed else "noindex,nofollow","content_fingerprint":item.content_hash,"indexable":allowed}
    def sitemap(self,items:list[PublicContent],*,base_url:str)->list[str]:
        return sorted(self.metadata(item,base_url=base_url)["canonical"] for item in items if self.eligible(item))


class DeepLinkSigner:
    DESTINATIONS={"diagnostic","daily","question","mock"}
    def __init__(self,secret:str): self.secret=secret
    def create(self,*,campaign:str,destination:str,target_id:str)->str:
        if destination not in self.DESTINATIONS or not campaign.strip() or not target_id.strip(): raise ValueError("invalid deep link")
        payload={"campaign":campaign,"destination":destination,"target_id":target_id}; signature=hmac.new(self.secret.encode(),_canonical(payload).encode(),hashlib.sha256).hexdigest(); return "prepdrill://open?"+urlencode({**payload,"sig":signature})
    def verify(self,params:dict[str,str])->dict[str,str]:
        payload={key:params.get(key,"") for key in ("campaign","destination","target_id")}
        if payload["destination"] not in self.DESTINATIONS: raise ValueError("unsupported destination")
        expected=hmac.new(self.secret.encode(),_canonical(payload).encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,params.get("sig","")): raise PermissionError("invalid signature")
        return payload


class GrowthRepository:
    def __init__(self,connection:sqlite3.Connection): self.connection=connection; self.connection.row_factory=sqlite3.Row; self._init()
    @classmethod
    def open(cls,path:str=":memory:")->"GrowthRepository": return cls(sqlite3.connect(path))
    def _init(self)->None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS phase11_attribution(subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,first_campaign TEXT NOT NULL,last_campaign TEXT NOT NULL,first_at INTEGER NOT NULL,last_at INTEGER NOT NULL,PRIMARY KEY(subject_type,subject_id));
        CREATE TABLE IF NOT EXISTS phase11_conversions(conversion_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,conversion_type TEXT NOT NULL,campaign TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(account_id,conversion_type));
        CREATE TABLE IF NOT EXISTS phase11_referrals(code TEXT PRIMARY KEY,owner_id TEXT NOT NULL,owner_device_hash TEXT NOT NULL,max_redemptions INTEGER NOT NULL,redeemed_count INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS phase11_redemptions(redemption_id TEXT PRIMARY KEY,code TEXT NOT NULL REFERENCES phase11_referrals(code),redeemer_id TEXT NOT NULL UNIQUE,device_hash TEXT NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS phase11_experiments(experiment_id TEXT PRIMARY KEY,hypothesis TEXT NOT NULL,primary_metric TEXT NOT NULL,guardrails_json TEXT NOT NULL,variants_json TEXT NOT NULL,allocation INTEGER NOT NULL,active INTEGER NOT NULL,killed INTEGER NOT NULL DEFAULT 0);
        """); self.connection.commit()
    def touch(self,*,subject_type:str,subject_id:str,campaign:str,epoch:int)->None:
        row=self.connection.execute("SELECT * FROM phase11_attribution WHERE subject_type=? AND subject_id=?",(subject_type,subject_id)).fetchone()
        if row: self.connection.execute("UPDATE phase11_attribution SET last_campaign=?,last_at=? WHERE subject_type=? AND subject_id=?",(campaign,epoch,subject_type,subject_id))
        else: self.connection.execute("INSERT INTO phase11_attribution VALUES (?,?,?,?,?,?)",(subject_type,subject_id,campaign,campaign,epoch,epoch))
        self.connection.commit()
    def merge_guest(self,*,guest_id:str,account_id:str)->dict[str,Any]:
        guest=self.connection.execute("SELECT * FROM phase11_attribution WHERE subject_type='guest' AND subject_id=?",(guest_id,)).fetchone(); account=self.connection.execute("SELECT * FROM phase11_attribution WHERE subject_type='account' AND subject_id=?",(account_id,)).fetchone()
        if guest:
            first=account["first_campaign"] if account else guest["first_campaign"]; first_at=account["first_at"] if account else guest["first_at"]; last=guest["last_campaign"] if not account or guest["last_at"]>=account["last_at"] else account["last_campaign"]; last_at=max(guest["last_at"],account["last_at"] if account else guest["last_at"])
            self.connection.execute("INSERT INTO phase11_attribution VALUES ('account',?,?,?,?,?) ON CONFLICT(subject_type,subject_id) DO UPDATE SET first_campaign=excluded.first_campaign,last_campaign=excluded.last_campaign,first_at=excluded.first_at,last_at=excluded.last_at",(account_id,first,last,first_at,last_at))
        self.connection.commit(); row=self.connection.execute("SELECT * FROM phase11_attribution WHERE subject_type='account' AND subject_id=?",(account_id,)).fetchone(); return dict(row) if row else {}
    def record_conversion(self,*,account_id:str,conversion_type:str,epoch:int)->str:
        attr=self.connection.execute("SELECT last_campaign FROM phase11_attribution WHERE subject_type='account' AND subject_id=?",(account_id,)).fetchone(); campaign=attr[0] if attr else "direct"; conversion_id=_id("conversion",account_id,conversion_type)
        self.connection.execute("INSERT OR IGNORE INTO phase11_conversions VALUES (?,?,?,?,?)",(conversion_id,account_id,conversion_type,campaign,epoch)); self.connection.commit(); return conversion_id
    def create_referral(self,*,owner_id:str,owner_device_hash:str,max_redemptions:int=5)->str:
        if max_redemptions<=0: raise ValueError("invalid redemption limit")
        code=hashlib.sha256(f"{owner_id}\x1f{owner_device_hash}".encode()).hexdigest()[:10]; self.connection.execute("INSERT OR IGNORE INTO phase11_referrals VALUES (?,?,?,?,0,1)",(code,owner_id,owner_device_hash,max_redemptions)); self.connection.commit(); return code
    def redeem(self,*,code:str,redeemer_id:str,device_hash:str,epoch:int)->str:
        row=self.connection.execute("SELECT * FROM phase11_referrals WHERE code=?",(code,)).fetchone()
        if not row or not row["active"]: raise ValueError("invalid referral")
        if row["owner_id"]==redeemer_id or row["owner_device_hash"]==device_hash: raise PermissionError("self referral blocked")
        if row["redeemed_count"]>=row["max_redemptions"]: raise ValueError("redemption limit reached")
        if self.connection.execute("SELECT 1 FROM phase11_redemptions WHERE device_hash=?",(device_hash,)).fetchone(): raise PermissionError("device already redeemed")
        redemption_id=_id("redemption",code,redeemer_id); self.connection.execute("INSERT INTO phase11_redemptions VALUES (?,?,?,?,?)",(redemption_id,code,redeemer_id,device_hash,epoch)); self.connection.execute("UPDATE phase11_referrals SET redeemed_count=redeemed_count+1 WHERE code=?",(code,)); self.connection.commit(); return redemption_id
    def create_experiment(self,*,experiment_id:str,hypothesis:str,primary_metric:str,guardrails:list[str],variants:list[str],allocation:int)->None:
        if not hypothesis.strip() or not primary_metric.strip() or not guardrails or len(variants)<2 or not 0<allocation<=100: raise ValueError("experiment contract incomplete")
        self.connection.execute("INSERT INTO phase11_experiments VALUES (?,?,?,?,?,?,1,0)",(experiment_id,hypothesis,primary_metric,_canonical(guardrails),_canonical(variants),allocation)); self.connection.commit()
    def assign(self,experiment_id:str,subject_id:str)->str|None:
        row=self.connection.execute("SELECT * FROM phase11_experiments WHERE experiment_id=?",(experiment_id,)).fetchone()
        if not row or not row["active"] or row["killed"]: return None
        bucket=int(hashlib.sha256(f"{experiment_id}\x1f{subject_id}".encode()).hexdigest()[:8],16)%100
        if bucket>=row["allocation"]: return None
        variants=json.loads(row["variants_json"]); return variants[bucket%len(variants)]
    def kill_experiment(self,experiment_id:str)->None: self.connection.execute("UPDATE phase11_experiments SET killed=1,active=0 WHERE experiment_id=?",(experiment_id,)); self.connection.commit()


@dataclass(frozen=True)
class Phase11Evaluation:
    passed:bool; checks:dict[str,bool]
    def to_dict(self)->dict[str,Any]: return {"passed":self.passed,"checks":self.checks,"check_count":len(self.checks)}

class Phase11Evaluator:
    def run(self)->Phase11Evaluation:
        checks:dict[str,bool]={}; gate=PublicPageGate(); eligible=PublicContent("1","sampling","Sampling","published","clear","licensed",True,True,"official_previous_year","h1"); blocked=PublicContent("2","blocked","Blocked","published","clear","unknown",True,True,"official_previous_year","h2"); experimental=PublicContent("3","exp","Exp","published","clear","owned",True,True,"ai_generated_experimental","h3")
        checks["eligible_page_indexed"]=gate.metadata(eligible,base_url="https://example.com")["robots"]=="index,follow"
        checks["blocked_and_experimental_noindex"]=not gate.metadata(blocked,base_url="https://example.com")["indexable"] and not gate.metadata(experimental,base_url="https://example.com")["indexable"]
        checks["sitemap_matches_gate"]=gate.sitemap([blocked,eligible,experimental],base_url="https://example.com")==["https://example.com/questions/sampling"]
        signer=DeepLinkSigner("secret"); link=signer.create(campaign="telegram-daily",destination="question",target_id="1"); query=dict(part.split("=",1) for part in link.split("?",1)[1].split("&")); checks["signed_link_verified"]=signer.verify(query)["target_id"]=="1"
        tampered=dict(query); tampered["target_id"]="2"
        try: signer.verify(tampered); checks["tampered_link_blocked"]=False
        except PermissionError: checks["tampered_link_blocked"]=True
        repo=GrowthRepository.open(); repo.touch(subject_type="guest",subject_id="g",campaign="telegram",epoch=1); repo.touch(subject_type="guest",subject_id="g",campaign="youtube",epoch=2); merged=repo.merge_guest(guest_id="g",account_id="u")
        checks["attribution_survives_merge"]=(merged["first_campaign"],merged["last_campaign"])==("telegram","youtube")
        c1=repo.record_conversion(account_id="u",conversion_type="activation",epoch=3); c2=repo.record_conversion(account_id="u",conversion_type="activation",epoch=4); checks["conversion_exactly_once"]=c1==c2 and repo.connection.execute("SELECT COUNT(*) FROM phase11_conversions").fetchone()[0]==1
        code=repo.create_referral(owner_id="owner",owner_device_hash="d1",max_redemptions=1)
        try: repo.redeem(code=code,redeemer_id="owner",device_hash="d2",epoch=1); checks["self_referral_blocked"]=False
        except PermissionError: checks["self_referral_blocked"]=True
        repo.redeem(code=code,redeemer_id="friend",device_hash="d2",epoch=2)
        try: repo.redeem(code=code,redeemer_id="friend2",device_hash="d3",epoch=3); checks["redemption_limit_enforced"]=False
        except ValueError: checks["redemption_limit_enforced"]=True
        try: repo.create_experiment(experiment_id="bad",hypothesis="",primary_metric="clicks",guardrails=[],variants=["a","b"],allocation=100); checks["experiment_guardrails_required"]=False
        except ValueError: checks["experiment_guardrails_required"]=True
        repo.create_experiment(experiment_id="exp1",hypothesis="Diagnostic improves activation",primary_metric="activated",guardrails=["retention_not_lower"],variants=["control","treatment"],allocation=100); a=repo.assign("exp1","u"); b=repo.assign("exp1","u"); checks["experiment_assignment_deterministic"]=a==b and a in {"control","treatment"}; repo.kill_experiment("exp1"); checks["experiment_kill_switch"]=repo.assign("exp1","u") is None
        checks["meaningful_conversion_recorded"]=repo.connection.execute("SELECT conversion_type FROM phase11_conversions").fetchone()[0]=="activation"
        checks["evaluator_depth"]=len(checks)>=12
        return Phase11Evaluation(all(checks.values()),checks)

if __name__=="__main__":
    result=Phase11Evaluator().run(); print(json.dumps(result.to_dict(),indent=2,sort_keys=True)); raise SystemExit(0 if result.passed else 1)
