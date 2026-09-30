from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core import media_storage
from app.core.media_storage import LocalStorage, R2Storage, sign_v4

AWS_EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_EXAMPLE_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_signature_matches_the_aws_sigv4_reference_example() -> None:
    # "GET Object" example from the AWS S3 SigV4 documentation (header-based auth).
    headers = sign_v4(
        method="GET",
        url="https://examplebucket.s3.amazonaws.com/test.txt",
        headers={"Range": "bytes=0-9"},
        payload_hash=EMPTY_SHA256,
        access_key_id=AWS_EXAMPLE_KEY,
        secret_access_key=AWS_EXAMPLE_SECRET,
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
    )
    assert headers["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert headers["x-amz-date"] == "20130524T000000Z"
    assert headers["x-amz-content-sha256"] == EMPTY_SHA256


def _r2(handler) -> R2Storage:  # type: ignore[no-untyped-def]
    return R2Storage(
        account_id="acc123",
        access_key_id="key",
        secret_access_key="secret",
        bucket="photos",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_r2_save_puts_the_object_with_a_signed_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    _r2(handler).save("products/abc.webp", b"webp-bytes")

    (request,) = seen
    assert request.method == "PUT"
    assert str(request.url) == "https://acc123.r2.cloudflarestorage.com/photos/products/abc.webp"
    assert request.content == b"webp-bytes"
    assert request.headers["Content-Type"] == "image/webp"
    assert request.headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=key/")
    assert "/auto/s3/aws4_request" in request.headers["Authorization"]


def test_r2_save_raises_when_the_bucket_refuses() -> None:
    storage = _r2(lambda request: httpx.Response(403, text="AccessDenied"))
    with pytest.raises(media_storage.MediaStorageError):
        storage.save("products/abc.webp", b"x")


def test_r2_remove_deletes_and_tolerates_failures() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(500)

    _r2(handler).remove("products/abc.webp")  # must not raise: the row is already gone
    assert seen == ["DELETE"]


def test_local_storage_writes_and_removes(tmp_path: Path) -> None:
    storage = LocalStorage(str(tmp_path))
    storage.save("products/a.webp", b"data")
    assert (tmp_path / "products" / "a.webp").read_bytes() == b"data"
    storage.remove("products/a.webp")
    assert not (tmp_path / "products" / "a.webp").exists()
    storage.remove("products/a.webp")  # already missing is fine


def test_local_storage_refuses_keys_outside_the_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        LocalStorage(str(tmp_path)).save("../escape.webp", b"x")


def test_r2_mode_requires_all_credentials() -> None:
    with pytest.raises(ValidationError, match="R2_"):
        Settings(media_storage="r2", r2_account_id="acc")


def test_storage_follows_the_settings(tmp_path: Path) -> None:
    local = Settings(media_root=str(tmp_path))
    assert isinstance(media_storage.from_settings(local), LocalStorage)
    r2 = Settings(
        media_storage="r2",
        r2_account_id="a",
        r2_access_key_id="k",
        r2_secret_access_key="s",
        r2_bucket="b",
    )
    assert isinstance(media_storage.from_settings(r2), R2Storage)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # Supabase / Neon hand out libpq URLs: asyncpg needs its driver name and ssl=...
        (
            "postgresql://u:p@db.example.com:5432/app?sslmode=require",
            "postgresql+asyncpg://u:p@db.example.com:5432/app?ssl=require",
        ),
        (
            "postgres://u:p@db.example.com/app?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@db.example.com/app?ssl=require",
        ),
        (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront",
        ),
    ],
)
def test_hosted_database_urls_are_made_asyncpg_ready(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected
