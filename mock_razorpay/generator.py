"""Generates a synthetic, reproducible batch of revenue-at-risk cases shaped
like real Razorpay test-mode data. No network calls, no real account needed.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .models import Case, CaseCategory, Customer, RAZORPAY_ERROR_CODES

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditi", "Diya", "Kabir", "Meera", "Rohan", "Isha",
    "Arjun", "Neha", "Karan", "Priya", "Sanjay", "Ananya", "Rahul", "Tanvi",
]
LAST_NAMES = ["Sharma", "Patel", "Reddy", "Iyer", "Gupta", "Nair", "Verma", "Singh"]

METHODS_BY_CATEGORY = {
    CaseCategory.FAILED_PAYMENT: ["card", "upi", "netbanking"],
    CaseCategory.ABANDONED_CHECKOUT: ["card", "upi", "wallet"],
    CaseCategory.OVERDUE_RECEIVABLE: ["bank_transfer", "cheque"],
    CaseCategory.FAILED_MANDATE: ["emandate", "upi_autopay"],
}

ERROR_CODES = list(RAZORPAY_ERROR_CODES.keys())


def _random_customer(rng: random.Random, i: int) -> Customer:
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    return Customer(
        id=f"cust_{i:04d}",
        name=name,
        email=f"{name.lower().replace(' ', '.')}{i}@example.com",
        contact=f"+91{rng.randint(7000000000, 9999999999)}",
        prefers_hinglish=rng.random() < 0.4,
        do_not_contact=rng.random() < 0.05,
    )


def generate_batch(n: int = 80, seed: int = 42) -> list[Case]:
    rng = random.Random(seed)
    now = datetime(2026, 8, 21, 10, 0, 0)
    cases: list[Case] = []

    # Weighted category mix: failed payments and abandoned checkouts are the
    # most common revenue-at-risk events in a typical merchant's funnel.
    category_weights = [
        (CaseCategory.FAILED_PAYMENT, 0.40),
        (CaseCategory.ABANDONED_CHECKOUT, 0.30),
        (CaseCategory.OVERDUE_RECEIVABLE, 0.15),
        (CaseCategory.FAILED_MANDATE, 0.15),
    ]
    categories = rng.choices(
        [c for c, _ in category_weights],
        weights=[w for _, w in category_weights],
        k=n,
    )

    for i, category in enumerate(categories):
        customer = _random_customer(rng, i)
        amount_paise = rng.choice(
            [50000, 99900, 149900, 249900, 499900, 999900, 1999900]
        )
        method = rng.choice(METHODS_BY_CATEGORY[category])
        created_at = now - timedelta(hours=rng.randint(1, 240))

        error_code = None
        checkout_opened_at = None
        payment_captured_at = None
        invoice_due_at = None
        subscription_id = None

        if category == CaseCategory.FAILED_PAYMENT:
            error_code = rng.choice(ERROR_CODES)
        elif category == CaseCategory.ABANDONED_CHECKOUT:
            checkout_opened_at = created_at
            # 5% "abandon" for <2 min (still mid-checkout, not really at risk)
            minutes = rng.choice([1, 2, 5, 15, 30, 45, 90, 180])
            checkout_opened_at = created_at
            created_at = checkout_opened_at + timedelta(minutes=minutes)
        elif category == CaseCategory.OVERDUE_RECEIVABLE:
            invoice_due_at = created_at - timedelta(days=rng.randint(1, 60))
            amount_paise *= rng.randint(3, 10)  # B2B invoices are larger
        elif category == CaseCategory.FAILED_MANDATE:
            error_code = rng.choice(
                ["MANDATE_NOT_APPROVED", "INSUFFICIENT_FUNDS", "BAD_REQUEST_ERROR"]
            )
            subscription_id = f"sub_{i:04d}"

        cases.append(
            Case(
                id=f"case_{i:04d}",
                category=category,
                amount_paise=amount_paise,
                currency="INR",
                created_at=created_at,
                customer=customer,
                method=method,
                error_code=error_code,
                checkout_opened_at=checkout_opened_at,
                payment_captured_at=payment_captured_at,
                invoice_due_at=invoice_due_at,
                subscription_id=subscription_id,
            )
        )

    return cases
