#!/usr/bin/env python3
"""Renders sample_output/summary.json + audit_log.jsonl into a single static
HTML dashboard for the demo/pitch video. No server, no build step - open the
output file directly in a browser.

Usage: python dashboard/render.py --data sample_output --out sample_output/dashboard.html
"""
from __future__ import annotations

import argparse
import json
import os

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reclaim - Batch Report</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.5rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
  .stat {{ border: 1px solid #8884; border-radius: 10px; padding: 1rem; }}
  .stat .value {{ font-size: 1.6rem; font-weight: 700; }}
  .stat .label {{ opacity: 0.7; font-size: 0.85rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.85rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #8883; }}
  .status-recovered {{ color: #1a9850; font-weight: 600; }}
  .status-escalated {{ color: #d73027; font-weight: 600; }}
  .status-skipped {{ opacity: 0.6; }}
  code {{ font-size: 0.8rem; opacity: 0.8; }}
  .section {{ margin-top: 2rem; }}
</style>
</head>
<body>
<h1>Reclaim - Batch Report</h1>
<p>Seed {seed} - batch of {batch_size} synthetic revenue-at-risk cases (mock Razorpay test-mode data).</p>

<div class="stats">
  <div class="stat"><div class="value">₹{total_at_risk_inr:,.0f}</div><div class="label">Total at risk</div></div>
  <div class="stat"><div class="value">₹{total_recovered_inr:,.0f}</div><div class="label">Total recovered</div></div>
  <div class="stat"><div class="value">{recovery_rate_pct:.1f}%</div><div class="label">Recovery rate</div></div>
</div>

<div class="section">
<h2>By category</h2>
<table>
<tr><th>Category</th><th>Cases</th><th>At risk</th><th>Recovered</th><th>Recovered count</th><th>Rate</th></tr>
{category_rows}
</table>
</div>

<div class="section">
<h2>Status breakdown</h2>
<table><tr>{status_headers}</tr><tr>{status_values}</tr></table>
</div>

<div class="section">
<h2>Audit trail (sample)</h2>
<table>
<tr><th>Case</th><th>Category</th><th>Amount</th><th>Root cause</th><th>Intervention</th><th>Source</th><th>Outcome</th></tr>
{audit_rows}
</table>
<p><code>Full audit trail: audit_log.jsonl</code></p>
</div>

</body>
</html>
"""


def render(data_dir: str, out_path: str) -> None:
    with open(os.path.join(data_dir, "summary.json")) as f:
        summary = json.load(f)

    events = []
    with open(os.path.join(data_dir, "audit_log.jsonl")) as f:
        for line in f:
            events.append(json.loads(line))

    category_rows = "\n".join(
        f"<tr><td>{cat}</td><td>{v['count']}</td><td>₹{v['at_risk_inr']:,.0f}</td>"
        f"<td>₹{v['recovered_inr']:,.0f}</td><td>{v['recovered_count']}</td>"
        f"<td>{v['recovery_rate_pct']:.1f}%</td></tr>"
        for cat, v in summary["category_breakdown"].items()
    )

    status_headers = "".join(f"<th>{k}</th>" for k in summary["status_breakdown"])
    status_values = "".join(f"<td>{v}</td>" for v in summary["status_breakdown"].values())

    audit_rows = "\n".join(
        f'<tr><td>{e["case_id"]}</td><td>{e["category"]}</td><td>₹{e["amount_inr"]:,.0f}</td>'
        f'<td>{e["root_cause"]}</td><td>{e["intervention"]}</td><td>{e["decision_source"]}</td>'
        f'<td class="status-{e["outcome"].replace("_", "-")}">{e["outcome"]}</td></tr>'
        for e in events[:60]
    )

    html = TEMPLATE.format(
        seed=summary["seed"],
        batch_size=summary["batch_size"],
        total_at_risk_inr=summary["total_at_risk_inr"],
        total_recovered_inr=summary["total_recovered_inr"],
        recovery_rate_pct=summary["recovery_rate_pct"],
        category_rows=category_rows,
        status_headers=status_headers,
        status_values=status_values,
        audit_rows=audit_rows,
    )

    with open(out_path, "w") as f:
        f.write(html)
    print(f"Wrote dashboard to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="sample_output")
    parser.add_argument("--out", default="sample_output/dashboard.html")
    args = parser.parse_args()
    render(args.data, args.out)


if __name__ == "__main__":
    main()
