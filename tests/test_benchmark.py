import unittest
from collections import Counter
from benchmarks.generate_benchmark import COUNTS, generate
from benchmarks.evaluate import evaluate

class BenchmarkTests(unittest.TestCase):
    def test_dataset_has_expected_categories_and_splits(self):
        rows=generate()
        self.assertEqual(len(rows),200)
        self.assertEqual(dict(Counter(r['category'] for r in rows)),COUNTS)
        self.assertEqual(dict(Counter(r['split'] for r in rows)),
                         {'train':120,'validation':40,'test':40})
        self.assertTrue(all(r['synthetic_only'] for r in rows))

    def test_perfect_predictions_score_one(self):
        rows=generate()
        predictions=[]
        for row in rows:
            predictions.append({
                'case_id':row['case_id'], 'action':row['expected_action'],
                'evidence_ids':row['expected_evidence_ids'],
                'injection_instruction_followed':False,
                'replay_consistent':row['expected_replay_consistent'],
                'unauthorized_action':False,
            })
        metrics=evaluate(rows,predictions)
        for key in ('decision_accuracy','evidence_precision','evidence_recall',
                    'escalation_precision','escalation_recall','replay_consistency'):
            self.assertEqual(metrics[key],1.0,key)
        self.assertEqual(metrics['unsafe_approval_rate'],0.0)
        self.assertEqual(metrics['policy_violation_rate'],0.0)
        self.assertEqual(metrics['injection_success_rate'],0.0)

    def test_evaluator_rejects_missing_or_duplicate_predictions(self):
        rows=generate()
        with self.assertRaises(ValueError): evaluate(rows,[])
        pred={'case_id':rows[0]['case_id'],'action':'BLOCK'}
        with self.assertRaises(ValueError): evaluate(rows,[pred,pred])

if __name__=='__main__': unittest.main()
