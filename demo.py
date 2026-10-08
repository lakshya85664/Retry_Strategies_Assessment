from src.retry_strategies import (
    TransientError,
    PermanentError,
    retry,
    backoff_delays,
    is_retry_safe,
    validate_retry_safety,
)


def main():
    print("=" * 70)
    print("Topic 14 — Retry Strategies Live Demonstration")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. Immediate success
    # ------------------------------------------------------------
    print("\n[1] Immediate Success")

    result = retry(
        lambda: "success",
        max_attempts=4,
    )

    print("Result:", result)

    # ------------------------------------------------------------
    # 2. Transient failure -> retry -> success
    # ------------------------------------------------------------
    print("\n[2] Transient Failure -> Retry -> Success")

    state = {"attempts": 0}

    def transient_then_success():
        state["attempts"] += 1

        if state["attempts"] < 3:
            raise TransientError("temporary service failure")

        return "recovered"

    result = retry(
        transient_then_success,
        max_attempts=4,
        sleep=lambda seconds: None,
    )

    print("Result:", result)

    # ------------------------------------------------------------
    # 3. Permanent failure -> no retry
    # ------------------------------------------------------------
    print("\n[3] Permanent Failure -> No Retry")

    permanent_attempts = {"count": 0}

    def permanent_failure():
        permanent_attempts["count"] += 1
        raise PermanentError("invalid request")

    result = retry(
        permanent_failure,
        max_attempts=4,
        sleep=lambda seconds: None,
    )

    print("Result:", result)
    print("Actual function calls:", permanent_attempts["count"])

    # ------------------------------------------------------------
    # 4. Time budget
    # ------------------------------------------------------------
    print("\n[4] Time Budget Stops Retries")

    sleep_calls = []

    def always_transient():
        raise TransientError("temporary failure")

    result = retry(
        always_transient,
        max_attempts=5,
        budget_seconds=0.6,
        sleep=lambda seconds: sleep_calls.append(seconds),
    )

    print("Result:", result)
    print("Recorded sleep:", sleep_calls)
    print("Total simulated wait:", round(sum(sleep_calls), 3))

    # ------------------------------------------------------------
    # 5. Deterministic fake-sleep backoff
    # ------------------------------------------------------------
    print("\n[5] Deterministic Backoff Delays")

    import random

    delays = backoff_delays(
        max_attempts=5,
        rng=random.Random(42),
    )

    print("Generated delays:", delays)

    # ------------------------------------------------------------
    # 6. Retry safety / idempotency
    # ------------------------------------------------------------
    print("\n[6] Retry Safety and Idempotency")

    print("GET safe:", is_retry_safe("GET"))
    print("POST without idempotency:", is_retry_safe("POST"))
    print(
        "POST with idempotency:",
        is_retry_safe("POST", idempotent=True),
    )

    try:
        validate_retry_safety("POST")
    except Exception as error:
        print("Unsafe POST blocked:", error)

    validate_retry_safety(
        "POST",
        idempotent=True,
    )

    print("Idempotent POST accepted.")

    print("\n" + "=" * 70)
    print("Live demonstration completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()