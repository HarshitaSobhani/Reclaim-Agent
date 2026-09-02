"""FastAPI app serving the batch results through a small JSON API, plus the
static frontend. Reuses run_batch.run() directly - no logic duplicated here.

Run with: uvicorn webapp.main:app --reload
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from run_batch import run

OUT_DIR = "sample_output"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Reclaim")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    n: int = 80
    seed: int = 42


@app.get("/api/summary")
def get_summary():
    path = os.path.join(OUT_DIR, "summary.json")
    if not os.path.exists(path):
        raise HTTPException(404, "No batch has been run yet. POST /api/run first.")
    with open(path) as f:
        return json.load(f)


@app.get("/api/audit")
def get_audit():
    path = os.path.join(OUT_DIR, "audit_log.jsonl")
    if not os.path.exists(path):
        raise HTTPException(404, "No batch has been run yet. POST /api/run first.")
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


@app.post("/api/run")
def post_run(req: RunRequest):
    if not (1 <= req.n <= 500):
        raise HTTPException(400, "n must be between 1 and 500")
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = run(n=req.n, seed=req.seed, out_dir=OUT_DIR)
    return summary


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
