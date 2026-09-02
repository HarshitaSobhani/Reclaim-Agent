"""Deterministic root-cause classification. This runs before the LLM call and
gives the LLM structured signal rather than raw fields - the LLM picks the
intervention and drafts the message, it does not guess the root cause from
scratch each time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mock_razorpay.models import Case, CaseCategory, RAZORPAY_ERROR_CODES
from agent.policy import ABANDONED_CHECKOUT_GRACE_MINUTES


@dataclass
class Diagnosis:
    root_cause: str
    confidence: str  # "high" | "medium" | "low"
    is_actionable: bool
    rationale: str


def diagnose(case: Case, now: datetime) -> Diagnosis:
    if case.category == CaseCategory.FAILED_PAYMENT:
        cause = RAZORPAY_ERROR_CODES.get(case.error_code or "", "unknown_gateway_error")
        return Diagnosis(
            root_cause=cause,
            confidence="high" if case.error_code in RAZORPAY_ERROR_CODES else "low",
            is_actionable=True,
            rationale=f"Razorpay error_code={case.error_code} maps to '{cause}'",
        )

    if case.category == CaseCategory.ABANDONED_CHECKOUT:
        opened_at = case.checkout_opened_at or case.created_at
        idle_minutes = (now - opened_at).total_seconds() / 60
        if idle_minutes < ABANDONED_CHECKOUT_GRACE_MINUTES:
            return Diagnosis(
                root_cause="checkout_in_progress",
                confidence="high",
                is_actionable=False,
                rationale=f"only {idle_minutes:.0f}m idle - still within normal checkout time, not at risk",
            )
        return Diagnosis(
            root_cause="checkout_abandoned",
            confidence="high",
            is_actionable=True,
            rationale=f"checkout idle for {idle_minutes:.0f}m with no payment captured",
        )

    if case.category == CaseCategory.OVERDUE_RECEIVABLE:
        days_overdue = (now - (case.invoice_due_at or now)).days
        return Diagnosis(
            root_cause="invoice_overdue",
            confidence="high",
            is_actionable=days_overdue > 0,
            rationale=f"invoice {days_overdue} day(s) past due date",
        )

    if case.category == CaseCategory.FAILED_MANDATE:
        cause = RAZORPAY_ERROR_CODES.get(case.error_code or "", "mandate_failure")
        return Diagnosis(
            root_cause=cause,
            confidence="high" if case.error_code in RAZORPAY_ERROR_CODES else "medium",
            is_actionable=True,
            rationale=f"eMandate/UPI Autopay error_code={case.error_code} maps to '{cause}'",
        )

    return Diagnosis("unknown", "low", False, "unrecognized case category")
