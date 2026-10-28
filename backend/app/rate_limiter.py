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

import os
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


def _is_trusted_proxy(ip_str: str) -> bool:
    """Check if an IP address matches any trusted proxy IP or CIDR range."""
    trusted_raw = os.getenv("TRUSTED_PROXY_IPS", "")
    if not trusted_raw:
        return False
    trusted_list = [t.strip() for t in trusted_raw.split(",") if t.strip()]
    clean = _clean_ip(ip_str)
    try:
        candidate_ip = ipaddress.ip_address(clean)
        for trusted in trusted_list:
            if "/" in trusted:
                if candidate_ip in ipaddress.ip_network(trusted, strict=False):
                    return True
            else:
                if candidate_ip == ipaddress.ip_address(trusted):
                    return True
    except (ValueError, AttributeError):
        pass
    return False


RENDER_EDGE_NETWORKS = [
    ipaddress.ip_network("173.245.48.0/20"),
    ipaddress.ip_network("103.21.244.0/22"),
    ipaddress.ip_network("103.22.200.0/22"),
    ipaddress.ip_network("103.31.4.0/22"),
    ipaddress.ip_network("141.101.64.0/18"),
    ipaddress.ip_network("108.162.192.0/18"),
    ipaddress.ip_network("190.93.240.0/20"),
    ipaddress.ip_network("188.114.96.0/20"),
    ipaddress.ip_network("197.234.240.0/22"),
    ipaddress.ip_network("198.41.128.0/17"),
    ipaddress.ip_network("162.158.0.0/15"),
    ipaddress.ip_network("104.16.0.0/13"),
    ipaddress.ip_network("104.24.0.0/14"),
    ipaddress.ip_network("172.64.0.0/13"),
    ipaddress.ip_network("131.0.72.0/22"),
]


RENDER_INTERNAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


def _is_render_infra_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP belongs to Render's internal container mesh or edge reverse proxy."""
    for net in RENDER_INTERNAL_NETWORKS:
        if ip_obj in net:
            return True
    for net in RENDER_EDGE_NETWORKS:
        if ip_obj in net:
            return True
    return False


def get_client_ip(request: Request) -> str:
    """
    Extract verified client IP from trusted reverse proxy headers.
    1. On Render, X-Forwarded-For contains:
       [untrusted client spoof...], [Connecting Client IP], [Render Cloudflare Edge], [Render Internal Mesh]
    2. We strip Render internal (RFC 1918) and edge proxy infrastructure hops from the right.
    3. The rightmost non-infrastructure IP is the Connecting Peer.
    4. If Connecting Peer matches TRUSTED_PROXY_IPS (e.g., Vercel), we trust X-Vercel-Forwarded-For.
    5. If Connecting Peer does NOT match TRUSTED_PROXY_IPS, it IS the real client IP.
       Any forged X-Vercel-Forwarded-For or spoofed X-Forwarded-For is strictly discarded.
    """
    headers = request.headers
    forwarded = headers.get("x-forwarded-for")

    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]

        # Walk from right to left, stripping internal infrastructure and edge proxy hops
        non_infra_hops = []
        for p in reversed(parts):
            clean = _clean_ip(p)
            try:
                ip_obj = ipaddress.ip_address(clean)
                if not _is_render_infra_ip(ip_obj):
                    non_infra_hops.append(clean)
            except (ValueError, AttributeError):
                continue

        if non_infra_hops:
            connecting_peer = non_infra_hops[0]

            # 1. Check if request came through a verified trusted proxy (e.g. Vercel)
            if _is_trusted_proxy(connecting_peer):
                vercel_forwarded = headers.get("x-vercel-forwarded-for")
                if vercel_forwarded:
                    first_ip = vercel_forwarded.split(",")[0].strip()
                    if _is_valid_ip(first_ip):
                        return _clean_ip(first_ip)
                if len(non_infra_hops) >= 2 and _is_valid_ip(non_infra_hops[1]):
                    return _clean_ip(non_infra_hops[1])

            # 2. Direct connection from client to Render:
            return connecting_peer

    # Fallback to direct client socket host
    if request.client and request.client.host:
        candidate = _clean_ip(request.client.host)
        if _is_valid_ip(candidate):
            return candidate

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
