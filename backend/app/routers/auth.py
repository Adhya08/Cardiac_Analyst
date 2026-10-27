"""
Authentication & User Account Router
------------------------------------
Provides secure user registration, login, and profile access with JWT tokens.
"""
import re
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import User
from ..schemas import UserRegisterIn, UserLoginIn, TokenOut, UserProfileOut, UserProfileIn
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from ..rate_limiter import (
    get_client_ip,
    check_rate_limit,
    record_failed_login,
    is_login_locked,
    record_successful_login,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def check_password_complexity(password: str) -> None:
    """Enforce minimum 8 chars, uppercase, lowercase, number, and special symbol."""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter (A-Z).",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one lowercase letter (a-z).",
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one numeric digit (0-9).",
        )
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one special character (!@#$%^&*...).",
        )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegisterIn, db: Session = Depends(get_db)):
    """Register a new user account with hashed password and return access token."""
    check_password_complexity(payload.password)
    normalized_email = payload.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    hashed_pw = hash_password(payload.password)
    # Security Rule: Public self-registration ALWAYS creates a patient.
    # Client-supplied role is strictly ignored to prevent privilege escalation.
    user = User(
        email=normalized_email,
        hashed_password=hashed_pw,
        role="patient",
        name=payload.name or "User",
        age=payload.age,
        sex=payload.sex,
        is_smoker=payload.is_smoker,
        is_diabetic=payload.is_diabetic,
        has_family_history=payload.has_family_history,
        height_cm=payload.height_cm,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )
    return TokenOut(access_token=token, token_type="bearer", user=UserProfileOut.model_validate(user))


@router.post("/admin/create-clinician", response_model=UserProfileOut, status_code=status.HTTP_201_CREATED)
def admin_create_clinician(
    payload: UserRegisterIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to provision verified clinician accounts."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can provision clinician accounts.",
        )

    normalized_email = payload.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    check_password_complexity(payload.password)
    hashed_pw = hash_password(payload.password)
    clinician = User(
        email=normalized_email,
        hashed_password=hashed_pw,
        role="clinician",
        name=payload.name or "Clinician",
        age=payload.age,
        sex=payload.sex,
        is_smoker=payload.is_smoker,
        is_diabetic=payload.is_diabetic,
        has_family_history=payload.has_family_history,
        height_cm=payload.height_cm,
        is_active=True,
    )
    db.add(clinician)
    db.commit()
    db.refresh(clinician)
    return UserProfileOut.model_validate(clinician)


@router.post("/login", response_model=TokenOut)
def login_user(payload: UserLoginIn, request: Request, db: Session = Depends(get_db)):
    """Authenticate email and password with rate limiting and brute-force lockout."""
    check_rate_limit(request, limit=20, window_seconds=60, scope="auth_login", db=db)

    normalized_email = payload.email.strip().lower()
    client_ip = get_client_ip(request)

    # 1. Check IP lockout
    ip_locked, ip_rem = is_login_locked(f"ip:{client_ip}", db=db)
    if ip_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts from this network. Temporarily locked for {ip_rem} seconds.",
            headers={"Retry-After": str(ip_rem)},
        )

    # 2. Check Account lockout
    email_locked, email_rem = is_login_locked(f"email:{normalized_email}", db=db)
    if email_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to repeated failed login attempts. Please try again in {email_rem} seconds.",
            headers={"Retry-After": str(email_rem)},
        )

    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        record_failed_login(f"ip:{client_ip}", max_attempts=5, lockout_seconds=900, db=db)
        record_failed_login(f"email:{normalized_email}", max_attempts=5, lockout_seconds=900, db=db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    # Authentication successful: clear lockout tracking
    record_successful_login(f"ip:{client_ip}", db=db)
    record_successful_login(f"email:{normalized_email}", db=db)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )
    return TokenOut(access_token=token, token_type="bearer", user=UserProfileOut.model_validate(user))


@router.get("/me", response_model=UserProfileOut)
def get_authenticated_profile(current_user: User = Depends(get_current_user)):
    """Retrieve profile and demographics for the currently authenticated user."""
    return UserProfileOut.model_validate(current_user)


@router.put("/me", response_model=UserProfileOut)
def update_authenticated_profile(
    payload: UserProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile and clinical demographics for the currently authenticated user."""
    allowed_fields = [
        "name", "age", "sex", "is_smoker", "is_diabetic",
        "has_family_history", "height_cm"
    ]
    for key, value in payload.model_dump().items():
        if key in allowed_fields and hasattr(current_user, key):
            setattr(current_user, key, value)

    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return UserProfileOut.model_validate(current_user)


class ClinicianGrantIn(BaseModel):
    email: Optional[str] = Field(None, description="Clinician email address")
    invite_code: Optional[str] = Field(None, description="Clinician invite code")


def _find_clinician(
    db: Session,
    email: Optional[str] = None,
    invite_code: Optional[str] = None,
    identifier: Optional[str] = None,
) -> Optional[User]:
    """
    Safely resolves a verified, active clinician by invite_code, email, or identifier.
    Returns None if not found or if the account is not a clinician.
    """
    query = db.query(User).filter(User.role == "clinician", User.is_active == True)
    if invite_code:
        return query.filter(User.invite_code == invite_code.strip()).first()
    if email:
        return query.filter(User.email == email.strip().lower()).first()
    if identifier:
        target = identifier.strip()
        # Look up by invite_code, email, or internal id
        return query.filter(
            (User.id == target) |
            (User.email == target.lower()) |
            (User.invite_code == target)
        ).first()
    return None


@router.post("/grant-clinician", status_code=status.HTTP_200_OK)
def grant_clinician_by_email_or_code(
    payload: ClinicianGrantIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Patient explicitly grants a verified clinician access to their health records
    using the clinician's email or invite code (never raw database IDs).
    Anti-enumeration: Returns generic 400 for non-existent users or non-clinicians.
    """
    from ..models_db import PatientClinicianGrant

    if not payload.email and not payload.invite_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to grant access. Invalid clinician email or invite code.",
        )

    clinician = _find_clinician(db, email=payload.email, invite_code=payload.invite_code)
    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to grant access. Invalid clinician email or invite code.",
        )

    grant = (
        db.query(PatientClinicianGrant)
        .filter(
            PatientClinicianGrant.patient_id == current_user.id,
            PatientClinicianGrant.clinician_id == clinician.id,
        )
        .first()
    )
    if grant:
        grant.is_active = True
    else:
        grant = PatientClinicianGrant(
            id=str(uuid.uuid4()),
            patient_id=current_user.id,
            clinician_id=clinician.id,
            is_active=True,
        )
        db.add(grant)

    db.commit()
    return {"status": "granted", "message": "Clinician access granted successfully."}


@router.post("/revoke-clinician", status_code=status.HTTP_200_OK)
def revoke_clinician_by_email_or_code(
    payload: ClinicianGrantIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Patient explicitly revokes a clinician's access using email or invite code.
    Idempotent and anti-enumeration: always returns status: revoked.
    """
    from ..models_db import PatientClinicianGrant

    clinician = _find_clinician(db, email=payload.email, invite_code=payload.invite_code)
    if clinician:
        grant = (
            db.query(PatientClinicianGrant)
            .filter(
                PatientClinicianGrant.patient_id == current_user.id,
                PatientClinicianGrant.clinician_id == clinician.id,
            )
            .first()
        )
        if grant:
            grant.is_active = False
            db.commit()

    return {"status": "revoked", "message": "Clinician access revoked successfully."}


@router.post("/grant-clinician/{clinician_id}", status_code=status.HTTP_200_OK)
def grant_clinician_access(
    clinician_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy / identifier grant endpoint with anti-enumeration protection."""
    from ..models_db import PatientClinicianGrant

    clinician = _find_clinician(db, identifier=clinician_id)
    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to grant access. Invalid clinician email or invite code.",
        )

    grant = (
        db.query(PatientClinicianGrant)
        .filter(
            PatientClinicianGrant.patient_id == current_user.id,
            PatientClinicianGrant.clinician_id == clinician.id,
        )
        .first()
    )
    if grant:
        grant.is_active = True
    else:
        grant = PatientClinicianGrant(
            id=str(uuid.uuid4()),
            patient_id=current_user.id,
            clinician_id=clinician.id,
            is_active=True,
        )
        db.add(grant)

    db.commit()
    return {"status": "granted", "patient_id": current_user.id, "clinician_id": clinician.id}


@router.delete("/grant-clinician/{clinician_id}", status_code=status.HTTP_200_OK)
def revoke_clinician_access(
    clinician_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy / identifier revoke endpoint."""
    from ..models_db import PatientClinicianGrant

    clinician = _find_clinician(db, identifier=clinician_id)
    if clinician:
        grant = (
            db.query(PatientClinicianGrant)
            .filter(
                PatientClinicianGrant.patient_id == current_user.id,
                PatientClinicianGrant.clinician_id == clinician.id,
            )
            .first()
        )
        if grant:
            grant.is_active = False
            db.commit()

    return {"status": "revoked", "patient_id": current_user.id, "clinician_id": clinician_id}


@router.get("/my-invite-code", status_code=status.HTTP_200_OK)
def get_my_invite_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve clinician's unique invite code. Clinician-only."""
    if current_user.role != "clinician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clinicians have invite codes.",
        )
    if not current_user.invite_code:
        current_user.invite_code = f"DR-{uuid.uuid4().hex[:6].upper()}"
        db.commit()
    return {"invite_code": current_user.invite_code}
