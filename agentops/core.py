"""Evidence-constrained workflow runtime for a simulated securities KYC process.

Standard-library-only reference implementation. Not a production compliance system.
"""
from __future__ import annotations
import hashlib, json, sqlite3, time, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

TERMINAL = {"APPROVED", "REJECTED", "ESCALATED"}

class ControlError(Exception): pass

class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, status TEXT NOT NULL, version INTEGER NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL, digest TEXT NOT NULL, source TEXT NOT NULL, verified INTEGER NOT NULL, created REAL NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(id));
        CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, code TEXT NOT NULL, conclusion TEXT NOT NULL, evidence_ids TEXT NOT NULL, rule_version TEXT NOT NULL, created REAL NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(id));
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, actor TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL, created REAL NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(id));
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, maker TEXT NOT NULL, checker TEXT NOT NULL, decision TEXT NOT NULL, created REAL NOT NULL, task_digest TEXT, policy_versions TEXT, FOREIGN KEY(case_id) REFERENCES cases(id));
        CREATE TABLE IF NOT EXISTS tool_runs(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, tool TEXT NOT NULL, actor TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT NOT NULL, created REAL NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(id));
        """)
        approval_columns={r[1] for r in self.db.execute("PRAGMA table_info(approvals)")}
        if "task_digest" not in approval_columns:
            self.db.execute("ALTER TABLE approvals ADD COLUMN task_digest TEXT")
        if "policy_versions" not in approval_columns:
            self.db.execute("ALTER TABLE approvals ADD COLUMN policy_versions TEXT")

    def close(self):
        self.db.close()

    def _event(self, case_id: str, actor: str, event_type: str, payload: dict[str,Any]):
        prev = self.db.execute("SELECT event_hash FROM events WHERE case_id=? ORDER BY seq DESC LIMIT 1", (case_id,)).fetchone()
        prev_hash = prev[0] if prev else "GENESIS"
        body = {"case_id":case_id,"actor":actor,"event_type":event_type,"payload":payload,"prev_hash":prev_hash}
        digest = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        self.db.execute("INSERT INTO events(case_id,actor,event_type,payload,prev_hash,event_hash,created) VALUES(?,?,?,?,?,?,?)",
                        (case_id,actor,event_type,json.dumps(payload,sort_keys=True,ensure_ascii=False),prev_hash,digest,time.time()))

    def create_case(self, case_id: str | None = None, actor="system") -> str:
        cid = case_id or str(uuid.uuid4())
        self.db.execute("INSERT INTO cases VALUES(?,?,?,?)",(cid,"RECEIVED",1,time.time()))
        self._event(cid,actor,"CASE_CREATED",{"status":"RECEIVED","version":1})
        self.db.commit(); return cid

    def case(self, cid):
        r=self.db.execute("SELECT * FROM cases WHERE id=?",(cid,)).fetchone()
        if not r: raise ControlError("case not found")
        return dict(r)

    def transition(self,cid,new_status,actor,expected_version=None):
        # Serialize state transitions and use a compare-and-swap update. A prior
        # read followed by an unconditional UPDATE is vulnerable to concurrent writers.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            c=self.case(cid)
            if c["status"] in TERMINAL: raise ControlError("terminal case cannot transition")
            if expected_version is not None and c["version"] != expected_version: raise ControlError("stale case version")
            allowed={"RECEIVED":{"IN_REVIEW","ESCALATED"},"IN_REVIEW":{"PENDING_APPROVAL","ESCALATED"},"PENDING_APPROVAL":{"APPROVED","REJECTED","ESCALATED"}}
            if new_status not in allowed.get(c["status"],set()): raise ControlError(f"invalid transition {c['status']} -> {new_status}")
            if new_status == "PENDING_APPROVAL":
                gate=PolicyGate().evaluate_for_approval(self,cid)
                if not gate["allowed"]: raise ControlError("policy gate blocked approval: "+gate["reason"])
            v=c["version"]+1
            cur=self.db.execute("UPDATE cases SET status=?,version=? WHERE id=? AND version=?",(new_status,v,cid,c["version"]))
            if cur.rowcount != 1: raise ControlError("stale case version")
            self._event(cid,actor,"STATUS_CHANGED",{"from":c["status"],"to":new_status,"version":v})
            self.db.commit()
            return self.case(cid)
        except Exception:
            self.db.rollback()
            raise

    def _assert_case_mutable(self,cid):
        status=self.case(cid)["status"]
        if status in {"PENDING_APPROVAL", *TERMINAL}:
            raise ControlError("case evidence/findings are frozen during or after approval")

    def add_evidence(self,cid,kind,content,source,verified=False,actor="agent"):
        self._assert_case_mutable(cid)
        eid=str(uuid.uuid4()); digest=hashlib.sha256(content if isinstance(content,bytes) else str(content).encode()).hexdigest()
        self.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?)",(eid,cid,kind,digest,source,int(verified),time.time()))
        self._event(cid,actor,"EVIDENCE_REGISTERED",{"evidence_id":eid,"kind":kind,"digest":digest,"source":source,"verified":bool(verified)})
        self.db.commit(); return eid

    def evidence(self,cid,eid):
        r=self.db.execute("SELECT * FROM evidence WHERE case_id=? AND id=?",(cid,eid)).fetchone()
        return dict(r) if r else None

    def add_finding(self,cid,code,conclusion,evidence_ids,rule_version="kyc-policy-1.0",actor="agent"):
        self._assert_case_mutable(cid)
        if not evidence_ids: raise ControlError("finding must cite at least one evidence item")
        for eid in evidence_ids:
            if not self.evidence(cid,eid): raise ControlError(f"evidence not found in case: {eid}")
        fid=str(uuid.uuid4())
        payload={"finding_id":fid,"code":code,"conclusion":conclusion,"evidence_ids":evidence_ids,"rule_version":rule_version}
        self.db.execute("INSERT INTO findings VALUES(?,?,?,?,?,?,?)",(fid,cid,code,conclusion,json.dumps(evidence_ids),rule_version,time.time()))
        self._event(cid,actor,"FINDING_RECORDED",payload); self.db.commit(); return fid

    def findings(self,cid):
        return [dict(r) for r in self.db.execute("SELECT * FROM findings WHERE case_id=? ORDER BY created",(cid,))]

    def record_tool_run(self,cid,tool,actor,inputs,outputs):
        rid=str(uuid.uuid4())
        self.db.execute("INSERT INTO tool_runs VALUES(?,?,?,?,?,?,?)",(rid,cid,tool,actor,json.dumps(inputs,sort_keys=True),json.dumps(outputs,sort_keys=True),time.time()))
        self._event(cid,actor,"TOOL_EXECUTED",{"run_id":rid,"tool":tool,"input":inputs,"output":outputs})
        self.db.commit(); return rid

    def _approval_snapshot(self,cid,decision):
        evidence=[dict(r) for r in self.db.execute(
            "SELECT id,kind,digest,source,verified FROM evidence WHERE case_id=? ORDER BY id",(cid,))]
        findings=[dict(r) for r in self.db.execute(
            "SELECT id,code,conclusion,evidence_ids,rule_version FROM findings WHERE case_id=? ORDER BY id",(cid,))]
        policy_versions=sorted({f["rule_version"] for f in findings})
        body={"case_id":cid,"decision":decision,"evidence":evidence,"findings":findings,
              "policy_versions":policy_versions}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        return digest,policy_versions

    def verify_approval_snapshot(self,approval_id):
        row=self.db.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone()
        if not row or not row["task_digest"]:
            return False
        digest,versions=self._approval_snapshot(row["case_id"],row["decision"])
        return digest==row["task_digest"] and json.loads(row["policy_versions"] or "[]")==versions

    def approve(self,cid,maker,checker,decision):
        if maker==checker: raise ControlError("maker and checker must be different principals")
        if decision not in {"APPROVE","REJECT","ESCALATE"}: raise ControlError("invalid decision")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            c=self.case(cid)
            if c["status"]!="PENDING_APPROVAL": raise ControlError("case is not pending approval")
            # Re-evaluate at the decision boundary, not only when entering the queue.
            gate=PolicyGate().evaluate_for_approval(self,cid)
            if not gate["allowed"]: raise ControlError("policy gate blocked decision: "+gate["reason"])
            aid=str(uuid.uuid4()); target={"APPROVE":"APPROVED","REJECT":"REJECTED","ESCALATE":"ESCALATED"}[decision]
            task_digest,policy_versions=self._approval_snapshot(cid,decision)
            self.db.execute("INSERT INTO approvals(id,case_id,maker,checker,decision,created,task_digest,policy_versions) VALUES(?,?,?,?,?,?,?,?)",
                (aid,cid,maker,checker,decision,time.time(),task_digest,json.dumps(policy_versions)))
            self._event(cid,checker,"HUMAN_DECISION",{"approval_id":aid,"maker":maker,"checker":checker,
                "decision":decision,"task_digest":task_digest,"policy_versions":policy_versions})
            v=c["version"]+1
            cur=self.db.execute("UPDATE cases SET status=?,version=? WHERE id=? AND version=? AND status='PENDING_APPROVAL'",(target,v,cid,c["version"]))
            if cur.rowcount != 1: raise ControlError("case changed during approval")
            self._event(cid,checker,"STATUS_CHANGED",{"from":"PENDING_APPROVAL","to":target,"version":v})
            self.db.commit()
            return aid
        except Exception:
            self.db.rollback()
            raise

    def verify_audit_chain(self,cid):
        rows=self.db.execute("SELECT * FROM events WHERE case_id=? ORDER BY seq",(cid,)).fetchall(); prev="GENESIS"
        for r in rows:
            payload=json.loads(r["payload"])
            body={"case_id":cid,"actor":r["actor"],"event_type":r["event_type"],"payload":payload,"prev_hash":prev}
            expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            if r["prev_hash"]!=prev or r["event_hash"]!=expected: return False
            prev=r["event_hash"]
        return True

    def event_log(self,cid):
        return [dict(r) for r in self.db.execute("SELECT * FROM events WHERE case_id=? ORDER BY seq",(cid,))]

@dataclass
class Principal:
    name: str
    roles: frozenset[str]

class ToolRegistry:
    def __init__(self): self._tools: dict[str,tuple[set[str],Callable]]={}
    def register(self,name,allowed_roles,fn): self._tools[name]=(set(allowed_roles),fn)
    def invoke(self,name,principal:Principal,store:Store,cid:str,inputs:dict):
        if name not in self._tools: raise ControlError("unknown tool")
        roles,fn=self._tools[name]
        if not (roles & set(principal.roles)): raise ControlError("tool permission denied")
        output=fn(inputs)
        store.record_tool_run(cid,name,principal.name,inputs,output)
        return output

class PolicyGate:
    REQUIRED_EVIDENCE={"INCORPORATION_DOCUMENT","OWNERSHIP_STRUCTURE","AUTHORIZED_SIGNATORY"}
    def evaluate_for_approval(self,store:Store,cid:str):
        rows=store.db.execute("SELECT kind,verified FROM evidence WHERE case_id=?",(cid,)).fetchall()
        verified={r["kind"] for r in rows if r["verified"]}
        missing=sorted(self.REQUIRED_EVIDENCE-verified)
        if missing: return {"allowed":False,"reason":"MISSING_VERIFIED_EVIDENCE","missing":missing}
        if not store.findings(cid): return {"allowed":False,"reason":"NO_EVIDENCE_BACKED_FINDINGS"}
        return {"allowed":True,"reason":"POLICY_CHECKS_PASSED"}

class Replay:
    """Replay recorded tool calls against a deterministic fixture; never re-calls live external systems."""
    @staticmethod
    def replay_tool_runs(store:Store,cid:str):
        runs=store.db.execute("SELECT tool,input_json,output_json FROM tool_runs WHERE case_id=? ORDER BY created",(cid,)).fetchall()
        return [{"tool":r["tool"],"input":json.loads(r["input_json"]),"recorded_output":json.loads(r["output_json"])} for r in runs]
