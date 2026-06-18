"""Device API key authentication for the signing backend.

Each authorized desktop installation has a random 32-byte token (issued by
issue_device_key.py). The token is stored as a SHA-256 hex digest in the DB
— SHA-256 is appropriate here because the key is 32 random bytes (high
entropy), unlike user passwords which require Argon2.
"""

import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Device

_bearer = HTTPBearer()


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def require_device(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Device:
    """FastAPI dependency — returns the authenticated Device or raises 401."""
    key_hash = _hash_key(credentials.credentials)
    device = db.query(Device).filter_by(api_key_hash=key_hash, is_active=True).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device API key inválida o inactiva.",
        )
    return device
