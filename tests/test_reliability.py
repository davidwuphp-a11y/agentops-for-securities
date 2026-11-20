import json, os, tempfile, unittest
from agentops.reliability import ExecutionLedger, ResumableExecutor, ExecutionError, OpenAICompatibleAdapter

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,"ledger.db")
        self.ledger=ExecutionLedger(self.path)
        self.rid=self.ledger.create_run("CASE-1",{"task":"screen"})
        self.ledger.plan_step(self.rid,1,"lookup",{"ticker":"ABC"},"lookup-1")
    def tearDown(self):
        self.ledger.close(); self.tmp.cleanup()
    def test_persists_across_reopen(self):
        self.ledger.close()
        self.ledger=ExecutionLedger(self.path)
        self.assertEqual(self.ledger.get_run(self.rid)["state"],"PENDING")
        self.assertEqual(len(self.ledger.recoverable()),1)
    def test_idempotency_key_stable(self):
        a=self.ledger.get_step(self.rid,"lookup-1")["idempotency_key"]
        self.ledger.plan_step(self.rid,1,"lookup",{"ticker":"ABC"},"lookup-1")
        b=self.ledger.get_step(self.rid,"lookup-1")["idempotency_key"]
        self.assertEqual(a,b)
    def test_step_key_cannot_be_reused_with_new_input(self):
        with self.assertRaises(ExecutionError):
            self.ledger.plan_step(self.rid,1,"lookup",{"ticker":"XYZ"},"lookup-1")
    def test_executor_succeeds_and_does_not_repeat_success(self):
        calls=[]
        ex=ResumableExecutor(self.ledger,{"lookup":lambda data,key:(calls.append((data,key)) or {"price":10})})
        first=ex.execute(self.rid,"lookup-1")
        second=ex.execute(self.rid,"lookup-1")
        self.assertEqual(first["state"],"SUCCEEDED")
        self.assertEqual(second["reason"],"already_succeeded")
        self.assertEqual(len(calls),1)
    def test_failure_is_recoverable(self):
        ex=ResumableExecutor(self.ledger,{"lookup":lambda data,key:(_ for _ in ()).throw(TimeoutError("late"))})
        with self.assertRaises(TimeoutError): ex.execute(self.rid,"lookup-1")
        self.assertEqual(self.ledger.get_step(self.rid,"lookup-1")["state"],"FAILED")
        self.assertEqual(len(self.ledger.recoverable()),1)
    def test_attempt_limit_dead_letters(self):
        for _ in range(2):
            claim=self.ledger.claim(self.rid,"lookup-1",max_attempts=2)
            self.assertTrue(claim["claimed"])
            self.ledger.fail(self.rid,"lookup-1","failure")
        result=self.ledger.claim(self.rid,"lookup-1",max_attempts=2)
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"],"attempt_limit")
    def test_running_step_not_double_claimed(self):
        self.assertTrue(self.ledger.claim(self.rid,"lookup-1")["claimed"])
        self.assertEqual(self.ledger.claim(self.rid,"lookup-1")["reason"],"already_running")
    def test_provider_adapter_parses_json(self):
        def fake(url,key,data,timeout):
            body=json.loads(data)
            self.assertEqual(body["model"],"unit-test")
            return json.dumps({"model":"unit-test","choices":[{"message":{"content":'{"risk":"low"}'}}],"usage":{"total_tokens":12}}).encode()
        adapter=OpenAICompatibleAdapter("https://api.example.test/v1","secret","unit-test",transport=fake)
        result=adapter.generate(system="sys",user="user")
        self.assertEqual(result["output"],{"risk":"low"})
        self.assertEqual(result["usage"]["total_tokens"],12)
    def test_provider_rejects_insecure_remote_endpoint(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleAdapter("http://remote.test/v1","secret","m")

if __name__=="__main__": unittest.main()
