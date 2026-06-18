"""
Security utilities for password hashing and data encryption

- Argon2id for password hashing
- Fernet (symmetric encryption) for sensitive data
"""

import os
import base64
import hashlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Argon2 password hasher
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password_hash: Stored password hash
        password: Plain text password to verify
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        ph.verify(password_hash, password)
        # Check if rehashing is needed (parameters changed)
        if ph.check_needs_rehash(password_hash):
            # In production, you'd update the hash in the database here
            pass
        return True
    except VerifyMismatchError:
        return False


def derive_key(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt (will be generated if not provided)
        
    Returns:
        Tuple of (key, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def generate_encryption_key() -> bytes:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Encryption key as bytes
    """
    return Fernet.generate_key()


def encrypt_data(data: str, key: bytes) -> str:
    """
    Encrypt data using Fernet symmetric encryption.
    
    Args:
        data: Plain text data to encrypt
        key: Encryption key (from generate_encryption_key or derive_key)
        
    Returns:
        Encrypted data as base64 string
    """
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str, key: bytes) -> str:
    """
    Decrypt data using Fernet symmetric encryption.
    
    Args:
        encrypted_data: Encrypted data as base64 string
        key: Encryption key used for encryption
        
    Returns:
        Decrypted plain text data
    """
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data.encode())
    return decrypted.decode()


# Global encryption key management
# In production, this should be stored securely (e.g., environment variable, key vault)
_ENCRYPTION_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "data", 
    ".encryption_key"
)


def get_or_create_encryption_key() -> bytes:
    """
    Get the global encryption key or create one if it doesn't exist.
    
    Returns:
        Encryption key as bytes
    """
    if os.path.exists(_ENCRYPTION_KEY_FILE):
        with open(_ENCRYPTION_KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = generate_encryption_key()
        os.makedirs(os.path.dirname(_ENCRYPTION_KEY_FILE), exist_ok=True)
        with open(_ENCRYPTION_KEY_FILE, "wb") as f:
            f.write(key)
        return key


def validate_xrpl_seed(seed: str) -> bool:
    """Cryptographically validate an XRPL seed by attempting wallet derivation."""
    try:
        from xrpl.wallet import Wallet
        Wallet.from_seed(seed)
        return True
    except Exception:
        return False


def generate_escrow_condition() -> tuple[str, str]:
    """Generate a PREIMAGE-SHA-256 crypto-condition pair for XRPL escrow.

    Returns (condition_hex, fulfillment_hex). Uses 32 random bytes as preimage.
    Manual DER encoding — no external cryptoconditions library needed.

    DER layout (fixed for 32-byte preimage):
      condition   = A0 25 80 20 <sha256(preimage)> 81 01 20  (39 bytes)
      fulfillment = A0 22 80 20 <preimage>                   (36 bytes: 4 header + 32 preimage)

    The fulfillment is the release key: whoever holds it can call EscrowFinish.
    In this platform, it travels inside the pacs.002 ACSC message (ISO 20022
    Payment Status Report), making the banking message the literal unlock key.
    Only XRP escrow is supported (classic XRPL EscrowCreate).
    """
    preimage    = os.urandom(32)
    condition   = bytes.fromhex("A0258020") + hashlib.sha256(preimage).digest() + bytes.fromhex("810120")
    fulfillment = bytes.fromhex("A0228020") + preimage
    return condition.hex().upper(), fulfillment.hex().upper()
