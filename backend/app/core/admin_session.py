"""Stateless signed admin cookies: "<telegram_id>.<version>.<issued_at>.<hmac>".

Two kinds share the format: the browser session, and the short-lived password confirmation that
unlocks dangerous actions (Spec 7 §5). The kind is part of the signed payload, so one can never be
used as the other. No session table: the admins row is re-read on every request, and its
`session_version` must match, so a password change or deactivation ends access at once even though
an old cookie still verifies.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass

SESSION = "session"
CONFIRM = "confirm"


@dataclass(frozen=True)
class SignedAdmin:
    telegram_id: int
    version: int
    issued_at: int


def _signature(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def sign(
    telegram_id: int, version: int, secret: str, *, kind: str = SESSION, now: float | None = None
) -> str:
    body = f"{telegram_id}.{version}.{int(now if now is not None else time.time())}"
    return f"{body}.{_signature(secret, f'{kind}:{body}')}"


def verify(
    value: str, secret: str, max_age_seconds: int, *, kind: str = SESSION
) -> SignedAdmin | None:
    """The signed admin of a valid, unexpired cookie of this kind, else None."""
    if not secret:
        return None
    parts = value.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts[:3]):
        return None
    body = ".".join(parts[:3])
    if not hmac.compare_digest(_signature(secret, f"{kind}:{body}").encode(), parts[3].encode()):
        return None
    signed = SignedAdmin(int(parts[0]), int(parts[1]), int(parts[2]))
    if time.time() - signed.issued_at > max_age_seconds:
        return None
    return signed


# Kept for the Telegram widget sign-in and older call sites: a session for the current version.
def sign_session(
    telegram_id: int, secret: str, *, version: int = 1, now: float | None = None
) -> str:
    return sign(telegram_id, version, secret, kind=SESSION, now=now)


def verify_session(value: str, secret: str, max_age_seconds: int) -> int | None:
    signed = verify(value, secret, max_age_seconds, kind=SESSION)
    return signed.telegram_id if signed else None
