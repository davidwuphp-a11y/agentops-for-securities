import unittest
from agentops.core import Store, Principal, ToolRegistry, ControlError
from agentops.runtime import AgentRuntime, AgentSpec, FixtureModel, EvidenceGraph, EvaluationEngine

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.s=Store(); self.cid=self.s.create_case('RUNTIME-1')
        self.s.transition(self.cid,'IN_REVIEW','system',1)
        self.eid=self.s.add_evidence(self.cid,'INCORPORATION_DOCUMENT','synthetic doc','synthetic://doc',True)
        self.registry=ToolRegistry(); self.registry.register('lookup',{'analyst'},lambda x:{'found':x['key']})
        self.runtime=AgentRuntime(self.s,self.registry)
        self.principal=Principal('agent-user',frozenset({'analyst'}))
    def tearDown(self):
        self.s.close()
    def test_fixture_agent_executes_allowlisted_tool(self):
        model=FixtureModel({'conclusion':'document present','evidence_ids':[self.eid],'tool_calls':[{'name':'lookup','input':{'key':'ABC'}}]})
        spec=AgentSpec('document-agent','analyst','Extract and verify.',frozenset({'lookup'}),1)
        result=self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='check document')
        self.assertEqual(result.status,'SUCCEEDED'); self.assertEqual(result.trace[0]['result'],{'found':'ABC'})
    def test_agent_cannot_call_non_allowlisted_tool(self):
        model=FixtureModel({'tool_calls':[{'name':'admin','input':{}}]})
        spec=AgentSpec('bad-agent','analyst','Nope.',frozenset({'lookup'}),1)
        with self.assertRaises(ControlError): self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='bad')
    def test_agent_cannot_cite_other_case_evidence(self):
        other=self.s.create_case('OTHER'); foreign=self.s.add_evidence(other,'X','x','synthetic://x')
        model=FixtureModel({'evidence_ids':[foreign]})
        spec=AgentSpec('agent','analyst','Check.',frozenset())
        with self.assertRaises(ControlError): self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='cite')
    def test_role_required(self):
        model=FixtureModel({}); spec=AgentSpec('agent','compliance','Check.')
        with self.assertRaises(ControlError): self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='x')
    def test_step_budget(self):
        model=FixtureModel({'tool_calls':[{'name':'lookup','input':{'key':'A'}},{'name':'lookup','input':{'key':'B'}}]})
        spec=AgentSpec('agent','analyst','Check.',frozenset({'lookup'}),1)
        with self.assertRaises(ControlError): self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='x')
    def test_evidence_graph(self):
        self.s.add_finding(self.cid,'F1','supported',[self.eid])
        graph=EvidenceGraph(self.s).export(self.cid)
        self.assertEqual(len(graph['nodes']),2); self.assertEqual(graph['edges'][0]['type'],'SUPPORTS')
    def test_evaluator(self):
        result=EvaluationEngine.evaluate(expected={'conclusion':'yes'},actual={'conclusion':'yes','evidence_ids':[self.eid]},allowed_evidence_ids={self.eid})
        self.assertTrue(result['conclusion_match']); self.assertEqual(result['evidence_precision'],1.0); self.assertTrue(result['policy_compliant'])
    def test_evaluator_flags_unsupported(self):
        result=EvaluationEngine.evaluate(expected={'conclusion':'yes'},actual={'conclusion':'yes','evidence_ids':['bogus']},allowed_evidence_ids={self.eid})
        self.assertFalse(result['policy_compliant']); self.assertEqual(result['unsupported_evidence_ids'],['bogus'])

if __name__=='__main__': unittest.main()

class Phase5RuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        from agentops.phase5 import VersionRegistry
        self.s=Store(); self.cid=self.s.create_case('PHASE5-RUNTIME')
        self.s.transition(self.cid,'IN_REVIEW','system')
        self.registry=ToolRegistry(); self.calls=[]
        self.registry.register('write',{'analyst'},lambda x:self.calls.append(x) or {'ok':True})
        self.versions=VersionRegistry()
        self.runtime=AgentRuntime(self.s,self.registry,self.versions)
        self.principal=Principal('agent',frozenset({'analyst'}))
    def tearDown(self):
        self.s.close(); self.versions.close()
    def test_output_schema_rejected_before_any_tool_execution(self):
        spec=AgentSpec('agent','analyst','system',frozenset({'write'}),1,
                       output_schema={'type':'object','required':['decision']})
        model=FixtureModel({'tool_calls':[{'name':'write','input':{'x':1}}]})
        with self.assertRaises(ControlError):
            self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=model,task='x')
        self.assertEqual(self.calls,[])
    def test_prompt_and_policy_versions_are_verified_and_bound(self):
        prompt='Use only verified evidence.'
        self.versions.register('PROMPT','kyc-agent','1.0',prompt)
        self.versions.register('POLICY','kyc-policy','2.0',{'allow_approval':True})
        spec=AgentSpec('agent','analyst',prompt,frozenset(),1,
                       output_schema={'type':'object'},prompt_name='kyc-agent',prompt_version='1.0',
                       policy_name='kyc-policy',policy_version='2.0')
        result=self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,
                                model=FixtureModel({'conclusion':'review'}),task='review')
        record=self.s.db.execute("SELECT input_json FROM tool_runs WHERE case_id=? AND tool='__agent_run__'",(self.cid,)).fetchone()
        logged=__import__('json').loads(record['input_json'])['request']
        self.assertEqual(logged['prompt_registry_digest'],self.versions.get('PROMPT','kyc-agent','1.0')['digest'])
        self.assertEqual(logged['policy_registry_digest'],self.versions.get('POLICY','kyc-policy','2.0')['digest'])
    def test_prompt_version_digest_mismatch_fails_before_model_call(self):
        self.versions.register('PROMPT','kyc-agent','1.0','approved prompt')
        spec=AgentSpec('agent','analyst','modified prompt',frozenset(),1,
                       prompt_name='kyc-agent',prompt_version='1.0')
        class NeverCalled:
            def generate(self,**kwargs): raise AssertionError('model should not be called')
        with self.assertRaises(ControlError):
            self.runtime.run(case_id=self.cid,spec=spec,principal=self.principal,model=NeverCalled(),task='x')
