"""Encrypted key/value configuration store backed by the local SQLite DB.

Keys: backend_url, device_api_key, use_xaman ("1" / "0").
Values are Fernet-encrypted at rest using the same key as the rest of the app.
"""

from core.database import get_session, close_session
from core.models import AppConfig
from core.security import encrypt_data, decrypt_data, get_or_create_encryption_key


def set_config(key: str, value: str) -> None:
    """Encrypt and persist a config value. Creates or updates the row."""
    enc_key = get_or_create_encryption_key()
    encrypted = encrypt_data(value, enc_key)
    session = get_session()
    try:
        row = session.query(AppConfig).filter_by(key=key).first()
        if row:
            row.value = encrypted
        else:
            session.add(AppConfig(key=key, value=encrypted))
        session.commit()
    finally:
        close_session()


def get_config(key: str, default: str = "") -> str:
    """Retrieve and decrypt a config value. Returns default if not found."""
    session = get_session()
    try:
        row = session.query(AppConfig).filter_by(key=key).first()
        if not row or not row.value:
            return default
        enc_key = get_or_create_encryption_key()
        return decrypt_data(row.value, enc_key)
    except Exception:
        return default
    finally:
        close_session()


def is_xaman_enabled() -> bool:
    return get_config("use_xaman", "0") == "1"
