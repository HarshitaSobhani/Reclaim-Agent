"""LLM-powered intervention choice + message drafting, via Groq's free-tier API.

The model is given the deterministic diagnosis (from diagnose.py) plus case
context, and asked to return STRICT JSON: {intervention, message, rationale}.
`intervention` MUST be one of policy.ALLOWED_INTERVENTIONS - the response is
validated and any invalid/malformed output is coerced to a safe fallback
(NO_ACTION + escalation note), never executed blind.

If GROQ_API_KEY is not set, falls back to a deterministic rule-based chooser
(rule_based_decide) so the whole pipeline still runs end-to-end for demos
without an API key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from agent.diagnose import Diagnosis
from agent.policy import ALLOWED_INTERVENTIONS, Intervention
from mock_razorpay.models import Case

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are a revenue-recovery decision assistant for an Indian \
payments merchant using Razorpay. You are given ONE case with its deterministic \
root-cause diagnosis. Your job:

1. Choose exactly ONE intervention from this fixed list (copy the string exactly):
   instant_retry, retry_with_delay, request_new_payment_method, send_checkout_nudge,
   send_mandate_retry_link, send_receivable_reminder, escalate_to_human, no_action

2. Draft a short customer-facing recovery message (<=280 chars) appropriate to the \
intervention, in Hinglish if the customer prefers it, else plain English. Be polite, \
never pushy, never mention internal error codes to the customer.

3. Give a one-sentence rationale for a human auditor.

Respond with ONLY valid JSON, no markdown fences, no extra text:
{"intervention": "...", "message": "...", "rationale": "..."}

Rules: if the case is not actionable, you MUST choose "no_action". Never invent an \
intervention outside the fixed list."""


@dataclass
class Decision:
    intervention: str
    message: str
    rationale: str
    source: str  # "groq" | "rule_based_fallback" | "invalid_output_fallback"


def _build_user_prompt(case: Case, diagnosis: Diagnosis) -> str:
    return json.dumps(
        {
            "case_id": case.id,
            "category": case.category.value,
            "amount_inr": case.amount_inr,
            "method": case.method,
            "customer_name": case.customer.name,
            "prefers_hinglish": case.customer.prefers_hinglish,
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "confidence": diagnosis.confidence,
                "is_actionable": diagnosis.is_actionable,
                "rationale": diagnosis.rationale,
            },
        }
    )


def rule_based_decide(case: Case, diagnosis: Diagnosis) -> Decision:
    """Deterministic fallback used when no GROQ_API_KEY is configured."""
    if not diagnosis.is_actionable:
        return Decision(Intervention.NO_ACTION.value, "", diagnosis.rationale, "rule_based_fallback")

    cause_to_action = {
        "gateway_timeout": Intervention.INSTANT_RETRY,
        "insufficient_funds": Intervention.RETRY_WITH_DELAY,
        "card_expired": Intervention.REQUEST_NEW_PAYMENT_METHOD,
        "issuer_declined": Intervention.REQUEST_NEW_PAYMENT_METHOD,
        "otp_failed": Intervention.RETRY_WITH_DELAY,
        "checkout_abandoned": Intervention.SEND_CHECKOUT_NUDGE,
        "invoice_overdue": Intervention.SEND_RECEIVABLE_REMINDER,
        "mandate_not_approved": Intervention.SEND_MANDATE_RETRY_LINK,
    }
    action = cause_to_action.get(diagnosis.root_cause, Intervention.ESCALATE_TO_HUMAN)

    templates = {
        Intervention.INSTANT_RETRY: "",
        Intervention.RETRY_WITH_DELAY: f"Hi {case.customer.name}, your payment of ₹{case.amount_inr:.0f} didn't go through. We'll retry shortly, or you can pay now via a fresh link.",
        Intervention.REQUEST_NEW_PAYMENT_METHOD: f"Hi {case.customer.name}, your payment of ₹{case.amount_inr:.0f} needs an updated payment method. Please update it to complete your order.",
        Intervention.SEND_CHECKOUT_NUDGE: f"Hi {case.customer.name}, you left something in your cart worth ₹{case.amount_inr:.0f}. Complete your purchase before it's gone!",
        Intervention.SEND_MANDATE_RETRY_LINK: f"Hi {case.customer.name}, your autopay mandate for ₹{case.amount_inr:.0f} needs re-approval. Tap here to re-authorize.",
        Intervention.SEND_RECEIVABLE_REMINDER: f"Dear {case.customer.name}, invoice for ₹{case.amount_inr:.0f} is overdue. Please arrange payment at your earliest convenience.",
        Intervention.ESCALATE_TO_HUMAN: "",
    }
    return Decision(
        action.value,
        templates.get(action, ""),
        f"rule-based mapping: {diagnosis.root_cause} -> {action.value}",
        "rule_based_fallback",
    )


def decide(case: Case, diagnosis: Diagnosis) -> Decision:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return rule_based_decide(case, diagnosis)

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=600,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(case, diagnosis)},
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        intervention = parsed.get("intervention", "")
        if intervention not in ALLOWED_INTERVENTIONS:
            raise ValueError(f"invalid intervention '{intervention}'")
        return Decision(
            intervention=intervention,
            message=parsed.get("message", ""),
            rationale=parsed.get("rationale", ""),
            source="groq",
        )
    except Exception as exc:  # noqa: BLE001 - any LLM/parse failure falls back safely
        fallback = rule_based_decide(case, diagnosis)
        fallback.rationale = f"[groq call failed: {exc}] {fallback.rationale}"
        fallback.source = "invalid_output_fallback"
        return fallback
