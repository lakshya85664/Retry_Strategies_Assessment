"""
Topic 14: Retry Strategies

Tasks 1-2:
- Exponential backoff with cap and jitter.
- Retry transient errors only.
- Never retry permanent errors.
- Respect max_attempts.
"""

import random


class TransientError(Exception):
    """Raised when an operation may succeed if retried."""
    pass


class PermanentError(Exception):
    """Raised when retrying the operation is unsafe or pointless."""
    pass

class RetrySafetyError(Exception):
    """Raised when an operation is unsafe to retry without idempotency."""
    pass


def is_retry_safe(
    operation: str,
    *,
    idempotent: bool = False,
) -> bool:
    """
    Determine whether an operation may safely be retried.

    Read-only operations such as GET are treated as retry-safe.

    Side-effecting operations such as POST require explicit
    idempotency protection.
    """
    if not isinstance(operation, str):
        raise TypeError("operation must be a string")

    operation = operation.upper()

    if operation in {"GET", "HEAD", "OPTIONS"}:
        return True

    if operation in {"POST", "PATCH", "DELETE"}:
        return bool(idempotent)

    raise ValueError(
        f"unsupported operation: {operation}"
    )


def validate_retry_safety(
    operation: str,
    *,
    idempotent: bool = False,
) -> None:
    """
    Raise RetrySafetyError when an operation should not be retried.
    """
    if not is_retry_safe(
        operation,
        idempotent=idempotent,
    ):
        raise RetrySafetyError(
            f"{operation.upper()} is not safe to retry "
            "without idempotency protection"
        )

def backoff_delays(
    max_attempts: int = 5,
    base: float = 0.5,
    cap: float = 8.0,
    jitter: float = 0.25,
    rng=None,
) -> list[float]:
    """
    Return retry delays using exponential backoff with jitter.

    Delay before retry n:
        min(cap, base * 2**n)

    A multiplicative jitter factor in the range
    [1-jitter, 1+jitter] is then applied.
    """
    if not isinstance(max_attempts, int):
        raise TypeError("max_attempts must be an integer")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if not isinstance(base, (int, float)):
        raise TypeError("base must be numeric")

    if base < 0:
        raise ValueError("base must be non-negative")

    if not isinstance(cap, (int, float)):
        raise TypeError("cap must be numeric")

    if cap < 0:
        raise ValueError("cap must be non-negative")

    if not isinstance(jitter, (int, float)):
        raise TypeError("jitter must be numeric")

    if not 0 <= jitter <= 1:
        raise ValueError("jitter must be between 0 and 1")

    if cap < base:
        raise ValueError("cap must be greater than or equal to base")

    if rng is None:
        rng = random.Random()

    if not hasattr(rng, "uniform"):
        raise TypeError("rng must provide a uniform method")

    delays = []

    for n in range(max_attempts - 1):
        delay = min(cap, base * (2 ** n))

        factor = 1 + rng.uniform(-jitter, jitter)

        delay = delay * factor

        delays.append(round(delay, 3))

    return delays


def retry(
    fn,
    max_attempts: int = 4,
    budget_seconds: float = 10.0,
    sleep=None,
    rng=None,
) -> dict:
    """
    Retry a callable when it raises TransientError.

    PermanentError is returned immediately and is never retried.

    The sleep function is injectable so tests can avoid real waiting.

    Returns:
        {
            "ok": bool,
            "value": result_or_none,
            "attempts": number_of_attempts,
            "log": list_of_attempt_messages,
        }
    """
    if not callable(fn):
        raise TypeError("fn must be callable")

    if not isinstance(max_attempts, int):
        raise TypeError("max_attempts must be an integer")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if not isinstance(budget_seconds, (int, float)):
        raise TypeError("budget_seconds must be numeric")

    if budget_seconds < 0:
        raise ValueError("budget_seconds must be non-negative")

    if sleep is None:
        sleep = lambda seconds: None

    if not callable(sleep):
        raise TypeError("sleep must be callable")

    if rng is None:
        rng = random.Random()

    delays = backoff_delays(
        max_attempts=max_attempts,
        rng=rng,
    )

    log = []
    waited = 0.0

    for attempt in range(1, max_attempts + 1):
        try:
            value = fn()

            log.append(
                f"attempt {attempt}: ok"
            )

            return {
                "ok": True,
                "value": value,
                "attempts": attempt,
                "log": log,
            }

        except PermanentError as error:
            log.append(
                f"attempt {attempt}: permanent {error}"
            )

            return {
                "ok": False,
                "value": None,
                "attempts": attempt,
                "log": log,
            }

        except TransientError as error:
            log.append(
                f"attempt {attempt}: transient {error}"
            )

            if attempt == max_attempts:
                break

            delay = delays[attempt - 1]

            if waited + delay > budget_seconds:
                log.append("time budget exhausted")
                break

            sleep(delay)
            waited += delay

    return {
        "ok": False,
        "value": None,
        "attempts": len(log),
        "log": log,
    }