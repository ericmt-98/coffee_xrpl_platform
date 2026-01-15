"""
Database models for the Coffee XRPL Payment Platform

Tables:
- User: System operators (admin and payment app users)
- Producer: Coffee producers receiving payments
- Payment: XRPL payment records
- Delivery: Coffee delivery records (weight, price)
- IsoMessage: ISO 20022 XML messages
- AuditLog: System audit trail
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, 
    ForeignKey, Enum as SQLEnum, Boolean
)
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    """User roles in the system"""
    ADMIN = "admin"
    OPERATOR = "operator"


class PaymentStatus(enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    """System users (admin and operators)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)  # Generated ID
    password_hash = Column(String(255), nullable=True)  # Nullable for first login
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.OPERATOR)
    full_name = Column(String(200), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    xrpl_address = Column(String(100), nullable=True)  # For operators
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    payments = relationship("Payment", back_populates="operator")
    audit_logs = relationship("AuditLog", back_populates="user")


class Producer(Base):
    """Coffee producers"""
    __tablename__ = "producers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    xrpl_address = Column(String(100), nullable=False, unique=True)
    id_image_path = Column(String(500), nullable=True)  # Path to ID image
    contact_info = Column(Text, nullable=True)
    rfc_encrypted = Column(String(500), nullable=True)  # Encrypted RFC
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    payments = relationship("Payment", back_populates="producer")


class Payment(Base):
    """XRPL payment records"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    uetr = Column(String(36), unique=True, nullable=False)  # UUID v4
    xrpl_tx_hash = Column(String(100), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)  # XRP, USDC, RLUSD, MXN
    amount_mxn = Column(Float, nullable=True)  # Original amount in MXN
    producer_id = Column(Integer, ForeignKey("producers.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    notes = Column(Text, nullable=True)
    
    # Relationships
    producer = relationship("Producer", back_populates="payments")
    operator = relationship("User", back_populates="payments")
    delivery = relationship("Delivery", back_populates="payment", uselist=False)
    iso_messages = relationship("IsoMessage", back_populates="payment")


class Delivery(Base):
    """Coffee delivery records"""
    __tablename__ = "deliveries"
    
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, unique=True)
    weight_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    total_mxn = Column(Float, nullable=False)
    delivery_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    
    # Relationships
    payment = relationship("Payment", back_populates="delivery")


class MessageType(enum.Enum):
    """ISO 20022 message types"""
    PACS_008 = "pacs.008"
    CAMT_053 = "camt.053"
    CAMT_054 = "camt.054"


class IsoMessage(Base):
    """ISO 20022 XML messages"""
    __tablename__ = "iso_messages"
    
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    message_type = Column(SQLEnum(MessageType), nullable=False)
    xml_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = relationship("Payment", back_populates="iso_messages")


class AuditLog(Base):
    """System audit trail"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
