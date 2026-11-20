"""Agent runtime primitives: model adapters, bounded tool plans and evidence-aware execution.
This is a local research prototype; no live model provider is called by default.
"""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field
from typing import Any, Protocol
from .core import ControlError, Principal, Store, ToolRegistry
from .phase5 import JsonSchemaValidator, SchemaValidationError

class ModelAdapter(Protocol):
    def generate(self, *, system: str, user: str, temperature: float = 0.0) -> dict[str, Any]: ...

class FixtureModel:
    """Deterministic offline model fixture for tests and reproducible demos."""
    def __init__(self, response: dict[str, Any]): self.response = response
    def generate(self, *, system: str, user: str, temperature: float = 0.0):
        return {"output": self.response, "provider": "fixture", "model": "fixture-v1", "usage": {"input_tokens": 0, "output_tokens": 0}}

@dataclass
class AgentSpec:
    name: str
    role: str
    system_prompt: str
    allowed_tools: frozenset[str] = frozenset()
    max_steps: int = 4
    output_schema: dict[str, Any] | None = None
    prompt_name: str | None = None
    prompt_version: str | None = None
    policy_name: str | None = None
    policy_version: str | None = None

@dataclass
class AgentResult:
    run_id: str
    agent: str
    status: str
    output: dict[str, Any]
    evidence_ids: list[str]
    trace: list[dict[str, Any]] = field(default_factory=list)

class AgentRuntime:
    def __init__(self, store: Store, registry: ToolRegistry, version_registry=None):
        self.store, self.registry = store, registry
        self.version_registry = version_registry

    def run(self, *, case_id: str, spec: AgentSpec, principal: Principal,
            model: ModelAdapter, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        run_id = str(uuid.uuid4()); trace=[]; evidence_ids=[]
        if spec.role not in principal.roles:
            raise ControlError("principal lacks agent role")
        prompt_digest=hashlib.sha256(spec.system_prompt.encode("utf-8")).hexdigest()
        prompt_record=None; policy_record=None
        if spec.prompt_name or spec.prompt_version:
            if not (spec.prompt_name and spec.prompt_version and self.version_registry):
                raise ControlError("prompt name/version require a configured version registry")
            prompt_record=self.version_registry.get("PROMPT",spec.prompt_name,spec.prompt_version)
            if not prompt_record or prompt_record["digest"] != prompt_digest:
                raise ControlError("prompt version missing or digest does not match active system prompt")
        if spec.policy_name or spec.policy_version:
            if not (spec.policy_name and spec.policy_version and self.version_registry):
                raise ControlError("policy name/version require a configured version registry")
            policy_record=self.version_registry.get("POLICY",spec.policy_name,spec.policy_version)
            if not policy_record:
                raise ControlError("policy version is not registered")
        request = {"task": task, "context": context or {}, "allowed_tools": sorted(spec.allowed_tools),
                   "max_steps": spec.max_steps, "prompt_digest":prompt_digest,
                   "prompt_name":spec.prompt_name,"prompt_version":spec.prompt_version,
                   "prompt_registry_digest":prompt_record["digest"] if prompt_record else None,
                   "policy_name":spec.policy_name,"policy_version":spec.policy_version,
                   "policy_registry_digest":policy_record["digest"] if policy_record else None}
        started=time.time()
        try:
            response=model.generate(system=spec.system_prompt, user=json.dumps(request, sort_keys=True), temperature=0.0)
            output=response.get("output", {})
            if not isinstance(output, dict): raise ControlError("agent output must be a JSON object")
            if spec.output_schema is not None:
                try:
                    JsonSchemaValidator.validate(output,spec.output_schema)
                except SchemaValidationError as exc:
                    raise ControlError("agent output schema rejected: "+str(exc)) from exc
            # The runtime accepts evidence references only if they belong to this case.
            for eid in output.get("evidence_ids", []):
                if not self.store.evidence(case_id, eid): raise ControlError("agent cited evidence outside this case")
                evidence_ids.append(eid)
            calls=output.get("tool_calls", [])
            if not isinstance(calls, list): raise ControlError("tool_calls must be a list")
            # Validate the complete plan before executing any side-effecting tool.
            if len(calls) > spec.max_steps: raise ControlError("agent step budget exceeded")
            for call in calls:
                if not isinstance(call, dict) or call.get("name") not in spec.allowed_tools:
                    raise ControlError("tool is not in agent allowlist")
            for step, call in enumerate(calls, start=1):
                name=call["name"]
                result=self.registry.invoke(name, principal, self.store, case_id, call.get("input", {}))
                trace.append({"step":step,"tool":name,"result":result})
            status="SUCCEEDED"
            self.store.record_tool_run(case_id, "__agent_run__", principal.name,
                {"run_id":run_id,"agent":spec.name,"task":task,"request":request},
                {"status":status,"output":output,"trace":trace,"provider":response.get("provider"),"model":response.get("model"),"usage":response.get("usage",{})})
            return AgentResult(run_id,spec.name,status,output,evidence_ids,trace)
        except Exception as exc:
            status="FAILED"
            self.store.record_tool_run(case_id, "__agent_run__", principal.name,
                {"run_id":run_id,"agent":spec.name,"task":task,"request":request},
                {"status":status,"error_type":type(exc).__name__,"error":str(exc),"elapsed_ms":round((time.time()-started)*1000,2)})
            raise

class EvidenceGraph:
    """Read-only graph projection over case evidence and findings."""
    def __init__(self, store: Store): self.store=store
    def export(self, case_id: str) -> dict[str, Any]:
        evidence=self.store.db.execute("SELECT id,kind,digest,source,verified FROM evidence WHERE case_id=? ORDER BY created",(case_id,)).fetchall()
        findings=self.store.findings(case_id)
        nodes=[]; edges=[]
        for e in evidence:
            nodes.append({"id":e["id"],"type":"EVIDENCE","kind":e["kind"],"digest":e["digest"],"source":e["source"],"verified":bool(e["verified"])})
        for f in findings:
            nodes.append({"id":f["id"],"type":"FINDING","code":f["code"],"conclusion":f["conclusion"],"rule_version":f["rule_version"]})
            for eid in json.loads(f["evidence_ids"]): edges.append({"from":eid,"to":f["id"],"type":"SUPPORTS"})
        return {"case_id":case_id,"nodes":nodes,"edges":edges}

class EvaluationEngine:
    """Small deterministic evaluator; production metrics need adjudicated gold labels."""
    @staticmethod
    def evaluate(*, expected: dict[str, Any], actual: dict[str, Any], allowed_evidence_ids: set[str]) -> dict[str, Any]:
        expected_conclusion=expected.get("conclusion")
        actual_conclusion=actual.get("conclusion")
        cited=set(actual.get("evidence_ids", []))
        unsupported=sorted(cited-allowed_evidence_ids)
        return {
            "conclusion_match": expected_conclusion == actual_conclusion,
            "evidence_precision": (len(cited & allowed_evidence_ids)/len(cited)) if cited else 0.0,
            "unsupported_evidence_ids": unsupported,
            "policy_compliant": not unsupported and bool(cited),
        }
