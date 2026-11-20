import tempfile, os, unittest
from agentops.core import Store, ControlError, PolicyGate, Principal, ToolRegistry, Replay

class RuntimeTests(unittest.TestCase):
 def setUp(self): self.s=Store(); self.cid=self.s.create_case('C1')
 def tearDown(self): self.s.close()
 def test_case_persists_after_reopen(self):
  fd,p=tempfile.mkstemp(); os.close(fd)
  try:
   a=Store(p); a.create_case('PERSIST'); b=Store(p); self.assertEqual(b.case('PERSIST')['status'],'RECEIVED'); a.close(); b.close()
  finally: os.unlink(p)
 def test_optimistic_version(self):
  with self.assertRaises(ControlError): self.s.transition(self.cid,'IN_REVIEW','x',99)
 def test_invalid_transition(self):
  with self.assertRaises(ControlError): self.s.transition(self.cid,'APPROVED','x')
 def test_evidence_scoped_to_case(self):
  other=self.s.create_case('C2'); e=self.s.add_evidence(other,'X','data','src')
  with self.assertRaises(ControlError): self.s.add_finding(self.cid,'F','claim',[e])
 def test_finding_requires_evidence(self):
  with self.assertRaises(ControlError): self.s.add_finding(self.cid,'F','claim',[])
 def test_policy_blocks_missing_evidence(self):
  self.assertFalse(PolicyGate().evaluate_for_approval(self.s,self.cid)['allowed'])
 def test_cannot_enter_approval_without_policy_gate(self):
  self.s.transition(self.cid,'IN_REVIEW','x')
  with self.assertRaises(ControlError): self.s.transition(self.cid,'PENDING_APPROVAL','x')
 def test_case_evidence_is_frozen_after_submission(self):
  for k in PolicyGate.REQUIRED_EVIDENCE: self.s.add_evidence(self.cid,k,k,'src',True)
  ids=[r['id'] for r in self.s.db.execute('select id from evidence where case_id=?',(self.cid,))]
  self.s.add_finding(self.cid,'F','supported',ids)
  self.s.transition(self.cid,'IN_REVIEW','x')
  self.s.transition(self.cid,'PENDING_APPROVAL','x')
  with self.assertRaises(ControlError): self.s.add_evidence(self.cid,'EXTRA','x','src')
  with self.assertRaises(ControlError): self.s.add_finding(self.cid,'F2','new',[ids[0]])
 def test_policy_passes_with_verified_evidence_and_finding(self):
  ids=[self.s.add_evidence(self.cid,k,k,'synthetic://x',True) for k in PolicyGate.REQUIRED_EVIDENCE]
  self.s.add_finding(self.cid,'F','supported',ids)
  self.assertTrue(PolicyGate().evaluate_for_approval(self.s,self.cid)['allowed'])
 def test_maker_checker_separation(self):
  self.s.transition(self.cid,'IN_REVIEW','x');
  for k in PolicyGate.REQUIRED_EVIDENCE: ids=[self.s.add_evidence(self.cid,k,k,'src',True)]
  ev=[r['id'] for r in self.s.db.execute('select id from evidence where case_id=?',(self.cid,))]
  self.s.add_finding(self.cid,'F','supported',ev); self.s.transition(self.cid,'PENDING_APPROVAL','x')
  with self.assertRaises(ControlError): self.s.approve(self.cid,'same','same','APPROVE')
 def test_tool_rbac(self):
  reg=ToolRegistry(); reg.register('lookup',{'compliance'},lambda x:{'ok':True})
  with self.assertRaises(ControlError): reg.invoke('lookup',Principal('agent',frozenset({'sales'})),self.s,self.cid,{})
 def test_tool_call_is_audited_and_replayable(self):
  reg=ToolRegistry(); reg.register('lookup',{'compliance'},lambda x:{'risk':'low'})
  reg.invoke('lookup',Principal('c1',frozenset({'compliance'})),self.s,self.cid,{'entity':'ACME-SYNTH'})
  self.assertEqual(Replay.replay_tool_runs(self.s,self.cid)[0]['recorded_output'],{'risk':'low'})
  self.assertTrue(self.s.verify_audit_chain(self.cid))
 def test_audit_tamper_detected(self):
  self.s._event(self.cid,'a','TEST',{'x':1}); self.s.db.commit()
  self.s.db.execute("UPDATE events SET payload='{}' WHERE case_id=?",(self.cid,)); self.s.db.commit()
  self.assertFalse(self.s.verify_audit_chain(self.cid))
 def test_terminal_state_locked(self):
  self.s.transition(self.cid,'IN_REVIEW','x')
  for k in PolicyGate.REQUIRED_EVIDENCE: self.s.add_evidence(self.cid,k,k,'src',True)
  ev=[r['id'] for r in self.s.db.execute('select id from evidence where case_id=?',(self.cid,))]
  self.s.add_finding(self.cid,'F','supported',ev); self.s.transition(self.cid,'PENDING_APPROVAL','x'); self.s.approve(self.cid,'maker','checker','APPROVE')
  with self.assertRaises(ControlError): self.s.transition(self.cid,'ESCALATED','x')

if __name__=='__main__': unittest.main()

class ApprovalSnapshotTests(unittest.TestCase):
 def setUp(self):
  self.s=Store(); self.cid=self.s.create_case('SNAPSHOT-1')
  ids=[self.s.add_evidence(self.cid,k,k,'synthetic://evidence',True) for k in PolicyGate.REQUIRED_EVIDENCE]
  self.s.add_finding(self.cid,'F-1','Synthetic evidence supports the finding',ids,'kyc-policy-1.2')
  self.s.transition(self.cid,'IN_REVIEW','maker')
  self.s.transition(self.cid,'PENDING_APPROVAL','maker')
 def tearDown(self): self.s.close()
 def test_approval_binds_task_digest_and_policy_version(self):
  aid=self.s.approve(self.cid,'maker-1','checker-1','APPROVE')
  row=self.s.db.execute('SELECT * FROM approvals WHERE id=?',(aid,)).fetchone()
  self.assertEqual(len(row['task_digest']),64)
  self.assertEqual(__import__('json').loads(row['policy_versions']),['kyc-policy-1.2'])
  self.assertTrue(self.s.verify_approval_snapshot(aid))
 def test_snapshot_verification_detects_out_of_band_mutation(self):
  aid=self.s.approve(self.cid,'maker-1','checker-1','APPROVE')
  self.s.db.execute("UPDATE findings SET conclusion='tampered' WHERE case_id=?",(self.cid,))
  self.s.db.commit()
  self.assertFalse(self.s.verify_approval_snapshot(aid))
