"""Razorpay-shaped data models for the mock test-mode layer.

Field names and error-code vocabulary mirror Razorpay's real API docs
(https://razorpay.com/docs/api/errors/) closely enough that swapping this
module for a real Razorpay SDK client would need no changes downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CaseCategory(str, Enum):
    FAILED_PAYMENT = "failed_payment"
    ABANDONED_CHECKOUT = "abandoned_checkout"
    OVERDUE_RECEIVABLE = "overdue_receivable"
    FAILED_MANDATE = "failed_mandate"


# Real Razorpay error codes (subset) - see razorpay.com/docs/api/errors/
RAZORPAY_ERROR_CODES = {
    "BAD_REQUEST_ERROR": "insufficient_funds",
    "GATEWAY_ERROR": "gateway_timeout",
    "SERVER_ERROR": "gateway_timeout",
    "CARD_EXPIRED": "card_expired",
    "CARD_DECLINED": "issuer_declined",
    "AUTHENTICATION_FAILED": "otp_failed",
    "MANDATE_NOT_APPROVED": "mandate_not_approved",
    "INSUFFICIENT_FUNDS": "insufficient_funds",
}


@dataclass
class Customer:
    id: str
    name: str
    email: str
    contact: str
    prefers_hinglish: bool = False
    do_not_contact: bool = False


@dataclass
class Case:
    """A single revenue-at-risk record, shaped like a Razorpay Payment/Order/
    Invoice/Mandate object depending on `category`."""

    id: str
    category: CaseCategory
    amount_paise: int  # Razorpay amounts are always in paise
    currency: str
    created_at: datetime
    customer: Customer
    method: str  # card, upi, netbanking, emandate
    error_code: str | None = None  # Razorpay error code, if any
    checkout_opened_at: datetime | None = None
    payment_captured_at: datetime | None = None
    invoice_due_at: datetime | None = None
    subscription_id: str | None = None
    notes: dict = field(default_factory=dict)

    @property
    def amount_inr(self) -> float:
        return self.amount_paise / 100
