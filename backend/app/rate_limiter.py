"""
In-Memory Rate Limiting and Brute Force Protection
===================================================
Provides:
1. IP-based sliding window rate limiter for public endpoints (emergency triage, SOS, hospitals).
2. Login attempt rate limiting and temporary account lockout.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status

# In-memory storage: key -> list of float timestamps
_rate_limits: Dict[str, List[float]] = defaultdict(list)

# Login failed attempts: key (ip or email) -> list of failure timestamps
_login_failures: Dict[str, List[float]] = defaultdict(list)
_lockouts: Dict[str, float] = {}  # key -> lockout_until timestamp


def get_client_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For or client.host."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def check_rate_limit(
    request: Request,
    limit: int = 30,
    window_seconds: int = 60,
    scope: str = "default",
) -> None:
    """
    Enforce sliding window IP rate limiting.
    Raises HTTPException(429) if client exceeds limit in window.
    """
    ip = get_client_ip(request)
    key = f"{scope}:{ip}"
    now = time.time()
    cutoff = now - window_seconds

    # Filter out expired timestamps
    valid_timestamps = [ts for ts in _rate_limits[key] if ts > cutoff]
    if len(valid_timestamps) >= limit:
        oldest = valid_timestamps[0]
        retry_after = max(1, int(oldest + window_seconds - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {scope}: maximum {limit} requests per minute.",
            headers={"Retry-After": str(retry_after)},
        )

    valid_timestamps.append(now)
    _rate_limits[key] = valid_timestamps


def record_failed_login(identifier: str, max_attempts: int = 5, lockout_seconds: int = 900) -> None:
    """Record a failed login attempt and apply lockout if threshold exceeded."""
    now = time.time()
    cutoff = now - 300  # 5-minute rolling window for attempts
    valid_failures = [ts for ts in _login_failures[identifier] if ts > cutoff]
    valid_failures.append(now)
    _login_failures[identifier] = valid_failures

    if len(valid_failures) >= max_attempts:
        _lockouts[identifier] = now + lockout_seconds


def is_login_locked(identifier: str) -> Tuple[bool, int]:
    """Check if identifier (IP or email) is currently locked out."""
    now = time.time()
    lockout_until = _lockouts.get(identifier, 0)
    if lockout_until > now:
        remaining_seconds = max(1, int(lockout_until - now))
        return True, remaining_seconds
    if identifier in _lockouts:
        del _lockouts[identifier]
    return False, 0


def record_successful_login(identifier: str) -> None:
    """Reset failed login counters on successful authentication."""
    if identifier in _login_failures:
        del _login_failures[identifier]
    if identifier in _lockouts:
        del _lockouts[identifier]


def reset_rate_limits_for_testing() -> None:
    """Utility to clear in-memory rate limits during test runs."""
    _rate_limits.clear()
    _login_failures.clear()
    _lockouts.clear()
