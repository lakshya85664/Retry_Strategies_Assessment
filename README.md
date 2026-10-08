# Topic 14 — Retry Strategies Assessment

## Project Overview

This project implements and tests practical retry strategies for AI-agent workflows and other unreliable operations. The implementation focuses on controlled retries, exponential backoff, error classification, time budgets, deterministic testing, and retry safety.

**Project:** Retry Strategies Assessment  

## Objectives

- Implement exponential backoff with a configurable cap.
- Add deterministic jitter using an injectable random-number generator.
- Retry transient errors while avoiding retries for permanent errors.
- Enforce a maximum number of attempts.
- Enforce a total retry time budget.
- Inject a fake sleep function so tests never need real waiting.
- Record attempt outcomes for traceability.
- Demonstrate retry risks and idempotency requirements for side-effecting operations.

## Implementation

The main implementation is in:

`src/retry_strategies.py`

It provides:

- `TransientError`
- `PermanentError`
- `RetrySafetyError`
- `backoff_delays()`
- `retry()`
- `is_retry_safe()`
- `validate_retry_safety()`

### Backoff Strategy

Retry delays use exponential growth:

`min(cap, base × 2^n)`

A multiplicative jitter factor is then applied within the configured jitter range. A seeded RNG can be injected to make the generated delays deterministic during testing.

For the verified seed `42`, the five-attempt configuration generated:

`[0.535, 0.763, 1.775, 3.446]`

## Task Results

### Task 1 — Exponential Backoff with Cap and Jitter

Implemented exponential backoff with configurable base delay, cap, jitter, validation, and deterministic RNG support.

**Result:** Passed.

### Task 2 — Retry and Error Classification

Transient errors are retried up to the configured maximum. Permanent errors stop execution immediately and are not retried.

The live demonstration confirmed a transient operation failing twice and succeeding on the third attempt, while a permanent failure resulted in exactly one function call.

**Result:** Passed.

### Task 3 — Time Budget

The retry mechanism checks whether the next delay would exceed the configured retry budget. If it would, the retry process stops and records that the time budget was exhausted.

The verified evidence used a `0.6` second budget and simulated `0.535` seconds of waiting.

**Result:** Passed.

### Task 4 — Fake Sleep Testing

The retry function accepts an injectable sleep callable. Tests therefore record delays instead of actually waiting.

For the deterministic test, recorded delays exactly matched the expected values:

`[0.535, 0.763, 1.775]`

**Result:** Passed.

### Task 5 — Retry Risks and Idempotency

The implementation explicitly checks whether an operation is safe to retry.

- `GET` is treated as retry-safe.
- `POST` without idempotency protection is blocked.
- `POST` with idempotency protection is allowed.
- Unsafe operations raise `RetrySafetyError`.
- Unsupported operations and invalid operation types are rejected.

This demonstrates why retrying side-effecting operations can create duplicate effects unless idempotency protection is available.

**Result:** Passed.

## Testing

Focused and full regression testing were completed successfully.

```text
python -m pytest tests\test_retry_strategies.py -q
36 passed

python -m pytest -q
36 passed
```

## Live Demonstration

The live demonstration verified:

1. Immediate success.
2. Transient failure followed by successful retry.
3. Permanent failure with exactly one function call.
4. Retry stopping because of the time budget.
5. Deterministic backoff delays.
6. Retry safety and idempotency checks.

## Evidence

Generated evidence files:

```text
evidence/
├── task1_backoff_delays.json
├── task2_retry_classification.json
├── task3_time_budget.json
├── task4_fake_sleep.json
└── task5_retry_safety.json
```

All five evidence files reported `verified: true`.

## Assessment Result

| Task | Marks | Status |
|---|---:|---|
| Task 1 — Backoff | 20/20 | PASS |
| Task 2 — Retry & Classification | 20/20 | PASS |
| Task 3 — Time Budget | 20/20 | PASS |
| Task 4 — Fake Sleep | 20/20 | PASS |
| Task 5 — Retry Safety | 20/20 | PASS |
| **Core Total** | **100/100** | **PASS** |

The optional Retry-After stretch task was not implemented.

## Key Learning

This activity demonstrated that retries are not simply a matter of calling an operation repeatedly. A robust retry mechanism needs controlled backoff, bounded attempts, time limits, error classification, deterministic testing, and clear traceability. It also needs to consider whether repeating an operation is safe. In particular, side-effecting operations can create duplicate actions when a request succeeds but its response is lost, causing a retry to perform the same action again. Idempotency keys or equivalent safeguards make such retries safer. Injectable dependencies such as a fake sleep function and seeded random generator also make retry behavior reproducible and testable without introducing real delays. Overall, the project strengthened practical understanding of reliability patterns that are important in production agent and API workflows.

## Reflection

This activity helped me understand that retry logic is a reliability mechanism rather than simply repeating a failed operation. The most important part was learning how to distinguish between transient and permanent failures. A transient failure may be caused by a temporary network or service problem, so retrying can be useful. A permanent failure, such as an invalid request, should stop immediately because repeating the same request will not solve the underlying problem.

Implementing exponential backoff also showed why retries need controlled timing. Increasing the delay between attempts reduces the chance of overwhelming an unavailable service. Adding a cap prevents the delay from growing without a practical limit, while deterministic jitter helps avoid synchronized retry patterns. Using a seeded random generator made the behavior reproducible during testing.

The time-budget requirement was another important lesson. A retry mechanism should not continue indefinitely just because the maximum attempt count has not been reached. The system also needs a clear time boundary so that an operation can stop when further retries are no longer worthwhile. Injectable sleep made this behavior much easier to test because the tests could record simulated delays without actually waiting.

The idempotency task was especially useful from a real-world perspective. Retrying a side-effecting operation can accidentally create duplicate actions if the original request succeeded but its response was lost. This means retry safety must be considered before automatically retrying operations such as POST requests. Idempotency protection provides a way to make these retries safer.

Overall, this project strengthened my understanding of reliability patterns used in production systems and AI-agent workflows. It also reinforced the importance of deterministic testing, clear error classification, bounded execution, and traceable retry behavior.

