#!/usr/bin/env python3
"""CLI entrypoint: generate a batch -> diagnose -> decide -> gate -> execute
-> summarize. Produces audit_log.jsonl and a printed/JSON summary.

Usage:
    python run_batch.py --seed 42 --n 80 --out sample_output
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta

from agent.llm_client import decide
from agent.diagnose import diagnose
from agent.executor import AuditEvent, AuditLog, CaseState, CaseStatus, simulate_outcome
from agent.policy import COOLDOWN_HOURS, MAX_ATTEMPTS, check_stopping_rules
from mock_razorpay.generator import generate_batch


def run(n: int, seed: int, out_dir: str) -> dict:
    rng = random.Random(seed)
    cases = generate_batch(n=n, seed=seed)
    audit = AuditLog(path=f"{out_dir}/audit_log.jsonl")

    states: dict[str, CaseState] = {c.id: CaseState(case_id=c.id) for c in cases}
    total_at_risk_paise = 0
    total_recovered_paise = 0
    category_totals: dict[str, dict] = {}

    for case in cases:
        state = states[case.id]
        total_at_risk_paise += case.amount_paise
        cat = category_totals.setdefault(
            case.category.value, {"count": 0, "at_risk_inr": 0.0, "recovered_inr": 0.0, "recovered_count": 0}
        )
        cat["count"] += 1
        cat["at_risk_inr"] += case.amount_inr

        sim_now = case.created_at
        last_attempt_at: datetime | None = None
        max_attempts = MAX_ATTEMPTS.get(case.category.value, 3)

        while state.attempts < max_attempts and state.status in (CaseStatus.OPEN, CaseStatus.ATTEMPTED):
            diagnosis = diagnose(case, sim_now)
            hours_since_last = (
                (sim_now - last_attempt_at).total_seconds() / 3600 if last_attempt_at else None
            )

            if not diagnosis.is_actionable:
                audit.record(
                    AuditEvent(
                        timestamp=sim_now.isoformat(),
                        case_id=case.id,
                        category=case.category.value,
                        amount_inr=case.amount_inr,
                        attempt_number=state.attempts,
                        root_cause=diagnosis.root_cause,
                        diagnosis_confidence=diagnosis.confidence,
                        intervention="no_action",
                        decision_source="diagnosis",
                        rationale=diagnosis.rationale,
                        message_sent="",
                        gate_allowed=True,
                        gate_reason="not actionable",
                        outcome="not_attempted",
                        status_after=CaseStatus.SKIPPED.value,
                    )
                )
                state.status = CaseStatus.SKIPPED
                break

            decision = decide(case, diagnosis)
            gate = check_stopping_rules(
                category=case.category.value,
                amount_paise=case.amount_paise,
                attempts_so_far=state.attempts,
                hours_since_last_attempt=hours_since_last,
                proposed_intervention=decision.intervention,
                do_not_contact=case.customer.do_not_contact,
            )

            if not gate.allowed:
                status_after = (
                    CaseStatus.ESCALATED
                    if "max attempts" in gate.reason
                    else CaseStatus.SKIPPED
                )
                audit.record(
                    AuditEvent(
                        timestamp=sim_now.isoformat(),
                        case_id=case.id,
                        category=case.category.value,
                        amount_inr=case.amount_inr,
                        attempt_number=state.attempts,
                        root_cause=diagnosis.root_cause,
                        diagnosis_confidence=diagnosis.confidence,
                        intervention=decision.intervention,
                        decision_source=decision.source,
                        rationale=f"BLOCKED by policy gate: {gate.reason}",
                        message_sent="",
                        gate_allowed=False,
                        gate_reason=gate.reason,
                        outcome="not_attempted",
                        status_after=status_after.value,
                    )
                )
                state.status = status_after
                break

            state.attempts += 1
            last_attempt_at = sim_now
            recovered = simulate_outcome(rng, decision.intervention)
            outcome = "recovered" if recovered else "failed"
            status_after = CaseStatus.RECOVERED if recovered else CaseStatus.ATTEMPTED

            audit.record(
                AuditEvent(
                    timestamp=sim_now.isoformat(),
                    case_id=case.id,
                    category=case.category.value,
                    amount_inr=case.amount_inr,
                    attempt_number=state.attempts,
                    root_cause=diagnosis.root_cause,
                    diagnosis_confidence=diagnosis.confidence,
                    intervention=decision.intervention,
                    decision_source=decision.source,
                    rationale=decision.rationale,
                    message_sent=decision.message,
                    gate_allowed=True,
                    gate_reason="ok",
                    outcome=outcome,
                    status_after=status_after.value,
                )
            )

            if recovered:
                state.status = CaseStatus.RECOVERED
                state.recovered_amount_paise = case.amount_paise
                total_recovered_paise += case.amount_paise
                cat["recovered_inr"] += case.amount_inr
                cat["recovered_count"] += 1
                break

            state.status = CaseStatus.ATTEMPTED
            cooldown = COOLDOWN_HOURS.get(decision.intervention, 6)
            sim_now = sim_now + timedelta(hours=max(cooldown, 1))

        if state.status == CaseStatus.ATTEMPTED and state.attempts >= max_attempts:
            state.status = CaseStatus.ESCALATED

    audit.write()

    status_counts: dict[str, int] = {}
    for s in states.values():
        status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1

    summary = {
        "batch_size": n,
        "seed": seed,
        "total_at_risk_inr": round(total_at_risk_paise / 100, 2),
        "total_recovered_inr": round(total_recovered_paise / 100, 2),
        "recovery_rate_pct": round(100 * total_recovered_paise / total_at_risk_paise, 2)
        if total_at_risk_paise
        else 0,
        "status_breakdown": status_counts,
        "category_breakdown": {
            k: {
                "count": v["count"],
                "at_risk_inr": round(v["at_risk_inr"], 2),
                "recovered_inr": round(v["recovered_inr"], 2),
                "recovered_count": v["recovered_count"],
                "recovery_rate_pct": round(100 * v["recovered_inr"] / v["at_risk_inr"], 2)
                if v["at_risk_inr"]
                else 0,
            }
            for k, v in category_totals.items()
        },
    }

    with open(f"{out_dir}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the revenue recovery agent over a synthetic batch.")
    parser.add_argument("--n", type=int, default=80, help="batch size")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    parser.add_argument("--out", type=str, default="sample_output", help="output directory")
    args = parser.parse_args()

    import os

    os.makedirs(args.out, exist_ok=True)
    summary = run(n=args.n, seed=args.seed, out_dir=args.out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
