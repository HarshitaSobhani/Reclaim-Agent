import random

from agent.executor import CaseState, CaseStatus, simulate_outcome
from agent.policy import Intervention


def test_simulate_outcome_deterministic_with_seed():
    rng1 = random.Random(1)
    rng2 = random.Random(1)
    results1 = [simulate_outcome(rng1, Intervention.INSTANT_RETRY.value) for _ in range(20)]
    results2 = [simulate_outcome(rng2, Intervention.INSTANT_RETRY.value) for _ in range(20)]
    assert results1 == results2


def test_simulate_outcome_unknown_intervention_never_succeeds():
    rng = random.Random(1)
    assert all(not simulate_outcome(rng, "not_a_real_intervention") for _ in range(20))


def test_case_state_defaults():
    s = CaseState(case_id="c1")
    assert s.status == CaseStatus.OPEN
    assert s.attempts == 0
    assert s.recovered_amount_paise == 0


def test_run_batch_end_to_end_produces_consistent_totals():
    from run_batch import run
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        summary = run(n=30, seed=7, out_dir=tmp)
        assert summary["total_recovered_inr"] <= summary["total_at_risk_inr"]
        assert 0 <= summary["recovery_rate_pct"] <= 100
        assert sum(summary["status_breakdown"].values()) == 30
