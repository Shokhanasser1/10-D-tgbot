"""Stateless admin browser sessions: "<telegram_id>.<issued_at>.<hmac>".

No session table: the admins row is re-read on every request, so deactivating an admin ends
their access immediately even though an old cookie still verifies.
"""

import hashlib
import hmac
import time


def _signature(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def sign_session(telegram_id: int, secret: str, *, now: float | None = None) -> str:
    payload = f"{telegram_id}.{int(now if now is not None else time.time())}"
    return f"{payload}.{_signature(secret, payload)}"


def verify_session(value: str, secret: str, max_age_seconds: int) -> int | None:
    """Return the telegram_id of a valid, unexpired session, else None."""
    if not secret:
        return None
    parts = value.split(".")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    payload = f"{parts[0]}.{parts[1]}"
    if not hmac.compare_digest(_signature(secret, payload).encode(), parts[2].encode()):
        return None
    if time.time() - int(parts[1]) > max_age_seconds:
        return None
    return int(parts[0])
