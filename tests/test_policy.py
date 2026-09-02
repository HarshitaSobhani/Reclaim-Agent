from agent.policy import Intervention, check_stopping_rules


def test_rejects_unknown_intervention():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=0,
        hours_since_last_attempt=None,
        proposed_intervention="do_something_wild",
        do_not_contact=False,
    )
    assert not d.allowed
    assert "unknown intervention" in d.reason


def test_blocks_contact_when_do_not_contact():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=0,
        hours_since_last_attempt=None,
        proposed_intervention=Intervention.RETRY_WITH_DELAY.value,
        do_not_contact=True,
    )
    assert not d.allowed
    assert "opted out" in d.reason


def test_allows_no_action_even_when_do_not_contact():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=0,
        hours_since_last_attempt=None,
        proposed_intervention=Intervention.NO_ACTION.value,
        do_not_contact=True,
    )
    assert d.allowed


def test_blocks_below_minimum_amount():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=1000,
        attempts_so_far=0,
        hours_since_last_attempt=None,
        proposed_intervention=Intervention.RETRY_WITH_DELAY.value,
        do_not_contact=False,
    )
    assert not d.allowed
    assert "threshold" in d.reason


def test_max_attempts_forces_escalation():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=3,
        hours_since_last_attempt=100,
        proposed_intervention=Intervention.RETRY_WITH_DELAY.value,
        do_not_contact=False,
    )
    assert not d.allowed
    assert "max attempts" in d.reason

    escalate = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=3,
        hours_since_last_attempt=100,
        proposed_intervention=Intervention.ESCALATE_TO_HUMAN.value,
        do_not_contact=False,
    )
    assert escalate.allowed


def test_cooldown_blocks_too_soon_retry():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=1,
        hours_since_last_attempt=1,
        proposed_intervention=Intervention.REQUEST_NEW_PAYMENT_METHOD.value,
        do_not_contact=False,
    )
    assert not d.allowed
    assert "cooldown" in d.reason


def test_cooldown_allows_after_elapsed():
    d = check_stopping_rules(
        category="failed_payment",
        amount_paise=100000,
        attempts_so_far=1,
        hours_since_last_attempt=24,
        proposed_intervention=Intervention.REQUEST_NEW_PAYMENT_METHOD.value,
        do_not_contact=False,
    )
    assert d.allowed
