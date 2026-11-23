from contextlib import closing
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from quant import audit, fold_ranges, read_price_csv, regime, risk_summary, segment_result
from quant_report import render


def market():
    return [100+.04*i+5*math.sin(i*.45) for i in range(160)]


class QuantTests(unittest.TestCase):
    def test_report_escapes_custom_dataset_name(self):
        html = render(audit(market(),label='<script>alert(1)</script>'))
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('<svg',html)

    def test_fold_order_and_gap(self):
        ranges = fold_ranges(128,3,2)
        previous_end = 0
        for train_end,start,end in ranges:
            self.assertEqual(start-train_end,2)
            self.assertGreater(start,train_end)
            self.assertGreaterEqual(start,previous_end)
            previous_end = end
        self.assertEqual(previous_end,128)

    def test_future_changes_cannot_change_earlier_fold(self):
        prices = market()
        a = audit(prices)
        boundary = a['walk_forward'][0]['test_range'][1]
        changed = prices[:boundary]+[v*1.5 for v in prices[boundary:]]
        b = audit(changed)
        self.assertEqual(a['walk_forward'][0],b['walk_forward'][0])

    def test_holdout_cannot_change_development_diagnostics(self):
        prices = market()
        a = audit(prices)
        end = a['development_range'][1]
        b = audit(prices[:end]+[v*.8 for v in prices[end:]])
        for key in ('selected','walk_forward','cost_stress','parameter_neighbors','development_rankings'):
            self.assertEqual(a[key],b[key],key)

    def test_first_test_bar_fill_and_turnover(self):
        p = {'alpha':.3,'window':2,'hypothesis':'test'}
        r = segment_result(p,[10,20,30],1,3,0,0,100,buy_hold=True)
        self.assertEqual(r['trades'][0]['bar'],1)
        self.assertEqual(r['ending_equity'],150)
        self.assertEqual(r['equity'],[100,150])
        self.assertEqual(r['turnover'],2.5)

    def test_cost_sensitivity_is_real_recalculation(self):
        p = {'alpha':.7,'window':3,'hypothesis':'test'}
        r = audit(market(), candidates=[p])
        costs = r['cost_stress']
        self.assertGreater(costs[0]['trade_count'],0)
        self.assertGreater(costs[0]['net_return'],costs[-1]['net_return'])
        self.assertEqual([x['multiplier'] for x in costs],[1,2,4])

    def test_risk_metrics_known_equity(self):
        r = risk_summary([110,99,108.9],100)
        self.assertAlmostEqual(r['net_return'],.089)
        self.assertAlmostEqual(r['max_drawdown'],.1)
        self.assertAlmostEqual(r['historical_expected_shortfall_95_per_bar'],.1)

    def test_regime_is_descriptive(self):
        self.assertEqual(regime(list(range(100,140)))['trend'],'trending')
        self.assertEqual(regime([100,101]*20)['trend'],'ranging')

    def test_no_trade_evidence_flag(self):
        r = audit([100.0]*100)
        self.assertTrue(any('insufficient trade' in w for w in r['warnings']))
        self.assertTrue(any('no holdout trades' in w for w in r['warnings']))
        self.assertEqual(r['holdout']['net_return'],0)

    def test_invalid_inputs(self):
        for prices in ([1.]*20,[1.]*45+[float('nan')],[1.]*45+[0]):
            with self.assertRaises(ValueError):
                audit(prices)
        for kwargs in ({'fee':float('nan')},{'slip':-1},{'gap':20},{'splits':1}):
            with self.assertRaises(ValueError):
                audit(market(),**kwargs)

    def test_timestamped_csv_and_bad_order(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'prices.csv'
            rows = [f'{(datetime(2026,1,1)+timedelta(minutes=i)).isoformat()},{100+i}' for i in range(40)]
            p.write_text('timestamp,close\n'+'\n'.join(rows))
            self.assertEqual(len(read_price_csv(p)),40)
            p.write_text('timestamp,close\n'+'\n'.join(reversed(rows)))
            with self.assertRaises(ValueError):
                read_price_csv(p)

    def test_report_sqlite_and_strict_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'audit.db'
            r = audit(market(),db=path)
            json.dumps(r,allow_nan=False)
            with closing(sqlite3.connect(path)) as conn:
                saved = json.loads(conn.execute('SELECT report FROM quant_audits').fetchone()[0])
            self.assertEqual(saved,r)


if __name__ == '__main__':
    unittest.main()
