"""Portable, script-free HTML evidence card for a completed quant audit."""
from html import escape


def pct(value):
    return f"{100*value:.2f}%" if value is not None else "No observations"


def curve(primary, baseline):
    series = [primary,baseline]
    low, high = min(min(s) for s in series),max(max(s) for s in series)
    spread = high-low or max(1,high*.01)
    paths = []
    for values,color in zip(series,['#59ddc6','#d79bf5']):
        points = ' '.join(f'{25+650*i/max(1,len(values)-1):.1f},{200-160*(v-low)/spread:.1f}'
                          for i,v in enumerate(values))
        paths.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
    return ('<svg viewBox="0 0 700 230" role="img" aria-label="Holdout equity curves">'
            '<path d="M25 20V205H680" fill="none" stroke="#52637a"/>'
            + ''.join(paths)+f'<text x="30" y="225" fill="#a9bbd1">Start</text>'
            '<text x="635" y="225" fill="#a9bbd1">End</text></svg>'
            f'<p class="muted">Scale: {low:,.2f} to {high:,.2f}; initial capital 10,000. '
            'Green: selected strategy. Purple: buy-and-hold.</p>')


def render(report):
    warnings = ''.join('<li>'+escape(w)+'</li>' for w in report['warnings'])
    costs = ''.join(f'<tr><td>{r["multiplier"]}x</td><td>{r["fee_bps"]:g}</td>'
                    f'<td>{r["slippage_bps"]:g}</td><td>{pct(r["net_return"])}</td></tr>'
                    for r in report['cost_stress'])
    folds = ''.join(f'<tr><td>{i+1}</td><td>{r["train_range"]}</td><td>{r["test_range"]}</td>'
                    f'<td>{escape(r["regime_from_training"]["trend"])}</td>'
                    f'<td>{pct(r["test"]["net_return"])}</td><td>{r["test"]["trade_count"]}</td></tr>'
                    for i,r in enumerate(report['walk_forward']))
    neighbors = ''.join(f'<tr><td>{r["alpha"]:.3f}</td><td>{r["window"]}</td>'
                        f'<td>{pct(r["net_return"])}</td><td>{pct(r["max_drawdown"])}</td></tr>'
                        for r in report['parameter_neighbors'])
    notes = ''.join('<li>'+escape(n)+'</li>' for n in report['method_notes'])
    p = report['selected']
    return f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlphaLabLite - Quant research audit</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#0a1526;color:#e7eff9;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1050px;margin:auto;padding:40px 22px}}h1{{font-size:38px;line-height:1.2}}h2{{font-size:22px}}
.eyebrow{{color:#59ddc6;letter-spacing:.15em;font-size:12px}}.muted{{color:#a9bbd1;font-size:14px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}}
.card,section{{background:#112139;border:1px solid #293c56;border-radius:16px;padding:22px;margin:18px 0}}
.card strong{{display:block;font-size:29px;color:#59ddc6}}.alert{{border-left:4px solid #f4c77b}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px 7px;text-align:left;border-bottom:1px solid #293c56}}
.scroll{{overflow-x:auto}}svg{{width:100%;max-height:330px}}code{{word-break:break-word}}a{{color:#59ddc6}}
@media print{{body{{background:white;color:#14253b}}section,.card{{background:white;border-color:#ddd}}.muted{{color:#41566d}}}}
</style><main><div class="eyebrow">ALPHALABLITE / QUANT RESEARCH AUDIT</div>
<h1>Challenge the strategy.<br>Keep the evidence.</h1>
<p>{escape(report['dataset'])} | {report['bars']} observations | EMA alpha {p['alpha']:g}, SMA {p['window']}</p>
<div class="cards"><div class="card">Walk-forward return<strong>{pct(report['walk_forward_risk']['net_return'])}</strong></div>
<div class="card">Walk-forward drawdown<strong>{pct(report['walk_forward_risk']['max_drawdown'])}</strong></div>
<div class="card">Holdout fills<strong>{report['holdout']['trade_count']}</strong></div></div>
<section class="alert"><h2>Evidence review</h2><p>{escape(report['research_note'])}</p><ul>{warnings}</ul></section>
<section><h2>Final holdout: strategy versus baseline</h2>
<p>Strategy {pct(report['holdout']['net_return'])}; buy-and-hold {pct(report['holdout_baseline']['net_return'])}.</p>
{curve(report['holdout']['equity'],report['holdout_baseline']['equity'])}</section>
<section><h2>Walk-forward and past-only regime labels</h2><div class="scroll"><table>
<tr><th>Fold</th><th>Train bars</th><th>Test bars</th><th>Regime</th><th>Net return</th><th>Fills</th></tr>{folds}</table></div>
<p class="muted">Ranges use inclusive starts and exclusive ends. Fold positions reset; results compound across folds.</p></section>
<section><h2>What if trading costs rise?</h2><table><tr><th>Scenario</th><th>Fee bps</th><th>Slip bps</th><th>Net return</th></tr>{costs}</table>
<p class="muted">Fixed strategy recalculated on development history only.</p></section>
<section><h2>Does a small parameter change break the result?</h2><table><tr><th>EMA alpha</th><th>SMA window</th><th>Net return</th><th>Drawdown</th></tr>{neighbors}</table>
<p class="muted">Four local perturbations on development history; no automatic retuning on the holdout.</p></section>
<section><h2>Method and provenance</h2><ul>{notes}</ul>
<p class="muted">Run <code>{escape(report['run_id'])}</code><br>Data SHA-256 <code>{escape(report['data_sha256'])}</code></p></section>
<p class="muted">Historical research tool. No brokerage execution or real-time market connection.</p></main></html>'''
