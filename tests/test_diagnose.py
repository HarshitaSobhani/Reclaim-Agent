from datetime import datetime, timedelta

from agent.diagnose import diagnose
from mock_razorpay.models import Case, CaseCategory, Customer

CUST = Customer(id="c1", name="Test User", email="t@example.com", contact="+911234567890")


def _case(**overrides) -> Case:
    base = dict(
        id="case_x",
        category=CaseCategory.FAILED_PAYMENT,
        amount_paise=100000,
        currency="INR",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        customer=CUST,
        method="card",
    )
    base.update(overrides)
    return Case(**base)


def test_failed_payment_maps_known_error_code():
    case = _case(error_code="CARD_EXPIRED")
    d = diagnose(case, now=case.created_at)
    assert d.root_cause == "card_expired"
    assert d.is_actionable
    assert d.confidence == "high"


def test_failed_payment_unknown_error_code_low_confidence():
    case = _case(error_code="SOME_NEW_CODE")
    d = diagnose(case, now=case.created_at)
    assert d.confidence == "low"
    assert d.is_actionable


def test_abandoned_checkout_within_grace_not_actionable():
    opened = datetime(2026, 1, 1, 12, 0, 0)
    case = _case(category=CaseCategory.ABANDONED_CHECKOUT, checkout_opened_at=opened, created_at=opened)
    d = diagnose(case, now=opened + timedelta(minutes=1))
    assert not d.is_actionable
    assert d.root_cause == "checkout_in_progress"


def test_abandoned_checkout_past_grace_is_actionable():
    opened = datetime(2026, 1, 1, 12, 0, 0)
    case = _case(category=CaseCategory.ABANDONED_CHECKOUT, checkout_opened_at=opened, created_at=opened)
    d = diagnose(case, now=opened + timedelta(minutes=30))
    assert d.is_actionable
    assert d.root_cause == "checkout_abandoned"


def test_overdue_receivable_actionable_when_past_due():
    due = datetime(2026, 1, 1, 0, 0, 0)
    case = _case(category=CaseCategory.OVERDUE_RECEIVABLE, invoice_due_at=due, created_at=due)
    d = diagnose(case, now=due + timedelta(days=5))
    assert d.is_actionable
    assert d.root_cause == "invoice_overdue"


def test_failed_mandate_maps_error_code():
    case = _case(category=CaseCategory.FAILED_MANDATE, error_code="MANDATE_NOT_APPROVED")
    d = diagnose(case, now=case.created_at)
    assert d.root_cause == "mandate_not_approved"
    assert d.is_actionable
