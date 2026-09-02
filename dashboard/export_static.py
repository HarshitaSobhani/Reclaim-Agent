#!/usr/bin/env python3
"""Exports the interactive webapp/ dashboard as a fully static site - no
FastAPI backend needed. Reads the batch results from an output dir (same
files run_batch.py writes) and bakes them into summary.json/audit.json
sitting next to a copy of the dashboard's HTML/CSS/JS.

Used for hosting on platforms that only serve static files for free
(e.g. Hugging Face Static Spaces, GitHub Pages) - the "run new batch"
control is hidden in this mode since there's no server to run it on;
run `run_batch.py` locally and re-export to update the published data.

Usage: python dashboard/export_static.py --data sample_output --out static_site
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

WEBAPP_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "webapp", "static")


def export(data_dir: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # Copy the dashboard's HTML/CSS/JS as-is.
    for fname in ("styles.css", "app.js"):
        shutil.copy(os.path.join(WEBAPP_STATIC_DIR, fname), os.path.join(out_dir, fname))

    # index.html needs one line added: set window.RECLAIM_STATIC = true
    # before app.js loads, so it reads the local JSON files below instead
    # of hitting a live /api/* backend.
    with open(os.path.join(WEBAPP_STATIC_DIR, "index.html")) as f:
        html = f.read()
    html = html.replace(
        '<script src="app.js"></script>',
        '<script>window.RECLAIM_STATIC = true;</script>\n  <script src="app.js"></script>',
    )
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)

    # Bake the batch results into static JSON files.
    with open(os.path.join(data_dir, "summary.json")) as f:
        summary = json.load(f)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f)

    events = []
    with open(os.path.join(data_dir, "audit_log.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    with open(os.path.join(out_dir, "audit.json"), "w") as f:
        json.dump(events, f)

    print(f"Exported static site to {out_dir}/ ({len(events)} audit events)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="sample_output")
    parser.add_argument("--out", default="static_site")
    args = parser.parse_args()
    export(args.data, args.out)


if __name__ == "__main__":
    main()
