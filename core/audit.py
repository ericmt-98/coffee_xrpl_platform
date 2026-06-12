"""
Audit logging helper for the Coffee XRPL Platform.
"""

from core.models import AuditLog


def log_audit(session, user_id, action: str, details: str = None):
    """Add an AuditLog entry to an existing session (caller commits)."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
    )
    session.add(entry)
