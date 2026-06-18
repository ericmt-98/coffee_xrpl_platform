"""Backend ORM models: Device, OperatorToken, SignRequestLog."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from backend.database import Base


class Device(Base):
    """Authorized desktop installations. Each holds a hashed device API key."""
    __tablename__ = "devices"

    id               = Column(Integer, primary_key=True)
    api_key_hash     = Column(String(64), unique=True, nullable=False)  # SHA-256 hex
    operator_username = Column(String(100), nullable=False)
    label            = Column(String(200), nullable=True)   # human name for this install
    is_active        = Column(Boolean, default=True, nullable=False)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OperatorToken(Base):
    """Xaman user_token per operator — enables push notifications after first sign-in."""
    __tablename__ = "operator_tokens"

    id                = Column(Integer, primary_key=True)
    operator_username  = Column(String(100), unique=True, nullable=False)
    xrpl_address      = Column(String(100), nullable=True)
    user_token        = Column(String(200), nullable=False)
    updated_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SignRequestLog(Base):
    """Audit trail for every sign request the backend creates."""
    __tablename__ = "sign_request_logs"

    id                 = Column(Integer, primary_key=True)
    uuid               = Column(String(36), unique=True, nullable=False)
    operator_username   = Column(String(100), nullable=False)
    identifier         = Column(String(200), nullable=True)   # UETR or custom id
    kind               = Column(String(50),  nullable=True)   # signin/payment/escrow_create/...
    status             = Column(String(20),  default="pending")  # pending/signed/cancelled/expired/failed
    txid               = Column(String(100), nullable=True)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at        = Column(DateTime, nullable=True)
    notes              = Column(Text, nullable=True)
