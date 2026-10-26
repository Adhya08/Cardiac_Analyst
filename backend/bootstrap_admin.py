"""
Cardiac Analyst — Admin Bootstrap CLI Tool
===========================================
Safe, one-time out-of-band CLI tool to provision the initial system administrator.
Not exposed via HTTP.
Reads email and password from environment variables (BOOTSTRAP_ADMIN_EMAIL,
BOOTSTRAP_ADMIN_PASSWORD) or prompts interactively.
Zero default credentials.
"""

import os
import sys
import uuid
import re
import getpass
from datetime import datetime

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal, init_db
from app.models_db import User
from app.auth import hash_password


EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def validate_password_strength(password: str) -> None:
    """Enforce strict administrative password strength rules."""
    if len(password) < 12:
        raise ValueError("Admin password must be at least 12 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Admin password must contain at least one uppercase letter (A-Z).")
    if not re.search(r"[a-z]", password):
        raise ValueError("Admin password must contain at least one lowercase letter (a-z).")
    if not re.search(r"[0-9]", password):
        raise ValueError("Admin password must contain at least one numeric digit (0-9).")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Admin password must contain at least one special character (!@#$%^&*...).")


def bootstrap_admin(email: str = None, password: str = None, name: str = "System Administrator") -> User:
    """Bootstrap an initial administrator account."""
    init_db()
    db = SessionLocal()
    try:
        # 1. Resolve email
        admin_email = email or os.getenv("BOOTSTRAP_ADMIN_EMAIL")
        if not admin_email and sys.stdin.isatty():
            admin_email = input("Enter admin email: ").strip()

        if not admin_email or not re.match(EMAIL_REGEX, admin_email):
            raise ValueError(f"Invalid or missing admin email: '{admin_email}'.")

        # 2. Check if admin already exists
        existing_admin = db.query(User).filter(User.role == "admin").first()
        if existing_admin:
            raise RuntimeError(
                f"An administrator account already exists ({existing_admin.email}). "
                "For security reasons, bootstrap_admin only provisions the initial administrator."
            )

        existing_user = db.query(User).filter(User.email == admin_email).first()
        if existing_user:
            raise RuntimeError(f"User with email '{admin_email}' already exists.")

        # 3. Resolve password
        admin_password = password or os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        if not admin_password and sys.stdin.isatty():
            admin_password = getpass.getpass("Enter strong admin password (min 12 chars): ")

        if not admin_password:
            raise ValueError("Admin password cannot be empty. No default credentials permitted.")

        validate_password_strength(admin_password)

        # 4. Hash and persist
        hashed = hash_password(admin_password)
        new_admin = User(
            id=str(uuid.uuid4()),
            email=admin_email,
            hashed_password=hashed,
            name=name,
            role="admin",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        return new_admin
    finally:
        db.close()


def main():
    try:
        admin = bootstrap_admin()
        print(f"\n[SUCCESS] Administrator account provisioned successfully.")
        print(f"  User ID : {admin.id}")
        print(f"  Email   : {admin.email}")
        print(f"  Role    : {admin.role}")
        print(f"  Active  : {admin.is_active}\n")
    except Exception as exc:
        print(f"\n[ERROR] Admin bootstrap failed: {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
