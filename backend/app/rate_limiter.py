"""
Persistent & Shared Rate Limiter with Trusted Proxy Client IP Extraction
========================================================================
Architecture (Render behind Vercel):
- Vercel Edge proxies requests to Render Load Balancer.
- Each proxy appends the remote address it received the connection from to the
  RIGHT side of X-Forwarded-For.
- Attackers can prepend arbitrary spoofed values to X-Forwarded-For.
- Blindly reading the leftmost IP (x_forwarded_for.split(',')[0]) is vulnerable to IP spoofing.
- Solution:
  1. If request comes through Vercel (x-vercel-id / x-vercel-forwarded-for present),
     we use Vercel's verified client IP or inspect the 2nd hop from the right (ips[-2]).
  2. If direct to Render (1 hop), we inspect the rightmost IP appended by Render (ips[-1]).
  3. Validate extracted IP with ipaddress.ip_address to reject header injection.

Storage:
- Rate limit counts and brute-force lockouts are stored in SQLite/PostgreSQL
  (RateLimitEvent & LoginLockout) to ensure state is shared across Uvicorn workers
  and survives service restarts.
"""

import time
import ipaddress
import uuid
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models_db import RateLimitEvent, LoginLockout


# In-memory fast caches (mirrored by database persistence)
_rate_limits: Dict[str, List[float]] = defaultdict(list)
_login_failures: Dict[str, List[float]] = defaultdict(list)
_lockouts: Dict[str, float] = {}


def _is_valid_ip(ip_str: str) -> bool:
    """Validate that a string is a legitimate IPv4 or IPv6 address."""
    try:
        # Strip port if present (e.g., "192.0.2.1:8080")
        if ":" in ip_str and not ip_str.startswith("[") and ip_str.count(":") == 1:
            ip_str = ip_str.split(":")[0]
        ipaddress.ip_address(ip_str.strip())
        return True
    except (ValueError, AttributeError):
        return False


def _clean_ip(ip_str: str) -> str:
    """Normalize and extract clean IP address string."""
    ip_str = ip_str.strip()
    if ":" in ip_str and not ip_str.startswith("[") and ip_str.count(":") == 1:
        ip_str = ip_str.split(":")[0]
    return ip_str


def get_client_ip(request: Request) -> str:
    """
    Extract verified client IP from trusted reverse proxy headers.
    Never trusts client-supplied leftmost X-Forwarded-For header.
    """
    headers = request.headers

    # 1. Check if request came through Vercel Edge Proxy
    # Vercel strips client-supplied x-vercel-forwarded-for and sets it to the socket IP.
    vercel_forwarded = headers.get("x-vercel-forwarded-for")
    if vercel_forwarded:
        first_ip = vercel_forwarded.split(",")[0].strip()
        if _is_valid_ip(first_ip):
            return _clean_ip(first_ip)

    # 2. Inspect X-Forwarded-For from the RIGHT (trusted proxy chain)
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            is_vercel = bool(headers.get("x-vercel-id") or headers.get("x-vercel-deployment-url"))
            if is_vercel and len(parts) >= 2:
                # Hop chain: [untrusted client spoof...], [Client IP (by Vercel)], [Vercel IP (by Render)]
                candidate = parts[-2]
            else:
                # Direct Render proxy (1 hop): [untrusted client spoof...], [Client IP (by Render)]
                candidate = parts[-1]

            if _is_valid_ip(candidate):
                return _clean_ip(candidate)

    # 3. Fallback to direct client socket host
    if request.client and request.client.host:
        candidate = request.client.host
        if _is_valid_ip(candidate):
            return _clean_ip(candidate)

    return "127.0.0.1"


def check_rate_limit(
    request: Request,
    limit: int = 120,
    window_seconds: int = 60,
    scope: str = "default",
    db: Optional[Session] = None,
) -> None:
    """
    Enforce sliding window IP rate limiting backed by persistent database storage.
    Raises HTTPException(429) if client exceeds limit in window.
    """
    ip = get_client_ip(request)
    key = f"{scope}:{ip}"
    now = time.time()
    cutoff = now - window_seconds

    # Database-backed counter for persistence and multi-worker sharing
    owns_session = False
    session = db
    if session is None:
        try:
            session = SessionLocal()
            owns_session = True
        except Exception:
            session = None

    if session:
        try:
            # Query recent event count in sliding window
            count = session.query(RateLimitEvent).filter(
                RateLimitEvent.key == key,
                RateLimitEvent.timestamp > cutoff
            ).count()

            if count >= limit:
                # Find oldest timestamp in current window to calculate Retry-After
                oldest_event = session.query(RateLimitEvent).filter(
                    RateLimitEvent.key == key,
                    RateLimitEvent.timestamp > cutoff
                ).order_by(RateLimitEvent.timestamp.asc()).first()
                retry_after = max(1, int(oldest_event.timestamp + window_seconds - now)) if oldest_event else 60
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {scope}: maximum {limit} requests per minute.",
                    headers={"Retry-After": str(retry_after)},
                )

            # Record this request event
            event = RateLimitEvent(
                id=str(uuid.uuid4()),
                key=key,
                scope=scope,
                timestamp=now,
            )
            session.add(event)
            session.commit()
        except HTTPException:
            raise
        except Exception:
            if session:
                session.rollback()
        finally:
            if owns_session and session:
                session.close()
    else:
        # Fallback to in-memory sliding window if DB is temporarily unreachable
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


def record_failed_login(
    identifier: str,
    max_attempts: int = 5,
    lockout_seconds: int = 900,
    db: Optional[Session] = None,
) -> None:
    """Record a failed login attempt and apply persistent lockout if threshold exceeded."""
    now = time.time()
    cutoff = now - 300  # 5-minute rolling window for attempts

    # Update in-memory cache
    valid_failures = [ts for ts in _login_failures[identifier] if ts > cutoff]
    valid_failures.append(now)
    _login_failures[identifier] = valid_failures
    if len(valid_failures) >= max_attempts:
        _lockouts[identifier] = now + lockout_seconds

    # Persist in database
    owns_session = False
    session = db
    if session is None:
        try:
            session = SessionLocal()
            owns_session = True
        except Exception:
            session = None

    if session:
        try:
            lockout_record = session.query(LoginLockout).filter(LoginLockout.key == identifier).first()
            if not lockout_record:
                lockout_record = LoginLockout(
                    key=identifier,
                    locked_until=0.0,
                    failure_count=1,
                    last_failure_at=now,
                )
                session.add(lockout_record)
            else:
                if lockout_record.last_failure_at < cutoff:
                    lockout_record.failure_count = 1
                else:
                    lockout_record.failure_count += 1
                lockout_record.last_failure_at = now

            if lockout_record.failure_count >= max_attempts:
                lockout_record.locked_until = now + lockout_seconds
                _lockouts[identifier] = lockout_record.locked_until

            session.commit()
        except Exception:
            session.rollback()
        finally:
            if owns_session:
                session.close()


def is_login_locked(identifier: str, db: Optional[Session] = None) -> Tuple[bool, int]:
    """Check if identifier (IP or email) is currently locked out in memory or database."""
    now = time.time()

    # Fast in-memory check
    lockout_until = _lockouts.get(identifier, 0)
    if lockout_until > now:
        return True, max(1, int(lockout_until - now))

    # Database check for persistent / multi-worker state
    owns_session = False
    session = db
    if session is None:
        try:
            session = SessionLocal()
            owns_session = True
        except Exception:
            session = None

    if session:
        try:
            record = session.query(LoginLockout).filter(LoginLockout.key == identifier).first()
            if record and record.locked_until > now:
                _lockouts[identifier] = record.locked_until
                return True, max(1, int(record.locked_until - now))
            elif record and record.locked_until <= now and record.failure_count >= 5:
                # Lockout expired, reset failure count
                record.failure_count = 0
                record.locked_until = 0.0
                session.commit()
        except Exception:
            if session:
                session.rollback()
        finally:
            if owns_session and session:
                session.close()

    if identifier in _lockouts:
        del _lockouts[identifier]
    return False, 0


def record_successful_login(identifier: str, db: Optional[Session] = None) -> None:
    """Reset failed login counters on successful authentication."""
    if identifier in _login_failures:
        del _login_failures[identifier]
    if identifier in _lockouts:
        del _lockouts[identifier]

    owns_session = False
    session = db
    if session is None:
        try:
            session = SessionLocal()
            owns_session = True
        except Exception:
            session = None

    if session:
        try:
            record = session.query(LoginLockout).filter(LoginLockout.key == identifier).first()
            if record:
                session.delete(record)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            if owns_session:
                session.close()


def reset_rate_limits_for_testing(db: Optional[Session] = None) -> None:
    """Utility to clear in-memory and database rate limits during test runs."""
    _rate_limits.clear()
    _login_failures.clear()
    _lockouts.clear()

    owns_session = False
    session = db
    if session is None:
        try:
            session = SessionLocal()
            owns_session = True
        except Exception:
            session = None

    if session:
        try:
            session.query(RateLimitEvent).delete()
            session.query(LoginLockout).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            if owns_session:
                session.close()
