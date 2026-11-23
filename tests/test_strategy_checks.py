import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research import run, script_for
from strategy_checks import analyze, check_strategy, similarity

P = {"alpha":.3,"window":20,"hypothesis":"Test crossover"}

class StrategyChecksTests(unittest.TestCase):
    def test_metrics_and_stable_fingerprint(self):
        script = script_for(P)
        first = analyze(script)
        renamed = script.replace("fast","quick").replace("slow","longer")
        self.assertEqual(first["fingerprint"],analyze(renamed)["fingerprint"])
        self.assertEqual(first["commands"],4)
        self.assertEqual(first["depth"],3)
        self.assertEqual(first["nodes"],10)

    def test_renamed_duplicate_rejected(self):
        s = script_for(P)
        with self.assertRaisesRegex(ValueError,"similar"):
            check_strategy(s.replace("fast","renamed"),[s])

    def test_tiny_parameter_change_rejected(self):
        with self.assertRaisesRegex(ValueError,"similar"):
            check_strategy(script_for(dict(P,alpha=.300001)),[script_for(P)])

    def test_distinct_parameters_accepted(self):
        result = check_strategy(script_for(dict(P,alpha=.7,window=5)),[script_for(P)])
        self.assertLess(result["max_similarity"],.995)

    def test_deep_expression_rejected(self):
        lines = ["x0 = SimpleMovingAverage{2}{price}"]
        lines += [f"x{i} = SimpleMovingAverage{{2}}{{x{i-1}}}" for i in range(1,8)]
        lines += ["entry = CrossAbove{}{x7, price}","exit = CrossAbove{}{price, x7}"]
        with self.assertRaisesRegex(ValueError,"complexity"):
            analyze("\n".join(lines))

    def test_expanded_node_budget(self):
        with self.assertRaisesRegex(ValueError,"node"):
            analyze(script_for(P),max_nodes=9)

    def test_unsafe_or_invalid_dsl(self):
        examples = [
            "entry = Fetch{anything}{}\nexit = Fetch{anything}{}",
            "x = SimpleMovingAverage{2}{unknown}",
            "price = SimpleMovingAverage{2}{price}",
            "entry = SimpleMovingAverage{nan}{price}",
            "entry = SimpleMovingAverage{0}{price}",
        ]
        for s in examples:
            with self.subTest(script=s),self.assertRaises(ValueError):
                analyze(s)

    def test_retry_receives_rejection_feedback(self):
        # Model first proposes an invalid window, then repairs it.
        proposals = [dict(P,window=100),P]
        observed = []
        def fake(mode,feedback,attempt,goal,errors):
            observed.append(list(errors))
            return proposals.pop(0)
        with tempfile.TemporaryDirectory() as d, patch("research.propose",side_effect=fake):
            r = run(rounds=1,db=str(Path(d)/"run.db"))
        self.assertEqual(len(r["proposal_failures"]),1)
        self.assertIn("error",observed[1][0])
        self.assertIn("strategy_checks",r["experiments"][0])

    def test_holdout_not_sent_to_proposer(self):
        seen = []
        def fake(mode,feedback,attempt,goal,errors):
            seen.append(json.loads(json.dumps(feedback)))
            return dict(P,alpha=.3+len(feedback)*.2)
        with tempfile.TemporaryDirectory() as d, patch("research.propose",side_effect=fake):
            r = run(rounds=2,db=str(Path(d)/"run.db"))
        self.assertEqual(seen[0],[])
        self.assertEqual(set(seen[1][0]),{"iteration","proposal","validation","script","strategy_checks"})
        self.assertNotIn("test",seen[1][0])
