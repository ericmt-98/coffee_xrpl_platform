"""
Coffee XRPL Platform — Signing Backend

Endpoints:
  GET  /health                  — liveness probe (no auth)
  POST /sign-requests           — create a Xaman sign request
  GET  /sign-requests/{uuid}    — poll a sign request status
"""

from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, init_db
from backend.auth import require_device
from backend.models import Device, OperatorToken, SignRequestLog
import backend.xumm_service as xumm_svc

app = FastAPI(title="Coffee XRPL Signing Backend", version="1.0.0")


@app.on_event("startup")
def on_startup():
    init_db()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Sign Requests ─────────────────────────────────────────────────────────────

class SignRequestBody(BaseModel):
    txjson:      dict
    identifier:  str          # UETR or custom id (for audit)
    instruction: str          # human-readable action shown in Xaman
    kind:        str          # signin / payment / escrow_create / escrow_finish / ...
    expire_minutes: int = 5


@app.post("/sign-requests")
def create_sign_request(
    body: SignRequestBody,
    device: Device = Depends(require_device),
    db: Session = Depends(get_db),
):
    # Look up stored user_token for push notifications (D4)
    op_token_row = db.query(OperatorToken).filter_by(
        operator_username=device.operator_username
    ).first()
    user_token = op_token_row.user_token if op_token_row else None

    try:
        result = xumm_svc.create_sign_request(
            body.txjson,
            identifier=body.identifier,
            instruction=body.instruction,
            kind=body.kind,
            user_token=user_token,
            expire_minutes=body.expire_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Xaman error: {exc}")

    # Audit log
    log = SignRequestLog(
        uuid=result["uuid"],
        operator_username=device.operator_username,
        identifier=body.identifier,
        kind=body.kind,
        status="pending",
    )
    db.add(log)
    db.commit()

    return result   # {uuid, qr_png, deeplink, pushed}


@app.get("/sign-requests/{uuid}")
def get_sign_request(
    uuid: str,
    device: Device = Depends(require_device),
    db: Session = Depends(get_db),
):
    try:
        status_data = xumm_svc.get_sign_status(uuid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Xaman error: {exc}")

    # If resolved and signed: persist user_token for future push (D4)
    if status_data["resolved"] and status_data["signed"]:
        issued = status_data.get("issued_user_token")
        if issued:
            row = db.query(OperatorToken).filter_by(
                operator_username=device.operator_username
            ).first()
            if row:
                row.user_token  = issued
                row.updated_at  = datetime.now(timezone.utc)
                if status_data.get("account"):
                    row.xrpl_address = status_data["account"]
            else:
                db.add(OperatorToken(
                    operator_username=device.operator_username,
                    xrpl_address=status_data.get("account"),
                    user_token=issued,
                ))

        # Update audit log
        log = db.query(SignRequestLog).filter_by(uuid=uuid).first()
        if log:
            log.status      = "signed"
            log.txid        = status_data.get("txid")
            log.resolved_at = datetime.now(timezone.utc)

        db.commit()

    elif status_data["resolved"]:
        final = "cancelled" if status_data["cancelled"] else "expired"
        log = db.query(SignRequestLog).filter_by(uuid=uuid).first()
        if log and log.status == "pending":
            log.status      = final
            log.resolved_at = datetime.now(timezone.utc)
            db.commit()

    return status_data   # {resolved, signed, cancelled, expired, txid, account, issued_user_token}
