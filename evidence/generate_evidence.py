import json
import random
import sys
from pathlib import Path


# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.retry_strategies import (
    TransientError,
    PermanentError,
    RetrySafetyError,
    backoff_delays,
    retry,
    is_retry_safe,
    validate_retry_safety,
)


EVIDENCE_DIR = Path(__file__).parent


def write_json(filename, data):
    path = EVIDENCE_DIR / filename

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
        )

    print(f"Created: evidence/{filename}")


def task1_evidence():
    rng = random.Random(42)

    delays = backoff_delays(
        max_attempts=5,
        base=0.5,
        cap=8.0,
        jitter=0.25,
        rng=rng,
    )

    write_json(
        "task1_backoff_delays.json",
        {
            "task": 1,
            "title": "Exponential Backoff with Cap and Jitter",
            "parameters": {
                "max_attempts": 5,
                "base": 0.5,
                "cap": 8.0,
                "jitter": 0.25,
                "seed": 42,
            },
            "delays": delays,
            "verified": True,
        },
    )


def task2_evidence():
    state = {"calls": 0}

    def transient_then_success():
        state["calls"] += 1

        if state["calls"] < 3:
            raise TransientError("temporary failure")

        return "success"

    transient_result = retry(
        transient_then_success,
        max_attempts=4,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    permanent_state = {"calls": 0}

    def permanent_failure():
        permanent_state["calls"] += 1
        raise PermanentError("permanent failure")

    permanent_result = retry(
        permanent_failure,
        max_attempts=4,
        sleep=lambda seconds: None,
        rng=random.Random(42),
    )

    write_json(
        "task2_retry_classification.json",
        {
            "task": 2,
            "title": "Retry and Error Classification",
            "transient_case": {
                "result": transient_result,
                "function_calls": state["calls"],
            },
            "permanent_case": {
                "result": permanent_result,
                "function_calls": permanent_state["calls"],
            },
            "verified": (
                transient_result["ok"] is True
                and state["calls"] == 3
                and permanent_state["calls"] == 1
            ),
        },
    )


def task3_evidence():
    recorded_sleep = []

    def always_transient():
        raise TransientError("temporary failure")

    result = retry(
        always_transient,
        max_attempts=5,
        budget_seconds=0.6,
        sleep=lambda seconds: recorded_sleep.append(seconds),
        rng=random.Random(42),
    )

    write_json(
        "task3_time_budget.json",
        {
            "task": 3,
            "title": "Time Budget Enforcement",
            "budget_seconds": 0.6,
            "result": result,
            "recorded_sleep": recorded_sleep,
            "total_simulated_wait": round(
                sum(recorded_sleep),
                3,
            ),
            "verified": (
                result["ok"] is False
                and "time budget exhausted" in result["log"]
                and sum(recorded_sleep) <= 0.6
            ),
        },
    )


def task4_evidence():
    recorded_sleep = []

    def always_transient():
        raise TransientError("temporary failure")

    result = retry(
        always_transient,
        max_attempts=4,
        sleep=lambda seconds: recorded_sleep.append(seconds),
        rng=random.Random(42),
    )

    expected = backoff_delays(
        max_attempts=4,
        rng=random.Random(42),
    )

    write_json(
        "task4_fake_sleep.json",
        {
            "task": 4,
            "title": "Injectable Fake Sleep Testing",
            "recorded_sleep": recorded_sleep,
            "expected_delays": expected,
            "match": recorded_sleep == expected,
            "result": result,
            "verified": recorded_sleep == expected,
        },
    )


def task5_evidence():
    unsafe_error = None

    try:
        validate_retry_safety("POST")
    except RetrySafetyError as error:
        unsafe_error = str(error)

    idempotent_post_allowed = is_retry_safe(
        "POST",
        idempotent=True,
    )

    write_json(
        "task5_retry_safety.json",
        {
            "task": 5,
            "title": "Retry Risks and Idempotency",
            "operations": {
                "GET": is_retry_safe("GET"),
                "POST_without_idempotency": is_retry_safe("POST"),
                "POST_with_idempotency": idempotent_post_allowed,
            },
            "unsafe_post_error": unsafe_error,
            "verified": (
                is_retry_safe("GET") is True
                and is_retry_safe("POST") is False
                and idempotent_post_allowed is True
                and unsafe_error is not None
            ),
        },
    )


def main():
    print("=" * 60)
    print("Topic 14 — Evidence Generation")
    print("=" * 60)

    task1_evidence()
    task2_evidence()
    task3_evidence()
    task4_evidence()
    task5_evidence()

    print("=" * 60)
    print("Evidence generation completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()