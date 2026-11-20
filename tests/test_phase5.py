import tempfile
import unittest

from agentops.phase5 import (
    LeaseLedger, JsonSchemaValidator, SchemaValidationError,
    VersionRegistry, Phase5Error,
)


class LeaseLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = LeaseLedger()

    def tearDown(self):
        self.db.close()

    def test_active_lease_cannot_be_stolen(self):
        first = self.db.acquire("run-1", "worker-a", 10, now=100)
        second = self.db.acquire("run-1", "worker-b", 10, now=105)
        self.assertTrue(first["acquired"])
        self.assertFalse(second["acquired"])

    def test_expired_lease_takeover_increments_fencing_token(self):
        first = self.db.acquire("run-1", "worker-a", 10, now=100)
        second = self.db.acquire("run-1", "worker-b", 10, now=111)
        self.assertTrue(second["acquired"])
        self.assertEqual(second["lease"]["fencing_token"], first["lease"]["fencing_token"] + 1)

    def test_old_owner_cannot_heartbeat_or_release_after_takeover(self):
        first = self.db.acquire("run-1", "worker-a", 10, now=100)["lease"]
        second = self.db.acquire("run-1", "worker-b", 10, now=111)["lease"]
        self.assertFalse(self.db.heartbeat("run-1", "worker-a", first["fencing_token"], 10, now=112))
        self.assertFalse(self.db.release("run-1", "worker-a", first["fencing_token"]))
        self.assertEqual(self.db.get("run-1")["owner"], "worker-b")
        self.assertTrue(self.db.heartbeat("run-1", "worker-b", second["fencing_token"], 10, now=112))

    def test_persists_across_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/leases.db"
            a = LeaseLedger(path)
            a.acquire("r", "w", 5, now=10)
            a.close()
            b = LeaseLedger(path)
            self.assertEqual(b.get("r")["owner"], "w")
            b.close()


class SchemaValidatorTests(unittest.TestCase):
    def test_valid_nested_object(self):
        schema = {"type": "object", "required": ["name", "scores"],
                  "additionalProperties": False,
                  "properties": {"name": {"type": "string", "minLength": 2},
                                 "scores": {"type": "array", "items": {"type": "number"}}}}
        JsonSchemaValidator.validate({"name": "ACME", "scores": [1, 2.5]}, schema)

    def test_rejects_missing_required(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate({}, {"type": "object", "required": ["x"]})

    def test_rejects_additional_property(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate({"x": 1, "y": 2},
                {"type": "object", "properties": {"x": {"type": "integer"}}, "additionalProperties": False})

    def test_rejects_wrong_type_and_boolean_as_integer(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate(True, {"type": "integer"})

    def test_unsupported_keyword_fails_closed(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate("abc", {"type": "string", "pattern": "^[a-z]+$"})

    def test_enum_and_bounds(self):
        JsonSchemaValidator.validate(3, {"type": "integer", "enum": [2, 3, 4], "minimum": 1, "maximum": 5})
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate(9, {"type": "integer", "maximum": 5})


class VersionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = VersionRegistry()

    def tearDown(self):
        self.registry.close()

    def test_register_and_digest(self):
        row = self.registry.register("POLICY", "kyc", "1.0", {"threshold": 5, "enabled": True})
        self.assertEqual(len(row["digest"]), 64)
        self.assertEqual(self.registry.get("POLICY", "kyc", "1.0")["digest"], row["digest"])

    def test_same_version_is_idempotent_but_immutable(self):
        first = self.registry.register("PROMPT", "screening", "1", "prompt text")
        second = self.registry.register("PROMPT", "screening", "1", "prompt text")
        self.assertEqual(first["digest"], second["digest"])
        with self.assertRaises(Phase5Error):
            self.registry.register("PROMPT", "screening", "1", "changed prompt")

    def test_rejects_invalid_kind(self):
        with self.assertRaises(Phase5Error):
            self.registry.register("OTHER", "x", "1", "content")


if __name__ == "__main__":
    unittest.main()

class LeasedExecutionIntegrationTests(unittest.TestCase):
    def setUp(self):
        import os
        from agentops.reliability import ExecutionLedger
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,'execution.db')
        self.execution=ExecutionLedger(self.path)
        self.leases=LeaseLedger(self.path)
        self.run_id=self.execution.create_run('case-1',{'purpose':'test'})
        self.execution.plan_step(self.run_id,1,'external_action',{'amount':10},'payment')

    def tearDown(self):
        self.execution.close(); self.leases.close(); self.tmp.cleanup()

    def test_leased_executor_passes_fencing_token_and_succeeds(self):
        from agentops.reliability import LeasedResumableExecutor
        seen=[]
        def tool(inputs, idem, token):
            seen.append((inputs,idem,token))
            return {'accepted':True}
        executor=LeasedResumableExecutor(self.execution,self.leases,
            {'external_action':tool},'worker-a',lease_ttl=10)
        result=executor.execute(self.run_id,'payment')
        self.assertEqual(result['state'],'SUCCEEDED')
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0][2],result['fencing_token'])

    def test_expired_running_step_is_quarantined_not_replayed(self):
        self.execution.claim(self.run_id,'payment')
        executor=__import__('agentops.reliability',fromlist=['LeasedResumableExecutor']).LeasedResumableExecutor(
            self.execution,self.leases,{},'worker-b',lease_ttl=10)
        quarantined=executor.quarantine_expired_running(now=10**12)
        self.assertEqual(len(quarantined),1)
        self.assertEqual(quarantined[0]['state'],'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execution.recoverable(),[])

    def test_reconciliation_requires_evidence_and_never_guesses(self):
        from agentops.reliability import ExecutionError
        self.execution.claim(self.run_id,'payment')
        self.execution.mark_reconciliation_required(self.run_id,'payment','worker crashed')
        with self.assertRaises(ExecutionError):
            self.execution.resolve_reconciliation(self.run_id,'payment','CONFIRMED_NOT_APPLIED')
        resolved=self.execution.resolve_reconciliation(self.run_id,'payment',
            'CONFIRMED_NOT_APPLIED',evidence='Downstream ledger lookup: no transaction')
        self.assertEqual(resolved['state'],'FAILED')
        self.assertEqual(len(self.execution.recoverable()),1)

    def test_confirmed_applied_requires_output(self):
        from agentops.reliability import ExecutionError
        self.execution.claim(self.run_id,'payment')
        self.execution.mark_reconciliation_required(self.run_id,'payment','worker crashed')
        with self.assertRaises(ExecutionError):
            self.execution.resolve_reconciliation(self.run_id,'payment','CONFIRMED_APPLIED',evidence='checked')
        resolved=self.execution.resolve_reconciliation(self.run_id,'payment','CONFIRMED_APPLIED',
            output={'transaction_id':'synthetic-1'},evidence='Downstream confirms transaction')
        self.assertEqual(resolved['state'],'SUCCEEDED')

    def test_lease_takeover_blocks_stale_worker_result(self):
        from agentops.reliability import LeasedResumableExecutor, ExecutionError
        # The simulated tool lets its lease expire and another worker take it over.
        def slow_tool(inputs, idem, token):
            lease=self.leases.acquire('agentops-step:'+self.run_id+':payment','worker-b',10,now=200)
            self.assertTrue(lease['acquired'])
            return {'accepted':True}
        executor=LeasedResumableExecutor(self.execution,self.leases,
            {'external_action':slow_tool},'worker-a',lease_ttl=10)
        with self.assertRaises(ExecutionError):
            executor.execute(self.run_id,'payment',now=100)
        self.assertEqual(self.execution.get_step(self.run_id,'payment')['state'],'RECONCILIATION_REQUIRED')


class SchemaMetaValidationTests(unittest.TestCase):
    def test_rejects_unsupported_keyword_in_unreached_property(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate({}, {'type':'object','properties':{'unused':{'pattern':'x'}}})

    def test_rejects_unsupported_keyword_in_empty_array_items(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate([], {'type':'array','items':{'format':'email'}})

    def test_rejects_invalid_keyword_types_even_if_value_does_not_use_them(self):
        for schema in ({'type':'object','minLength':-1},
                       {'type':'object','required':'x'},
                       {'type':'object','additionalProperties':'yes'},
                       {'type':'object','minimum':True}):
            with self.subTest(schema=schema), self.assertRaises(SchemaValidationError):
                JsonSchemaValidator.validate({},schema)

    def test_rejects_inconsistent_bounds(self):
        with self.assertRaises(SchemaValidationError):
            JsonSchemaValidator.validate('x',{'type':'string','minLength':5,'maxLength':2})

class AmbiguousToolFailureTests(unittest.TestCase):
    def test_tool_exception_after_invocation_requires_reconciliation(self):
        from agentops.reliability import ExecutionLedger, LeasedResumableExecutor, ExecutionError
        with tempfile.TemporaryDirectory() as d:
            path=d+'/db.sqlite'
            ledger=ExecutionLedger(path); leases=LeaseLedger(path)
            run=ledger.create_run('case',{})
            ledger.plan_step(run,1,'external',{},'s1')
            effects=[]
            def side_effect_then_timeout(inputs, idem, token):
                effects.append({'idempotency_key':idem,'effect':'may-have-occurred'})
                raise TimeoutError('response lost after downstream commit')
            executor=LeasedResumableExecutor(ledger,leases,{'external':side_effect_then_timeout},'worker')
            with self.assertRaises(TimeoutError): executor.execute(run,'s1')
            self.assertEqual(len(effects),1)
            self.assertEqual(ledger.get_step(run,'s1')['state'],'RECONCILIATION_REQUIRED')
            self.assertEqual(ledger.recoverable(),[])
            ledger.close(); leases.close()

class LeaseFencingHardeningTests(unittest.TestCase):
    def setUp(self): self.db=LeaseLedger()
    def tearDown(self): self.db.close()
    def test_release_preserves_monotonic_fencing_counter(self):
        a=self.db.acquire('resource','worker-a',10,now=100)['lease']
        self.assertTrue(self.db.release('resource','worker-a',a['fencing_token']))
        b=self.db.acquire('resource','worker-b',10,now=101)['lease']
        self.assertGreater(b['fencing_token'],a['fencing_token'])

    def test_concurrent_workers_only_one_acquires_active_lease(self):
        import os, threading
        with tempfile.TemporaryDirectory() as d:
            path=os.path.join(d,'leases.sqlite')
            seed=LeaseLedger(path); seed.close()
            barrier=threading.Barrier(8)
            outcomes=[]; errors=[]; lock=threading.Lock()
            def worker(i):
                db=LeaseLedger(path)
                try:
                    barrier.wait()
                    result=db.acquire('shared-resource',f'worker-{i}',30,now=100)
                    with lock: outcomes.append(result['acquired'])
                except Exception as exc:
                    with lock: errors.append(repr(exc))
                finally:
                    db.close()
            threads=[threading.Thread(target=worker,args=(i,)) for i in range(8)]
            for t in threads: t.start()
            for t in threads: t.join()
            self.assertEqual(errors,[])
            self.assertEqual(sum(outcomes),1)

