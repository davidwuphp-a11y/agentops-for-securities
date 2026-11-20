"""Durable execution primitives for AgentOps Phase 4.

The ledger provides at-least-once orchestration with idempotency keys. Exactly-once
external side effects are NOT claimed: tools must enforce idempotency themselves.
"""
from __future__ import annotations
import json, sqlite3, time, uuid, hashlib
from pathlib import Path
from typing import Callable, Any

class ExecutionError(RuntimeError): pass

class ExecutionLedger:
    def __init__(self, path: str | Path):
        self.db=sqlite3.connect(str(path), timeout=10, isolation_level=None, check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS runs(
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, state TEXT NOT NULL,
          input_json TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
          error TEXT
        );
        CREATE TABLE IF NOT EXISTS steps(
          run_id TEXT NOT NULL, step_key TEXT NOT NULL, ordinal INTEGER NOT NULL,
          tool_name TEXT NOT NULL, input_json TEXT NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, output_json TEXT, error TEXT,
          idempotency_key TEXT NOT NULL, updated REAL NOT NULL,
          PRIMARY KEY(run_id,step_key), UNIQUE(idempotency_key),
          FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );
        """)
    def close(self): self.db.close()
    def create_run(self, case_id: str, payload: dict, run_id: str|None=None) -> str:
        rid=run_id or str(uuid.uuid4()); now=time.time()
        self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,NULL)",
          (rid,case_id,"PENDING",json.dumps(payload,sort_keys=True),now,now))
        return rid
    def plan_step(self, run_id: str, ordinal: int, tool_name: str, inputs: dict, step_key: str|None=None):
        key=step_key or f"{ordinal}:{tool_name}"
        idem=hashlib.sha256(f"{run_id}:{key}".encode()).hexdigest()
        self.db.execute("""INSERT OR IGNORE INTO steps
          (run_id,step_key,ordinal,tool_name,input_json,state,idempotency_key,updated)
          VALUES(?,?,?,?,?,'PENDING',?,?)""",
          (run_id,key,ordinal,tool_name,json.dumps(inputs,sort_keys=True),idem,time.time()))
        row=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_key=?",(run_id,key)).fetchone()
        if row["tool_name"]!=tool_name or row["input_json"]!=json.dumps(inputs,sort_keys=True):
            raise ExecutionError("step key reused with different tool/input")
        return dict(row)
    def claim(self, run_id: str, step_key: str, max_attempts: int=3):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_key=?",(run_id,step_key)).fetchone()
            if not row: raise ExecutionError("step not found")
            if row["state"]=="SUCCEEDED":
                self.db.execute("COMMIT"); return {"claimed":False,"reason":"already_succeeded","step":dict(row)}
            if row["state"]=="RUNNING":
                self.db.execute("COMMIT"); return {"claimed":False,"reason":"already_running","step":dict(row)}
            if row["attempts"]>=max_attempts:
                self.db.execute("UPDATE steps SET state='DEAD',updated=? WHERE run_id=? AND step_key=?",(time.time(),run_id,step_key))
                self.db.execute("COMMIT"); return {"claimed":False,"reason":"attempt_limit","step":dict(row)}
            self.db.execute("UPDATE steps SET state='RUNNING',attempts=attempts+1,error=NULL,updated=? WHERE run_id=? AND step_key=?",
                            (time.time(),run_id,step_key))
            self.db.execute("UPDATE runs SET state='RUNNING',updated=? WHERE run_id=?",(time.time(),run_id))
            updated=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_key=?",(run_id,step_key)).fetchone()
            self.db.execute("COMMIT"); return {"claimed":True,"step":dict(updated)}
        except:
            self.db.execute("ROLLBACK"); raise
    def succeed(self, run_id: str, step_key: str, output: dict):
        cur=self.db.execute("""UPDATE steps SET state='SUCCEEDED',output_json=?,error=NULL,updated=?
          WHERE run_id=? AND step_key=? AND state='RUNNING'""",
          (json.dumps(output,sort_keys=True),time.time(),run_id,step_key))
        if cur.rowcount!=1: raise ExecutionError("step is not claimed")
        pending=self.db.execute("SELECT COUNT(*) FROM steps WHERE run_id=? AND state!='SUCCEEDED'",(run_id,)).fetchone()[0]
        self.db.execute("UPDATE runs SET state=?,updated=? WHERE run_id=?",
                        ("SUCCEEDED" if pending==0 else "RUNNING",time.time(),run_id))
    def fail(self, run_id: str, step_key: str, error: str):
        cur=self.db.execute("""UPDATE steps SET state='FAILED',error=?,updated=?
          WHERE run_id=? AND step_key=? AND state='RUNNING'""",
          (error[:2000],time.time(),run_id,step_key))
        if cur.rowcount!=1: raise ExecutionError("step is not claimed")
        self.db.execute("UPDATE runs SET state='RETRYABLE',error=?,updated=? WHERE run_id=?",(error[:2000],time.time(),run_id))
    def mark_reconciliation_required(self, run_id: str, step_key: str, reason: str):
        """Quarantine an expired RUNNING step; never retry an ambiguous side effect."""
        cur=self.db.execute("""UPDATE steps SET state='RECONCILIATION_REQUIRED',error=?,updated=?
          WHERE run_id=? AND step_key=? AND state='RUNNING'""",
          (reason[:2000],time.time(),run_id,step_key))
        if cur.rowcount != 1:
            raise ExecutionError("step is not RUNNING or was already reconciled")
        self.db.execute("UPDATE runs SET state='RECONCILIATION_REQUIRED',error=?,updated=? WHERE run_id=?",
                        (reason[:2000],time.time(),run_id))
        return self.get_step(run_id,step_key)

    def resolve_reconciliation(self, run_id: str, step_key: str, outcome: str,
                               output: dict | None = None, evidence: str = ""):
        """Operator resolution for uncertain external effects; evidence is mandatory."""
        if not evidence.strip():
            raise ExecutionError("reconciliation evidence is required")
        if outcome not in {"CONFIRMED_APPLIED", "CONFIRMED_NOT_APPLIED"}:
            raise ExecutionError("outcome must be CONFIRMED_APPLIED or CONFIRMED_NOT_APPLIED")
        row=self.get_step(run_id,step_key)
        if not row or row["state"] != "RECONCILIATION_REQUIRED":
            raise ExecutionError("step is not awaiting reconciliation")
        if outcome == "CONFIRMED_APPLIED":
            if not isinstance(output,dict):
                raise ExecutionError("confirmed applied outcome requires output object")
            self.db.execute("""UPDATE steps SET state='SUCCEEDED',output_json=?,error=NULL,updated=?
              WHERE run_id=? AND step_key=? AND state='RECONCILIATION_REQUIRED'""",
              (json.dumps(output,sort_keys=True),time.time(),run_id,step_key))
            remaining=self.db.execute("SELECT COUNT(*) FROM steps WHERE run_id=? AND state!='SUCCEEDED'",(run_id,)).fetchone()[0]
            new_state="SUCCEEDED" if remaining==1 else "RECONCILIATION_REQUIRED"
        else:
            self.db.execute("""UPDATE steps SET state='FAILED',error=?,updated=?
              WHERE run_id=? AND step_key=? AND state='RECONCILIATION_REQUIRED'""",
              (("Reconciled not applied: "+evidence)[:2000],time.time(),run_id,step_key))
            new_state="RETRYABLE"
        self.db.execute("UPDATE runs SET state=?,error=NULL,updated=? WHERE run_id=?",
                        (new_state,time.time(),run_id))
        return self.get_step(run_id,step_key)

    def recoverable(self):
        return [dict(r) for r in self.db.execute(
          "SELECT * FROM steps WHERE state IN ('PENDING','FAILED') ORDER BY run_id,ordinal")]
    def get_step(self,run_id,step_key):
        r=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_key=?",(run_id,step_key)).fetchone()
        return dict(r) if r else None
    def get_run(self,run_id):
        r=self.db.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
        return dict(r) if r else None

class ResumableExecutor:
    """Executes one planned step; callers resume by scanning ledger.recoverable()."""
    def __init__(self, ledger: ExecutionLedger, tools: dict[str,Callable[[dict,str],dict]], max_attempts=3):
        self.ledger,self.tools,self.max_attempts=ledger,tools,max_attempts
    def execute(self,run_id: str,step_key: str):
        claim=self.ledger.claim(run_id,step_key,self.max_attempts)
        if not claim["claimed"]: return claim
        s=claim["step"]
        try:
            if s["tool_name"] not in self.tools: raise ExecutionError("tool not registered")
            output=self.tools[s["tool_name"]](json.loads(s["input_json"]),s["idempotency_key"])
            if not isinstance(output,dict): raise ExecutionError("tool output must be object")
            self.ledger.succeed(run_id,step_key,output)
            return {"claimed":True,"state":"SUCCEEDED","output":output}
        except Exception as e:
            self.ledger.fail(run_id,step_key,f"{type(e).__name__}: {e}")
            raise

class OpenAICompatibleAdapter:
    """OpenAI-compatible Chat Completions adapter. Live network use is opt-in."""
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float=30,
                 transport=None):
        if not base_url.startswith("https://") and not base_url.startswith("http://localhost"):
            raise ValueError("base_url must use HTTPS (localhost allowed for development)")
        if not api_key or not model: raise ValueError("api_key and model are required")
        self.base_url=base_url.rstrip("/"); self.api_key=api_key; self.model=model
        self.timeout=timeout; self.transport=transport
    def generate(self, *, system: str, user: str, temperature: float=0.0):
        body={"model":self.model,"temperature":temperature,
              "response_format":{"type":"json_object"},
              "messages":[{"role":"system","content":system},{"role":"user","content":user}]}
        data=json.dumps(body).encode()
        if self.transport:
            raw=self.transport(self.base_url+"/chat/completions",self.api_key,data,self.timeout)
        else:
            from urllib.request import Request,urlopen
            req=Request(self.base_url+"/chat/completions",data=data,headers={
                "Authorization":"Bearer "+self.api_key,"Content-Type":"application/json"})
            with urlopen(req,timeout=self.timeout) as response: raw=response.read()
        parsed=json.loads(raw)
        content=parsed["choices"][0]["message"]["content"]
        return {"output":json.loads(content),"provider":"openai-compatible",
                "model":parsed.get("model",self.model),
                "usage":parsed.get("usage",{})}


class LeasedResumableExecutor:
    """Lease-coordinated executor with explicit quarantine of ambiguous crash outcomes.

    Tool signature: tool(inputs, idempotency_key, fencing_token). Downstream systems
    should persist idempotency keys and reject stale fencing tokens themselves.
    """
    def __init__(self, ledger: ExecutionLedger, lease_ledger, tools: dict[str,Callable],
                 worker_id: str, lease_ttl: float = 30.0, max_attempts: int = 3):
        if not worker_id or lease_ttl <= 0:
            raise ValueError("worker_id and positive lease_ttl are required")
        self.ledger=ledger
        self.lease_ledger=lease_ledger
        self.tools=tools
        self.worker_id=worker_id
        self.lease_ttl=lease_ttl
        self.max_attempts=max_attempts

    @staticmethod
    def _resource(run_id, step_key):
        return f"agentops-step:{run_id}:{step_key}"

    def execute(self, run_id: str, step_key: str, now: float | None = None):
        resource=self._resource(run_id,step_key)
        acquired=self.lease_ledger.acquire(resource,self.worker_id,self.lease_ttl,now=now)
        if not acquired["acquired"]:
            return {"claimed":False,"reason":"lease_active","lease":acquired["lease"]}
        token=acquired["lease"]["fencing_token"]
        claim=self.ledger.claim(run_id,step_key,self.max_attempts)
        if not claim["claimed"]:
            self.lease_ledger.release(resource,self.worker_id,token)
            return claim
        step=claim["step"]
        tool_started=False
        try:
            tool=self.tools.get(step["tool_name"])
            if tool is None:
                raise ExecutionError("tool not registered")
            tool_started=True
            output=tool(json.loads(step["input_json"]),step["idempotency_key"],token)
            if not isinstance(output,dict):
                raise ExecutionError("tool output must be object")
            current=self.lease_ledger.get(resource)
            clock=time.time() if now is None else float(now)
            if (not current or current["owner"] != self.worker_id or
                current["fencing_token"] != token or current["lease_until"] <= clock):
                raise ExecutionError("lease lost or fencing token superseded before commit")
            self.ledger.succeed(run_id,step_key,output)
            return {"claimed":True,"state":"SUCCEEDED","output":output,"fencing_token":token}
        except Exception as exc:
            # Once a tool was invoked, an exception does not prove that its side effect failed.
            # Quarantine it even if this worker still owns the lease; require external reconciliation.
            reason=("External tool was invoked but did not yield a committed result; "
                    "side-effect outcome is uncertain: "+f"{type(exc).__name__}: {exc}")
            if tool_started:
                self.ledger.mark_reconciliation_required(run_id,step_key,reason)
            else:
                self.ledger.fail(run_id,step_key,f"{type(exc).__name__}: {exc}")
            raise
        finally:
            self.lease_ledger.release(resource,self.worker_id,token)

    def quarantine_expired_running(self, now: float | None = None):
        """Move expired RUNNING steps to reconciliation; never auto-replay them."""
        clock=time.time() if now is None else float(now)
        rows=self.ledger.db.execute("SELECT run_id,step_key FROM steps WHERE state='RUNNING'").fetchall()
        quarantined=[]
        for row in rows:
            resource=self._resource(row["run_id"],row["step_key"])
            lease=self.lease_ledger.get(resource)
            if not lease or lease["lease_until"] <= clock:
                quarantined.append(self.ledger.mark_reconciliation_required(
                    row["run_id"],row["step_key"],
                    "Worker lease expired; external side-effect outcome must be reconciled before retry."))
        return quarantined
