"""
Issue a new device API key for an authorized desktop installation.

Usage:
    python -m backend.issue_device_key --username <operator_username> --label "Oficina Chiapas"

Prints the raw key ONCE. Copy it to the .env / config of that installation.
The key is stored hashed in the backend DB and cannot be recovered.
"""

import argparse
import hashlib
import secrets
import sys
import os

# Allow running from project root: python -m backend.issue_device_key
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Issue a new device API key.")
    parser.add_argument("--username", required=True, help="operator_username this key belongs to")
    parser.add_argument("--label",    default="",   help="Human label for this installation")
    args = parser.parse_args()

    raw_key  = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    from backend.database import init_db, SessionLocal
    from backend.models import Device

    init_db()
    db = SessionLocal()
    try:
        device = Device(
            api_key_hash=key_hash,
            operator_username=args.username,
            label=args.label or f"Device for {args.username}",
            is_active=True,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    finally:
        db.close()

    print("=" * 60)
    print(f"  Device API Key emitida para: {args.username}")
    print(f"  Label: {device.label}")
    print(f"  Device ID: {device.id}")
    print()
    print(f"  RAW KEY (copiar ahora — no se puede recuperar):")
    print(f"  {raw_key}")
    print("=" * 60)
    print("  Agregar al .env del operador:")
    print(f"  COFFEE_DEVICE_KEY={raw_key}")


if __name__ == "__main__":
    main()
