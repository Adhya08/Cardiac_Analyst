"""
User Consent Router
--------------------
POST /api/v1/consent/grant  — Grant server-side consent (e.g., third_party_ai)
POST /api/v1/consent/revoke — Revoke server-side consent
GET  /api/v1/consent        — Check active consent status
"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import User, UserConsent
from ..auth import get_current_user
from ..rate_limiter import get_client_ip

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


class ConsentGrantIn(BaseModel):
    consent_type: str = Field(default="third_party_ai", description="Consent identifier")
    policy_version: str = Field(default="v1.0", description="Privacy policy version agreed to")


class ConsentRevokeIn(BaseModel):
    consent_type: str = Field(default="third_party_ai", description="Consent identifier to revoke")


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    consent_type: str
    granted: bool
    policy_version: str
    timestamp: datetime


@router.post("/grant", response_model=ConsentOut)
def grant_consent(
    payload: ConsentGrantIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly grant server-side consent for a specific processing category."""
    ip = get_client_ip(request)
    now = datetime.utcnow()
    record = UserConsent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        consent_type=payload.consent_type.strip().lower(),
        granted=True,
        policy_version=payload.policy_version,
        ip_address=ip,
        timestamp=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/revoke", response_model=ConsentOut)
def revoke_consent(
    payload: ConsentRevokeIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly revoke server-side consent. Immediately halts third-party AI processing."""
    ip = get_client_ip(request)
    now = datetime.utcnow()
    record = UserConsent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        consent_type=payload.consent_type.strip().lower(),
        granted=False,
        policy_version="revoked",
        ip_address=ip,
        timestamp=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=ConsentOut)
def get_consent_status(
    consent_type: str = Query(default="third_party_ai"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch current active server-side consent status for the user."""
    norm_type = consent_type.strip().lower()
    latest = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == current_user.id, UserConsent.consent_type == norm_type)
        .order_by(UserConsent.timestamp.desc())
        .first()
    )
    if not latest:
        # Default ungranted consent record
        return ConsentOut(
            user_id=current_user.id,
            consent_type=norm_type,
            granted=False,
            policy_version="none",
            timestamp=datetime.utcnow(),
        )
    return latest
