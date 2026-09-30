"""Where uploaded product photos are kept.

MEDIA_STORAGE=local (the default) writes them under MEDIA_ROOT, which nginx serves. MEDIA_STORAGE=r2
puts them in a Cloudflare R2 bucket through its S3-compatible API, for hosts without a persistent
disk; the Pages Function in frontend/functions/media serves the bucket through a binding. Either
way the public URL stays /media/<key>, so nothing else changes.

The S3 request signing (AWS Signature Version 4) is done here rather than with boto3, which would
add tens of megabytes of memory on small free-tier hosts for two HTTP calls.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

R2_REGION = "auto"
R2_TIMEOUT_SECONDS = 30.0


class MediaStorageError(Exception):
    """The photo could not be stored."""


class MediaStorage(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def remove(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def _path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root not in path.parents:  # storage keys are ours, but never trust a path blindly
            raise ValueError(f"storage key escapes MEDIA_ROOT: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def remove(self, key: str) -> None:
        try:
            self._path_for(key).unlink(missing_ok=True)
        except (OSError, ValueError):
            # The row is already gone; an orphaned file is harmless, a 500 here would not be.
            logger.warning("could not remove media file %s", key, exc_info=True)


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def sign_v4(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload_hash: str,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    now: datetime | None = None,
    service: str = "s3",
) -> dict[str, str]:
    """Return `headers` plus the SigV4 ones (Authorization, x-amz-date, x-amz-content-sha256)."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    day = moment.strftime("%Y%m%d")
    parts = urlsplit(url)

    signed = {
        **{name.lower(): value.strip() for name, value in headers.items()},
        "host": parts.netloc,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    names = sorted(signed)
    canonical_request = "\n".join(
        [
            method,
            quote(parts.path or "/", safe="/-_.~"),
            parts.query,  # our requests carry no query string
            "".join(f"{name}:{signed[name]}\n" for name in names),
            ";".join(names),
            payload_hash,
        ]
    )
    scope = f"{day}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    key = _hmac(f"AWS4{secret_access_key}".encode(), day)
    for part in (region, service, "aws4_request"):
        key = _hmac(key, part)
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    return {
        **headers,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope},"
            f"SignedHeaders={';'.join(names)},Signature={signature}"
        ),
    }


class R2Storage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket}/"
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client = client or httpx.Client(timeout=R2_TIMEOUT_SECONDS)

    def _send(self, method: str, key: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
        url = self._base_url + key
        signed = sign_v4(
            method=method,
            url=url,
            headers=headers,
            payload_hash=hashlib.sha256(body).hexdigest(),
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            region=R2_REGION,
        )
        return self._client.request(method, url, content=body, headers=signed)

    def save(self, key: str, data: bytes) -> None:
        try:
            response = self._send("PUT", key, data, {"Content-Type": "image/webp"})
        except httpx.HTTPError as exc:
            raise MediaStorageError(f"R2 upload of {key} failed: {exc}") from exc
        if response.is_error:
            raise MediaStorageError(
                f"R2 upload of {key} failed: {response.status_code} {response.text[:200]}"
            )

    def remove(self, key: str) -> None:
        try:
            response = self._send("DELETE", key, b"", {})
            response.raise_for_status()
        except httpx.HTTPError:
            # Same as local: the row is already gone, an orphaned object is harmless.
            logger.warning("could not remove R2 object %s", key, exc_info=True)


def from_settings(settings: Settings) -> MediaStorage:
    if settings.media_storage == "r2":
        return R2Storage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
        )
    return LocalStorage(settings.media_root)
