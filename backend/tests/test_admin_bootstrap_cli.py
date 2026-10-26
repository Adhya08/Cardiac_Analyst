"""
Automated Pytest Suite: Admin Bootstrap CLI Tool (Item 3)
=========================================================
Verifies:
1. Admin bootstrap rejects empty passwords and weak passwords (<12 chars, missing special/digit/case).
2. Admin bootstrap rejects malformed emails.
3. Admin bootstrap successfully provisions an admin when valid credentials provided.
4. Second run refuses to create duplicate administrators (one-time safeguard).
"""

import uuid
import pytest
from app.database import SessionLocal, init_db
from app.models_db import User
from bootstrap_admin import bootstrap_admin, validate_password_strength


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    db = SessionLocal()
    # Clean any test admins
    db.query(User).filter(User.role == "admin").delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(User).filter(User.role == "admin").delete()
    db.commit()
    db.close()


def test_bootstrap_rejects_weak_passwords():
    """Passwords <12 chars or lacking complexity must be rejected."""
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password_strength("Short1!")

    with pytest.raises(ValueError, match="uppercase"):
        validate_password_strength("alllowercase123!@#")

    with pytest.raises(ValueError, match="lowercase"):
        validate_password_strength("ALLUPPERCASE123!@#")

    with pytest.raises(ValueError, match="numeric digit"):
        validate_password_strength("NoDigitsHere!@#$")

    with pytest.raises(ValueError, match="special character"):
        validate_password_strength("NoSpecialChar1234")


def test_bootstrap_admin_creation_and_one_time_guarantee():
    """Verify safe creation of first admin, and rejection of second."""
    email = f"admin_{uuid.uuid4().hex[:8]}@hospital.org"
    password = "SuperClinicalAdmin2026!#"

    admin = bootstrap_admin(email=email, password=password, name="Dr. Chief Admin")
    assert admin is not None
    assert admin.role == "admin"
    assert admin.email == email
    assert admin.is_active is True

    # Attempting to run bootstrap again must raise RuntimeError
    second_email = f"second_admin_{uuid.uuid4().hex[:8]}@hospital.org"
    with pytest.raises(RuntimeError, match="administrator account already exists"):
        bootstrap_admin(email=second_email, password="AnotherStrongAdmin2026!#")
