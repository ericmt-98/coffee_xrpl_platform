"""
Xaman Integration Spike — standalone, no app imports.

Tests the full sign-request cycle against Xaman API:
  1. Credentials ping
  2. Sign In (QR + polling)
  3. XRP Payment (signed + verified on testnet)
  4. Rejection detection
  5. Expiry detection

Usage:
    1. Copy .env.example to .env and fill in XUMM_APIKEY / XUMM_APISECRET.
    2. Install spike deps: pip install xumm-sdk-py python-dotenv xrpl-py
    3. python scripts/spike_xaman.py

Set XUMM_APIKEY and XUMM_APISECRET in .env or as environment variables.
IMPORTANT: The operator's Xaman app must be set to TESTNET mode for the
payment step (Profile → Advanced → Developer mode → XRPL Testnet).
"""

import os
import sys
import time

# ── Skip cleanly if credentials are missing ──────────────────────────────────
_APIKEY  = os.environ.get("XUMM_APIKEY", "")
_SECRET  = os.environ.get("XUMM_APISECRET", "")

if not _APIKEY or not _SECRET:
    # Try loading from .env in project root
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        _APIKEY = os.environ.get("XUMM_APIKEY", "")
        _SECRET = os.environ.get("XUMM_APISECRET", "")
    except ImportError:
        pass

if not _APIKEY or not _SECRET:
    print("SKIP: XUMM_APIKEY / XUMM_APISECRET not set. "
          "Add them to .env or environment variables.")
    sys.exit(0)

try:
    import xumm
except ImportError:
    print("SKIP: xumm-sdk-py not installed. Run: pip install xumm-sdk-py")
    sys.exit(0)

TESTNET_EXPLORER = "https://testnet.xrpl.org/transactions/{}"
POLL_INTERVAL    = 3   # seconds between status checks
POLL_TIMEOUT     = 120 # seconds before giving up


def _poll(sdk, uuid: str, label: str) -> dict:
    """Poll a payload until resolved or timeout."""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = sdk.payload.get(uuid)
        if status.meta.resolved:
            return status
        remaining = int(deadline - time.time())
        print(f"  [{label}] Esperando... ({remaining}s restantes)")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Payload {uuid} no resuelto en {POLL_TIMEOUT}s")


def step1_ping(sdk):
    print("\n=== STEP 1: Ping (credenciales) ===")
    pong = sdk.ping()
    app_name = getattr(getattr(pong, "application", None), "name", "?")
    quota    = getattr(getattr(pong, "quota", None), "ratelimit_remaining", "?")
    print(f"  OK — App: {app_name!r} | Quota restante: {quota}")


def step2_sign_in(sdk) -> str | None:
    """Sign In — returns issued_user_token if obtained."""
    print("\n=== STEP 2: Sign In ===")
    created = sdk.payload.create({"txjson": {"TransactionType": "SignIn"},
                                  "options": {"expire": 5}})
    uuid     = created.uuid
    qr       = created.refs.qr_png
    deeplink = created.next.always
    print(f"  UUID:     {uuid}")
    print(f"  QR URL:   {qr}")
    print(f"  Deeplink: {deeplink}")
    print(f"  Escanee el QR con Xaman (modo TESTNET) o abra el deeplink.")

    status = _poll(sdk, uuid, "SignIn")
    if status.meta.signed:
        acct  = status.response.account
        token = getattr(status.application, "issued_user_token", None)
        print(f"  FIRMADO ✓ | Cuenta: {acct} | user_token: {token}")
        return token
    else:
        print(f"  No firmado (cancelled={status.meta.cancelled}, "
              f"expired={status.meta.expired})")
        return None


def step3_payment(sdk, destination: str, amount_drops: str = "1000000"):
    """Payment payload — 1 XRP to destination on TESTNET."""
    print("\n=== STEP 3: Pago XRP en Testnet ===")
    print(f"  Destino: {destination} | Monto: {int(amount_drops)/1_000_000} XRP")
    created = sdk.payload.create({
        "txjson": {
            "TransactionType": "Payment",
            "Destination": destination,
            "Amount": amount_drops,
        },
        "options": {"submit": True, "expire": 5},
        "custom_meta": {
            "identifier": "spike-test",
            "instruction": "Pago de prueba — spike Xaman (testnet)",
        },
    })
    uuid     = created.uuid
    qr       = created.refs.qr_png
    deeplink = created.next.always
    print(f"  UUID:     {uuid}")
    print(f"  QR URL:   {qr}")
    print(f"  Deeplink: {deeplink}")
    print(f"  Escanee el QR y APRUEBE el pago en Xaman (modo TESTNET).")

    status = _poll(sdk, uuid, "Payment")
    if status.meta.signed:
        txid = status.response.txid
        print(f"  FIRMADO ✓ | txid: {txid}")
        print(f"  Explorer: {TESTNET_EXPLORER.format(txid)}")
    else:
        print(f"  No firmado (cancelled={status.meta.cancelled}, "
              f"expired={status.meta.expired})")


def step4_rejection(sdk):
    print("\n=== STEP 4: Detección de rechazo ===")
    created = sdk.payload.create({
        "txjson": {"TransactionType": "SignIn"},
        "options": {"expire": 5},
    })
    print(f"  UUID: {created.uuid}")
    print(f"  Escanee el QR y RECHACE en Xaman (botón ✗).")
    status = _poll(sdk, created.uuid, "Rejection")
    cancelled = status.meta.cancelled
    print(f"  cancelled={cancelled} — {'OK ✓' if cancelled else 'INESPERADO'}")


def step5_expiry(sdk):
    print("\n=== STEP 5: Detección de expiración (expire=1 min) ===")
    created = sdk.payload.create({
        "txjson": {"TransactionType": "SignIn"},
        "options": {"expire": 1},
    })
    print(f"  UUID: {created.uuid}")
    print(f"  Esperando expiración (~65s, NO firme)...")
    deadline = time.time() + 90
    while time.time() < deadline:
        status = sdk.payload.get(created.uuid)
        if status.meta.resolved:
            print(f"  expired={status.meta.expired} — "
                  f"{'OK ✓' if status.meta.expired else 'INESPERADO'}")
            return
        time.sleep(5)
    print("  Timeout esperando expiración — verificar manualmente.")


if __name__ == "__main__":
    print("=" * 60)
    print("  Xaman Integration Spike — XRPL Testnet")
    print("=" * 60)

    sdk = xumm.XummSdk(_APIKEY, _SECRET)

    step1_ping(sdk)
    step2_sign_in(sdk)

    # For steps 3+ we need a testnet destination address.
    # Use a known testnet faucet address or one you own on testnet.
    testnet_dest = os.environ.get("XUMM_SPIKE_DEST", "")
    if testnet_dest:
        step3_payment(sdk, testnet_dest)
    else:
        print("\n=== STEP 3: OMITIDO ===")
        print("  Defina XUMM_SPIKE_DEST=<dirección testnet> para probar pagos.")

    step4_rejection(sdk)
    step5_expiry(sdk)

    print("\n=== Spike completado ===")
