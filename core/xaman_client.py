"""HTTP client that talks to the Coffee XRPL Signing Backend.

The backend holds the Xaman API Secret. This client only knows the
backend URL and the device API key (both stored encrypted locally via
config_store). The operator's seed / private key is never involved here.
"""

import requests


class XamanClient:
    """Desktop-side client for the signing backend."""

    def __init__(self, base_url: str, device_api_key: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {device_api_key}",
            "Content-Type": "application/json",
        }
        self.timeout = timeout

    # ── Public API ────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the backend is reachable and the device key is valid."""
        try:
            r = requests.get(f"{self.base_url}/health",
                             headers=self._headers, timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def create_sign_request(
        self,
        txjson: dict,
        *,
        identifier: str,
        instruction: str,
        kind: str,
        expire_minutes: int = 5,
    ) -> dict:
        """Ask the backend to create a Xaman sign request.

        Returns {uuid, qr_png (URL), deeplink, pushed}.
        Raises requests.HTTPError on backend error.
        """
        r = requests.post(
            f"{self.base_url}/sign-requests",
            json={
                "txjson":      txjson,
                "identifier":  identifier,
                "instruction": instruction,
                "kind":        kind,
                "expire_minutes": expire_minutes,
            },
            headers=self._headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()   # {uuid, qr_png, deeplink, pushed}

    def get_sign_status(self, uuid: str) -> dict:
        """Poll a sign request status.

        Returns {resolved, signed, cancelled, expired, txid, account, issued_user_token}.
        """
        r = requests.get(
            f"{self.base_url}/sign-requests/{uuid}",
            headers=self._headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def fetch_qr_bytes(self, qr_png_url: str) -> bytes:
        """Download the QR PNG image. Returns raw bytes for QPixmap."""
        r = requests.get(qr_png_url, timeout=10)
        r.raise_for_status()
        return r.content

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls) -> "XamanClient | None":
        """Build a client from encrypted local config. Returns None if not configured."""
        try:
            from core.config_store import get_config
            url = get_config("backend_url")
            key = get_config("device_api_key")
            if url and key:
                return cls(url, key)
        except Exception:
            pass
        return None
