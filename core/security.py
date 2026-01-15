"""
Security utilities for password hashing and data encryption

- Argon2id for password hashing
- Fernet (symmetric encryption) for sensitive data
"""

import os
import base64
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
    """
    Basic validation for XRPL seed format.
    
    Args:
        seed: XRPL seed string
        
    Returns:
        True if format appears valid
    """
    # XRPL seeds start with 's' and are typically 29 characters
    # This is a basic check; actual validation happens in xrpl_client
    return seed.startswith('s') and len(seed) >= 25
