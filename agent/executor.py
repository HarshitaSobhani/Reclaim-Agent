"""Simulated execution against the mock Razorpay layer, with a per-case state
machine and an append-only audit trail. Nothing here calls a real payment
gateway - `simulate_outcome` stands in for what a real retry/webhook
response would tell us.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum

from agent.policy import Intervention


class CaseStatus(str, Enum):
    OPEN = "open"
    ATTEMPTED = "attempted"
    RECOVERED = "recovered"
    FAILED = "failed"
    ESCALATED = "escalated"
    SKIPPED = "skipped"


# Success probability per intervention, used only to simulate a realistic
# outcome distribution for the demo (a real system reads this from the
# gateway's actual retry/webhook response).
SUCCESS_RATE = {
    Intervention.INSTANT_RETRY.value: 0.55,
    Intervention.RETRY_WITH_DELAY.value: 0.45,
    Intervention.REQUEST_NEW_PAYMENT_METHOD.value: 0.35,
    Intervention.SEND_CHECKOUT_NUDGE.value: 0.25,
    Intervention.SEND_MANDATE_RETRY_LINK.value: 0.40,
    Intervention.SEND_RECEIVABLE_REMINDER.value: 0.30,
}


@dataclass
class AuditEvent:
    timestamp: str
    case_id: str
    category: str
    amount_inr: float
    attempt_number: int
    root_cause: str
    diagnosis_confidence: str
    intervention: str
    decision_source: str
    rationale: str
    message_sent: str
    gate_allowed: bool
    gate_reason: str
    outcome: str  # "recovered" | "failed" | "not_attempted"
    status_after: str


@dataclass
class CaseState:
    case_id: str
    status: CaseStatus = CaseStatus.OPEN
    attempts: int = 0
    last_attempt_at: datetime | None = None
    recovered_amount_paise: int = 0


def simulate_outcome(rng: random.Random, intervention: str) -> bool:
    rate = SUCCESS_RATE.get(intervention, 0.0)
    return rng.random() < rate


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)

    def write(self) -> None:
        with open(self.path, "w") as f:
            for e in self.events:
                f.write(json.dumps(asdict(e)) + "\n")
