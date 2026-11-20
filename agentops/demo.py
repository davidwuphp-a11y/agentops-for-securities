from .core import Store, PolicyGate, Principal, ToolRegistry, Replay

def run_demo(db_path=':memory:'):
    s=Store(db_path); cid=s.create_case('CASE-DEMO-0001')
    s.transition(cid,'IN_REVIEW','workflow-orchestrator',1)
    e1=s.add_evidence(cid,'INCORPORATION_DOCUMENT','synthetic incorporation certificate','synthetic://case/registration.pdf',True,'document-agent')
    e2=s.add_evidence(cid,'OWNERSHIP_STRUCTURE','synthetic ownership chart','synthetic://case/ownership.pdf',True,'ubo-agent')
    e3=s.add_evidence(cid,'AUTHORIZED_SIGNATORY','synthetic board authorization','synthetic://case/authority.pdf',True,'document-agent')
    s.add_finding(cid,'DOC-COMPLETE','Required institutional onboarding documents are present and verified.',[e1,e2,e3])
    gate=PolicyGate().evaluate_for_approval(s,cid)
    if gate['allowed']: s.transition(cid,'PENDING_APPROVAL','policy-gate',2)
    s.approve(cid,'relationship-manager','compliance-checker','APPROVE')
    result={"case":s.case(cid),"policy_gate":gate,"audit_chain_valid":s.verify_audit_chain(cid),"replay":Replay.replay_tool_runs(s,cid),"events":len(s.event_log(cid))}
    s.close()
    return result

if __name__=='__main__':
    import json; print(json.dumps(run_demo(),indent=2))
