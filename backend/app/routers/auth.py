"""
Authentication & User Account Router
------------------------------------
Provides secure user registration, login, and profile access with JWT tokens.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegisterIn, db: Session = Depends(get_db)):
    """Register a new user account with hashed password and return access token."""
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
def login_user(payload: UserLoginIn, db: Session = Depends(get_db)):
    """Authenticate email and password, returning a signed JWT access token."""
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
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


@router.post("/grant-clinician/{clinician_id}", status_code=status.HTTP_200_OK)
def grant_clinician_access(
    clinician_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patient explicitly grants a verified clinician access to their health records."""
    from ..models_db import PatientClinicianGrant

    clinician = db.query(User).filter(User.id == clinician_id, User.role == "clinician").first()
    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician not found.",
        )

    grant = (
        db.query(PatientClinicianGrant)
        .filter(
            PatientClinicianGrant.patient_id == current_user.id,
            PatientClinicianGrant.clinician_id == clinician_id,
        )
        .first()
    )
    if grant:
        grant.is_active = True
    else:
        grant = PatientClinicianGrant(
            patient_id=current_user.id,
            clinician_id=clinician_id,
            is_active=True,
        )
        db.add(grant)

    db.commit()
    return {"status": "granted", "patient_id": current_user.id, "clinician_id": clinician_id}


@router.delete("/grant-clinician/{clinician_id}", status_code=status.HTTP_200_OK)
def revoke_clinician_access(
    clinician_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patient explicitly revokes a clinician's access to their health records."""
    from ..models_db import PatientClinicianGrant

    grant = (
        db.query(PatientClinicianGrant)
        .filter(
            PatientClinicianGrant.patient_id == current_user.id,
            PatientClinicianGrant.clinician_id == clinician_id,
        )
        .first()
    )
    if grant:
        grant.is_active = False
        db.commit()

    return {"status": "revoked", "patient_id": current_user.id, "clinician_id": clinician_id}
