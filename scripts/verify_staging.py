"""
Staging End-to-End Verification Suite
======================================
Tests staging URLs against all production-readiness security and lifecycle guarantees:
1. Unauthenticated access to every health endpoint returns 401.
2. New registration strictly forces role='patient' (ignores client role injection).
3. Strict user isolation: User A cannot read User B's records (returns 403 Forbidden).
4. Emergency triage, SOS, and questions work 100% when logged out.
5. Cold-start recovery test: app gracefully responds after backend wake-up.
"""
import sys
import uuid
import time
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_staging_checks(base_url: str):
    base_url = base_url.rstrip("/")
    print(f"\n=======================================================")
    print(f"  RUNNING STAGING END-TO-END AUDIT ON: {base_url}")
    print(f"=======================================================\n")
    results = []

    # ---------------------------------------------------------
    # Check 1: Cold start / Health check recovery
    # ---------------------------------------------------------
    print("[1/5] Checking backend wake-up & health endpoint...")
    t0 = time.time()
    try:
        health_resp = requests.get(f"{base_url}/health", timeout=60)
        elapsed = round(time.time() - t0, 2)
        if health_resp.status_code == 200:
            print(f"  ✓ Backend awake and healthy in {elapsed}s (status={health_resp.status_code})")
            results.append(("Cold-Start Recovery & Health", True, f"Awake in {elapsed}s"))
        else:
            print(f"  ✗ Health check failed with status {health_resp.status_code}")
            results.append(("Cold-Start Recovery & Health", False, f"Status {health_resp.status_code}"))
    except Exception as e:
        print(f"  ✗ Connection error waking backend: {e}")
        results.append(("Cold-Start Recovery & Health", False, str(e)))
        return results

    # ---------------------------------------------------------
    # Check 2: Unauthenticated access to every health endpoint returns 401
    # ---------------------------------------------------------
    print("\n[2/5] Testing unauthenticated health endpoint access (Must return 401)...")
    protected_endpoints = [
        ("GET", "/api/v1/vitals/history"),
        ("POST", "/api/v1/vitals"),
        ("GET", "/api/v1/user/profile"),
        ("GET", "/api/v1/ecg/history"),
        ("POST", "/api/v1/ecg/upload"),
        ("GET", "/api/v1/emergency/history"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/user/access-log"),
        ("GET", "/api/v1/consent"),
    ]
    unauth_passed = True
    for method, path in protected_endpoints:
        url = f"{base_url}{path}"
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json={}, timeout=10)
        if r.status_code != 401:
            print(f"  ✗ Security Failure: {method} {path} returned {r.status_code} instead of 401 Unauthorized")
            unauth_passed = False
        else:
            print(f"  ✓ Protected: {method} {path} -> 401 Unauthorized")
    results.append(("Unauthenticated Health Endpoints -> 401", unauth_passed, f"{len(protected_endpoints)} endpoints tested"))

    # ---------------------------------------------------------
    # Check 3: New registration strictly defaults to patient (role injection immunity)
    # ---------------------------------------------------------
    print("\n[3/5] Testing registration role hardening...")
    u1_email = f"patient1_{uuid.uuid4().hex[:8]}@staging-audit.org"
    reg1 = requests.post(
        f"{base_url}/api/v1/auth/register",
        json={"email": u1_email, "password": "Password123!", "role": "clinician"},  # Attack attempt
        timeout=15,
    )
    if reg1.status_code in (200, 201):
        data1 = reg1.json()
        token1 = data1["access_token"]
        user1 = data1["user"]
        if user1.get("role") == "patient":
            print(f"  ✓ Role injection ignored: requested 'clinician', granted '{user1.get('role')}'")
            results.append(("Registration Role Hardening", True, f"role={user1.get('role')}"))
        else:
            print(f"  ✗ Vulnerability: registration assigned role='{user1.get('role')}'")
            results.append(("Registration Role Hardening", False, f"role={user1.get('role')}"))
    else:
        print(f"  ✗ Registration failed: {reg1.status_code} {reg1.text}")
        results.append(("Registration Role Hardening", False, f"HTTP {reg1.status_code}"))
        return results

    # ---------------------------------------------------------
    # Check 4: Strict User Isolation (User A cannot read User B)
    # ---------------------------------------------------------
    print("\n[4/5] Testing cross-tenant user isolation (User A vs User B)...")
    u2_email = f"patient2_{uuid.uuid4().hex[:8]}@staging-audit.org"
    reg2 = requests.post(
        f"{base_url}/api/v1/auth/register",
        json={"email": u2_email, "password": "Password123!"},
        timeout=15,
    )
    token2 = reg2.json()["access_token"]
    user2 = reg2.json()["user"]

    # Log vitals under User B
    vitals_b = requests.post(
        f"{base_url}/api/v1/vitals",
        json={
            "bp_sys": 125,
            "bp_dia": 82,
            "hr": 74,
            "weight": 70.0,
            "spo2": 98.0,
        },
        headers={"Authorization": f"Bearer {token2}"},
        timeout=15,
    )

    # User A attempts to read User B's records
    probe_vitals = requests.get(
        f"{base_url}/api/v1/vitals/history?user_id={user2['id']}",
        headers={"Authorization": f"Bearer {token1}"},
        timeout=10,
    )
    probe_triage = requests.get(
        f"{base_url}/api/v1/emergency/history?user_id={user2['id']}",
        headers={"Authorization": f"Bearer {token1}"},
        timeout=10,
    )

    isolation_ok = probe_vitals.status_code == 403 and probe_triage.status_code == 403
    if isolation_ok:
        print(f"  ✓ User A blocked from reading User B vitals -> 403 Forbidden")
        print(f"  ✓ User A blocked from reading User B triage -> 403 Forbidden")
        results.append(("User Isolation (A cannot read B)", True, "Both returned 403 Forbidden"))
    else:
        print(f"  ✗ Isolation Breach: vitals returned {probe_vitals.status_code}, triage returned {probe_triage.status_code}")
        results.append(("User Isolation (A cannot read B)", False, f"vitals={probe_vitals.status_code}, triage={probe_triage.status_code}"))

    # ---------------------------------------------------------
    # Check 5: Emergency Triage works when logged out
    # ---------------------------------------------------------
    print("\n[5/5] Testing unauthenticated emergency access (Life-safety)...")
    triage_req = requests.post(
        f"{base_url}/api/v1/emergency/triage",
        json={"symptoms": [True, True, False, False, False, True, False, False, False, False, False, False]},
        timeout=15,
    )
    sos_req = requests.post(f"{base_url}/api/v1/emergency/sos", json={}, timeout=15)

    emergency_ok = False
    if triage_req.status_code == 200 and sos_req.status_code == 200:
        td = triage_req.json()
        sd = sos_req.json()
        if td.get("severity") == "emergency" and len(td.get("hospitals", [])) > 0:
            print(f"  ✓ Emergency triage returned 200 OK without token: severity='{td['severity']}', {len(td['hospitals'])} hospitals returned")
            print(f"  ✓ Emergency SOS returned 200 OK without token: {len(sd.get('emergency_hotlines', []))} emergency helplines returned")
            emergency_ok = True
            results.append(("Emergency Public Access", True, "200 OK, full routing without token"))
    if not emergency_ok:
        print(f"  ✗ Emergency access failed: triage={triage_req.status_code}, sos={sos_req.status_code}")
        results.append(("Emergency Public Access", False, f"triage={triage_req.status_code}, sos={sos_req.status_code}"))

    # ---------------------------------------------------------
    # Summary Table
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("                STAGING AUDIT SUMMARY                  ")
    print("=======================================================")
    all_passed = True
    for name, passed, detail in results:
        status_sym = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False
        print(f"  {status_sym:<8} | {name:<38} | {detail}")
    print("=======================================================\n")
    return all_passed

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    success = run_staging_checks(target)
    sys.exit(0 if success else 1)
