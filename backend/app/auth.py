"""
Authentication & Access Control Module
---------------------------------------
Implements bcrypt password hashing, JWT stateless access tokens, and
FastAPI dependencies for role-based and user-isolated access control.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend/.env is discovered even if executed from repo root, without overriding test monkeypatch
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)
load_dotenv(override=False)

from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models_db import User

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY or len(JWT_SECRET_KEY.strip()) < 32:
    raise RuntimeError(
        "FATAL: JWT_SECRET_KEY must be set in the environment and be at least 32 characters long. "
        "Hardcoded fallbacks have been removed for clinical security compliance."
    )
JWT_SECRET_KEY = JWT_SECRET_KEY.strip()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt with automatic salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode user claims into a signed JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: strictly authenticates user or raises 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def verify_patient_access(
    current_user: User,
    patient_id: str,
    db: Session,
) -> bool:
    """
    Verifies that current_user has legitimate access to patient_id's health records.
    Allowed IF:
      1. current_user is the patient themselves (current_user.id == patient_id), OR
      2. current_user is an admin (current_user.role == 'admin'), OR
      3. current_user is a clinician (current_user.role == 'clinician') AND the patient
         has explicitly granted active access via PatientClinicianGrant.
    Otherwise raises 403 Forbidden.
    """
    if current_user.id == patient_id or current_user.role == "admin":
        return True

    if current_user.role == "clinician":
        from .models_db import PatientClinicianGrant
        grant = (
            db.query(PatientClinicianGrant)
            .filter(
                PatientClinicianGrant.patient_id == patient_id,
                PatientClinicianGrant.clinician_id == current_user.id,
                PatientClinicianGrant.is_active == True,
            )
            .first()
        )
        if grant:
            return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: You do not have permission to access records for this patient.",
    )
