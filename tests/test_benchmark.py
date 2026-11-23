import json
import unittest

from benchmark import benchmark, random_candidates, synthetic_prices


class BenchmarkTests(unittest.TestCase):
    def test_deterministic_data_and_candidates(self):
        self.assertEqual(synthetic_prices("trend",11),synthetic_prices("trend",11))
        self.assertEqual(random_candidates(11),random_candidates(11))
        self.assertNotEqual(synthetic_prices("trend",11),synthetic_prices("trend",23))

    def test_invalid_scenario(self):
        with self.assertRaises(ValueError):
            synthetic_prices("unrecognized",11)

    def test_protocol_and_strict_json(self):
        result = benchmark(seeds=(11,),n=200)
        self.assertEqual(result["case_count"],4)
        self.assertEqual(result["candidate_budget"],{"preset_search":6,"equal_budget_random_search":6})
        self.assertIn("synthetic",result["scenario_type"])
        json.dumps(result,allow_nan=False)

    def test_each_case_has_all_baselines(self):
        result = benchmark(seeds=(11,),n=200)
        for row in result["rows"]:
            self.assertEqual(set(row["strategies"]),{
                "preset_search","equal_budget_random_search","fixed_ema_sma","buy_and_hold","cash"})
            self.assertEqual(row["holdout_range"],[160,200])



if __name__ == "__main__":
    unittest.main()
