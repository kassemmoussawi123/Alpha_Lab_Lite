import math
from contextlib import closing
from unittest.mock import patch, MagicMock
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from engine import executeScript
from research import run,simulate,validate_proposal,evaluate,propose

class ResearchTests(unittest.TestCase):
    def test_numerical_sma(self):
        result = executeScript("s = SimpleMovingAverage{2}{price}",{"price":[1,3,5]})["s"]
        self.assertTrue(math.isnan(result[0]))
        self.assertEqual(result[1:],[2,4])

    def test_invalid_commands(self):
        for script in ["x = SimpleMovingAverage{}{price}",
                       "x = ExponentialMovingAverage{2}{price}",
                       "x = SimpleMovingAverage{0}{price}",
                       "x = Unknown{}{price}"]:
            with self.subTest(script=script), self.assertRaises(ValueError):
                executeScript(script,{"price":[1,2,3]})

    def test_no_same_bar_fill(self):
        r = simulate([10,20,30],[1,0,0],[0,0,0],0,0,100)
        self.assertEqual(r["trades"][0]["bar"],1)
        self.assertEqual(r["trades"][0]["units"],5)
        self.assertEqual(r["ending_equity"],150)

    def test_fees_charged_both_sides(self):
        r = simulate([10,10,10],[1,0,0],[0,0,0],100,0,100)
        self.assertAlmostEqual(r["ending_equity"],100*.99/1.01)

    def test_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            simulate([1,2],[1],[0,0])

    def test_proposal_restrictions(self):
        for p in [{"alpha":True,"window":10,"hypothesis":"x"},
                  {"alpha":.2,"window":10,"hypothesis":"x","code":"anything"},
                  {"alpha":.2,"window":0,"hypothesis":"x"}]:
            with self.assertRaises(ValueError):
                validate_proposal(p)

    def test_future_prices_do_not_change_past_equity(self):
        p = {"alpha":.5,"window":2,"hypothesis":"x"}
        a = evaluate(p,[10,9,12,13,12,14,15,13],10,5)
        b = evaluate(p,[10,9,12,13,12,99,1,50],10,5)
        self.assertEqual(a["equity"][:5],b["equity"][:5])

    def test_llm_adapter_with_mock_response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "choices":[{"message":{"content":json.dumps({
                "alpha":.3,"window":20,"hypothesis":"Test a crossover"})}}]}).encode()
        with patch.dict(os.environ,{"ALPHALAB_API_KEY":"test","ALPHALAB_MODEL":"test-model"}), patch("urllib.request.urlopen",return_value=response):
            self.assertEqual(propose("llm",[])["window"],20)

    def test_llm_missing_credentials(self):
        with patch.dict(os.environ,{},clear=True), self.assertRaises(ValueError):
            propose("llm",[])

    def test_reproducibility_and_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d)/"runs.db")
            a,b = run(db=db),run(db=db)
            self.assertEqual(a["selected"],b["selected"])
            self.assertEqual(a["test"],b["test"])
            self.assertEqual(len(a["experiments"]),3)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM research_runs").fetchone()[0],2)
            self.assertIn("code_sha256",a)

if __name__ == "__main__":
    unittest.main()
