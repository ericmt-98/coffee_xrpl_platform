"""Thin wrapper around xumm-sdk-py.

The Xaman API Secret lives ONLY here (loaded from env via config.py).
It is never returned to the desktop client.
"""

import xumm
from backend.config import XUMM_APIKEY, XUMM_APISECRET

_sdk = xumm.XummSdk(XUMM_APIKEY, XUMM_APISECRET)


def ping() -> dict:
    """Verify credentials. Returns app name and quota info."""
    pong = _sdk.ping()
    return {
        "app_name": getattr(getattr(pong, "application", None), "name", "unknown"),
        "quota_remaining": getattr(getattr(pong, "quota", None), "ratelimit_remaining", None),
    }


def create_sign_request(
    txjson: dict,
    *,
    identifier: str,
    instruction: str,
    kind: str,
    user_token: str | None = None,
    expire_minutes: int = 5,
) -> dict:
    """Create a Xaman payload (sign request).

    Returns {uuid, qr_png, deeplink, pushed}.
    qr_png is a URL to a PNG image hosted by Xaman — the desktop downloads it.
    """
    payload: dict = {
        "txjson": txjson,
        "options": {"submit": True, "expire": expire_minutes},
        "custom_meta": {"identifier": identifier, "instruction": instruction},
    }
    if user_token:
        payload["user_token"] = user_token

    created = _sdk.payload.create(payload)
    return {
        "uuid":     created.uuid,
        "qr_png":   created.refs.qr_png,
        "deeplink": created.next.always,
        "pushed":   bool(getattr(created, "pushed", False)),
    }


def get_sign_status(uuid: str) -> dict:
    """Poll a payload status.

    Returns {resolved, signed, cancelled, expired, txid, account, issued_user_token}.
    """
    p = _sdk.payload.get(uuid)
    return {
        "resolved":           bool(p.meta.resolved),
        "signed":             bool(p.meta.signed),
        "cancelled":          bool(p.meta.cancelled),
        "expired":            bool(p.meta.expired),
        "txid":               getattr(p.response, "txid", None),
        "account":            getattr(p.response, "account", None),
        "issued_user_token":  getattr(p.application, "issued_user_token", None),
    }
