import random

import pytest

from src.retry_strategies import (
    TransientError,
    PermanentError,
    backoff_delays,
    retry,
    is_retry_safe,
    validate_retry_safety,
    RetrySafetyError
)


# ============================================================
# Task 1 — backoff_delays()
# ============================================================

def test_backoff_returns_one_delay_between_attempts():
    delays = backoff_delays(
        max_attempts=4,
        base=0.5,
        cap=8.0,
        jitter=0.0,
    )

    assert delays == [
        0.5,
        1.0,
        2.0,
    ]


def test_backoff_uses_exponential_growth_without_jitter():
    delays = backoff_delays(
        max_attempts=5,
        base=1.0,
        cap=100.0,
        jitter=0.0,
    )

    assert delays == [
        1.0,
        2.0,
        4.0,
        8.0,
    ]


def test_backoff_respects_cap():
    delays = backoff_delays(
        max_attempts=6,
        base=1.0,
        cap=3.0,
        jitter=0.0,
    )

    assert delays == [
        1.0,
        2.0,
        3.0,
        3.0,
        3.0,
    ]


def test_backoff_jitter_is_repeatable_with_seed():
    rng1 = random.Random(42)
    rng2 = random.Random(42)

    delays1 = backoff_delays(
        max_attempts=5,
        base=0.5,
        cap=8.0,
        jitter=0.25,
        rng=rng1,
    )

    delays2 = backoff_delays(
        max_attempts=5,
        base=0.5,
        cap=8.0,
        jitter=0.25,
        rng=rng2,
    )

    assert delays1 == delays2


def test_backoff_jitter_stays_within_expected_range():
    rng = random.Random(42)

    delays = backoff_delays(
        max_attempts=5,
        base=1.0,
        cap=100.0,
        jitter=0.25,
        rng=rng,
    )

    base_delays = [1.0, 2.0, 4.0, 8.0]

    for actual, base_delay in zip(delays, base_delays):
        assert base_delay * 0.75 <= actual <= base_delay * 1.25


def test_backoff_returns_empty_for_one_attempt():
    delays = backoff_delays(
        max_attempts=1,
        base=0.5,
        cap=8.0,
        jitter=0.25,
    )

    assert delays == []


def test_backoff_rejects_invalid_attempt_count():
    with pytest.raises(ValueError, match="at least 1"):
        backoff_delays(max_attempts=0)


def test_backoff_rejects_invalid_jitter():
    with pytest.raises(ValueError, match="between 0 and 1"):
        backoff_delays(jitter=1.5)


def test_backoff_rejects_cap_smaller_than_base():
    with pytest.raises(
        ValueError,
        match="greater than or equal to base",
    ):
        backoff_delays(base=5.0, cap=2.0)


def test_error_classes_are_defined():
    assert issubclass(TransientError, Exception)
    assert issubclass(PermanentError, Exception)
    assert TransientError is not PermanentError

# ============================================================
# Task 2 — retry()
# ============================================================

def test_retry_succeeds_after_transient_failures():
    state = {"n": 0}

    def flaky():
        state["n"] += 1

        if state["n"] < 3:
            raise TransientError("503")

        return "payload"

    result = retry(
        flaky,
        max_attempts=4,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["value"] == "payload"
    assert result["attempts"] == 3
    assert state["n"] == 3
    assert result["log"] == [
        "attempt 1: transient 503",
        "attempt 2: transient 503",
        "attempt 3: ok",
    ]


def test_retry_stops_at_max_attempts():
    state = {"n": 0}

    def always_transient():
        state["n"] += 1
        raise TransientError("503")

    result = retry(
        always_transient,
        max_attempts=3,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert result["value"] is None
    assert state["n"] == 3
    assert result["attempts"] == 3


def test_retry_never_retries_permanent_error():
    state = {"n": 0}

    def permanent_failure():
        state["n"] += 1
        raise PermanentError("401")

    result = retry(
        permanent_failure,
        max_attempts=5,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert result["value"] is None
    assert result["attempts"] == 1
    assert state["n"] == 1
    assert result["log"] == [
        "attempt 1: permanent 401",
    ]


def test_retry_returns_immediately_on_first_success():
    state = {"n": 0}

    def successful():
        state["n"] += 1
        return "ready"

    result = retry(
        successful,
        max_attempts=5,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["value"] == "ready"
    assert result["attempts"] == 1
    assert state["n"] == 1


def test_retry_rejects_invalid_callable():
    with pytest.raises(TypeError, match="callable"):
        retry(
            "not callable",
            sleep=lambda seconds: None,
        )


def test_retry_rejects_invalid_max_attempts():
    with pytest.raises(ValueError, match="at least 1"):
        retry(
            lambda: "ok",
            max_attempts=0,
            sleep=lambda seconds: None,
        )


def test_retry_rejects_negative_budget():
    with pytest.raises(ValueError, match="non-negative"):
        retry(
            lambda: "ok",
            budget_seconds=-1,
            sleep=lambda seconds: None,
        )

# ============================================================
# Task 3 — Time budget
# ============================================================

def test_retry_allows_wait_that_fits_budget():
    state = {"n": 0}
    sleeps = []

    def flaky():
        state["n"] += 1

        if state["n"] == 1:
            raise TransientError("503")

        return "payload"

    result = retry(
        flaky,
        max_attempts=3,
        budget_seconds=1.0,
        sleep=sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["value"] == "payload"
    assert result["attempts"] == 2
    assert len(sleeps) == 1
    assert 0.0 < sleeps[0] <= 1.0


def test_retry_stops_when_next_delay_exceeds_budget():
    state = {"n": 0}
    sleeps = []

    def always_transient():
        state["n"] += 1
        raise TransientError("503")

    result = retry(
        always_transient,
        max_attempts=5,
        budget_seconds=0.1,
        sleep=sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert result["value"] is None
    assert state["n"] == 1
    assert sleeps == []
    assert "time budget exhausted" in result["log"]


def test_retry_does_not_sleep_after_budget_is_exhausted():
    sleeps = []

    def always_transient():
        raise TransientError("503")

    result = retry(
        always_transient,
        max_attempts=5,
        budget_seconds=0.0,
        sleep=sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert sleeps == []
    assert "time budget exhausted" in result["log"]


def test_retry_budget_allows_multiple_waits_when_they_fit():
    state = {"n": 0}
    sleeps = []

    def flaky():
        state["n"] += 1

        if state["n"] < 3:
            raise TransientError("503")

        return "done"

    result = retry(
        flaky,
        max_attempts=4,
        budget_seconds=2.0,
        sleep=sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["value"] == "done"
    assert result["attempts"] == 3
    assert len(sleeps) == 2
    assert sum(sleeps) <= 2.0

# ============================================================
# Task 4 — Fake sleep and exact delay verification
# ============================================================

def test_task4_fake_sleep_records_exact_delays():
    state = {"n": 0}
    recorded_sleeps = []

    def flaky():
        state["n"] += 1

        if state["n"] < 4:
            raise TransientError("503")

        return "payload"

    result = retry(
        flaky,
        max_attempts=4,
        budget_seconds=10.0,
        sleep=recorded_sleeps.append,
        rng=random.Random(42),
    )

    expected = backoff_delays(
        max_attempts=4,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["value"] == "payload"
    assert result["attempts"] == 4
    assert recorded_sleeps == expected


def test_task4_fake_sleep_is_never_real_sleep():
    recorded_sleeps = []

    def always_transient():
        raise TransientError("503")

    result = retry(
        always_transient,
        max_attempts=3,
        budget_seconds=10.0,
        sleep=recorded_sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert len(recorded_sleeps) == 2
    assert all(delay > 0 for delay in recorded_sleeps)


def test_task4_sleep_count_matches_successful_retries():
    state = {"n": 0}
    recorded_sleeps = []

    def succeeds_on_second_attempt():
        state["n"] += 1

        if state["n"] == 1:
            raise TransientError("temporary failure")

        return "success"

    result = retry(
        succeeds_on_second_attempt,
        max_attempts=5,
        budget_seconds=10.0,
        sleep=recorded_sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is True
    assert result["attempts"] == 2
    assert recorded_sleeps == [0.535]


def test_task4_sleep_is_not_called_after_final_attempt():
    recorded_sleeps = []

    def always_transient():
        raise TransientError("503")

    result = retry(
        always_transient,
        max_attempts=1,
        budget_seconds=10.0,
        sleep=recorded_sleeps.append,
        rng=random.Random(42),
    )

    assert result["ok"] is False
    assert result["attempts"] == 1
    assert recorded_sleeps == []

# ============================================================
# Task 5 — Retry risks and idempotency
# ============================================================

def test_task5_get_is_retry_safe():
    assert is_retry_safe("GET") is True


def test_task5_head_is_retry_safe():
    assert is_retry_safe("HEAD") is True


def test_task5_post_is_not_safe_without_idempotency():
    assert is_retry_safe("POST") is False


def test_task5_post_is_safe_with_idempotency():
    assert is_retry_safe(
        "POST",
        idempotent=True,
    ) is True


def test_task5_patch_is_not_safe_without_idempotency():
    assert is_retry_safe("PATCH") is False


def test_task5_delete_is_not_safe_without_idempotency():
    assert is_retry_safe("DELETE") is False


def test_task5_unsafe_operation_raises():
    with pytest.raises(
        RetrySafetyError,
        match="not safe to retry",
    ):
        validate_retry_safety("POST")


def test_task5_idempotent_post_is_allowed():
    validate_retry_safety(
        "POST",
        idempotent=True,
    )


def test_task5_unsupported_operation_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported operation",
    ):
        is_retry_safe("CONNECT")


def test_task5_invalid_operation_type_is_rejected():
    with pytest.raises(
        TypeError,
        match="operation must be a string",
    ):
        is_retry_safe(123)


def test_task5_retry_risk_is_explicitly_documented():
    """
    Demonstrate why side-effecting operations require
    idempotency protection before retries are allowed.
    """
    with pytest.raises(RetrySafetyError):
        validate_retry_safety("POST")

    # With idempotency protection, the same operation becomes retry-safe.
    validate_retry_safety(
        "POST",
        idempotent=True,
    )