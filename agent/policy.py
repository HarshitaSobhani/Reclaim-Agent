"""The bounded action space and stopping rules. Nothing in this file or in
llm_client.py is allowed to take an action outside `Intervention` -
the LLM's output is parsed against this enum and rejected if it doesn't match.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Intervention(str, Enum):
    INSTANT_RETRY = "instant_retry"  # gateway blip: retry immediately, no customer contact
    RETRY_WITH_DELAY = "retry_with_delay"  # insufficient funds: retry after a cooldown
    REQUEST_NEW_PAYMENT_METHOD = "request_new_payment_method"  # card expired/declined
    SEND_CHECKOUT_NUDGE = "send_checkout_nudge"  # abandoned checkout, high-value / long-idle only
    SEND_MANDATE_RETRY_LINK = "send_mandate_retry_link"  # failed UPI Autopay/eNACH mandate
    SEND_RECEIVABLE_REMINDER = "send_receivable_reminder"  # overdue B2B invoice
    ESCALATE_TO_HUMAN = "escalate_to_human"  # exhausted attempts / high-value / repeated failure
    NO_ACTION = "no_action"  # below threshold or too recent to act on

ALLOWED_INTERVENTIONS = {i.value for i in Intervention}

# Max automated attempts before a case is force-escalated, per category.
MAX_ATTEMPTS = {
    "failed_payment": 3,
    "abandoned_checkout": 2,
    "overdue_receivable": 4,
    "failed_mandate": 3,
}

# Minimum cooldown (hours) enforced between consecutive attempts on the same case.
COOLDOWN_HOURS = {
    "instant_retry": 0,
    "retry_with_delay": 6,
    "request_new_payment_method": 12,
    "send_checkout_nudge": 24,
    "send_mandate_retry_link": 24,
    "send_receivable_reminder": 72,
}

# Below this amount, we don't bother auto-recovering (cost of intervention > value).
MIN_AMOUNT_PAISE_TO_ACT = 20000  # ₹200

# Abandoned checkouts younger than this are still "in progress", not at risk.
ABANDONED_CHECKOUT_GRACE_MINUTES = 3


@dataclass
class StoppingDecision:
    allowed: bool
    reason: str


def check_stopping_rules(
    category: str,
    amount_paise: int,
    attempts_so_far: int,
    hours_since_last_attempt: float | None,
    proposed_intervention: str,
    do_not_contact: bool,
) -> StoppingDecision:
    """Deterministic guardrail applied AFTER the diagnosis/LLM choice, before
    execution. This is what makes the agent "bounded and gated": the LLM
    proposes, this function disposes.
    """
    if proposed_intervention not in ALLOWED_INTERVENTIONS:
        return StoppingDecision(False, f"unknown intervention '{proposed_intervention}' rejected")

    if do_not_contact and proposed_intervention != Intervention.NO_ACTION.value:
        return StoppingDecision(False, "customer opted out (do_not_contact) - contact-based actions blocked")

    if amount_paise < MIN_AMOUNT_PAISE_TO_ACT and proposed_intervention != Intervention.NO_ACTION.value:
        return StoppingDecision(False, "amount below minimum threshold for automated recovery")

    max_attempts = MAX_ATTEMPTS.get(category, 3)
    if attempts_so_far >= max_attempts and proposed_intervention != Intervention.ESCALATE_TO_HUMAN.value:
        return StoppingDecision(False, f"max attempts ({max_attempts}) reached - must escalate, not retry")

    cooldown = COOLDOWN_HOURS.get(proposed_intervention, 0)
    if hours_since_last_attempt is not None and hours_since_last_attempt < cooldown:
        return StoppingDecision(
            False,
            f"cooldown not elapsed ({hours_since_last_attempt:.1f}h < {cooldown}h required)",
        )

    return StoppingDecision(True, "ok")
