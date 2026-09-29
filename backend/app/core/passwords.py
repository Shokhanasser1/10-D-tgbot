"""Admin passwords (Spec 7 §4): scrypt hashes from the standard library, no extra dependency.

A hash is stored as "scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>", so the cost can be raised later
without breaking passwords set earlier.
"""

import base64
import hashlib
import hmac
import re
import secrets

_N, _R, _P = 2**14, 8, 1
_KEY_LENGTH = 32
_SALT_BYTES = 16

LOGIN_PATTERN = re.compile(r"[a-z0-9_.-]{3,32}")
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200  # scrypt is costly; refuse absurd inputs before hashing


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LENGTH, maxmem=64 * 1024 * 1024
    )
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or len(password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(base64.b64decode(expected)),
            maxmem=64 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, base64.b64decode(expected))


def normalize_login(login: str) -> str:
    return login.strip().lower()


def login_problem(login: str) -> str | None:
    """Why a login is not acceptable, or None."""
    if not LOGIN_PATTERN.fullmatch(normalize_login(login)):
        return "The login must be 3-32 characters: latin letters, digits, _ . -"
    return None


def password_problem(password: str, login: str | None) -> str | None:
    """Why a new password is not acceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"The password must be at least {MIN_PASSWORD_LENGTH} characters"
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"The password must be at most {MAX_PASSWORD_LENGTH} characters"
    if login and password.strip().lower() == normalize_login(login):
        return "The password must not be the login"
    return None


def temporary_password() -> str:
    """For an owner's reset: shown once, must be changed at the next sign-in."""
    return secrets.token_urlsafe(12)
