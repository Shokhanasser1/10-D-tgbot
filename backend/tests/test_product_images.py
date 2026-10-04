import io
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import media_storage
from app.core.images import MAX_SIDE, ImageRejectedError, to_webp
from app.core.media_storage import MediaStorageError
from app.models.category import Category
from app.models.enums import AdminRole, ProductStatus
from app.models.product import Product
from app.models.variant import Variant
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS
from tests.factories import default_seller_id

settings = get_settings()


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    yield tmp_path


def _image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (40, 30), exif: bool = False) -> bytes:
    image = Image.new("RGB", size, (200, 30, 60))
    out = io.BytesIO()
    kwargs = {}
    if exif:
        data = Image.Exif()
        data[0x010F] = "PhoneMaker"  # Make
        data[0x8825] = {2: (41.0, 18.0, 0.0), 4: (69.0, 16.0, 0.0)}  # GPSInfo
        kwargs["exif"] = data.tobytes()
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


async def _product(db: AsyncSession, sku: str) -> tuple[int, int]:
    category = Category(slug=f"img-{sku}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        seller_id=await default_seller_id(db),
        category_id=category.id,
        base_sku=sku,
        base_price=Decimal("5.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variant = Variant(product_id=product.id, sku=f"{sku}-V", price=Decimal("5.00"), stock_qty=1)
    db.add(variant)
    await db.commit()
    return product.id, variant.id


def _upload(data: bytes, name: str = "photo.jpg", content_type: str = "image/jpeg") -> dict:
    return {"file": (name, data, content_type)}


# --- processing -----------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_supported_formats_become_webp(fmt: str) -> None:
    result = Image.open(io.BytesIO(to_webp(_image_bytes(fmt))))
    assert result.format == "WEBP"
    assert result.size == (40, 30)


def test_large_images_are_shrunk_but_small_ones_never_upscaled() -> None:
    big = Image.open(io.BytesIO(to_webp(_image_bytes(size=(3200, 1600)))))
    assert big.size == (MAX_SIDE, MAX_SIDE // 2)


def test_exif_including_gps_is_removed() -> None:
    raw = _image_bytes(exif=True)
    assert Image.open(io.BytesIO(raw)).getexif()  # the fixture really carries EXIF

    result = Image.open(io.BytesIO(to_webp(raw)))

    assert not result.getexif()
    assert "exif" not in result.info


def test_exif_orientation_is_applied() -> None:
    image = Image.new("RGB", (40, 20))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise when displayed
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif.tobytes())

    assert Image.open(io.BytesIO(to_webp(out.getvalue()))).size == (20, 40)


@pytest.mark.parametrize(
    "raw",
    [
        b"not an image at all",
        b"GIF89a" + b"\x00" * 64,  # a real image type, but not an accepted one
        _image_bytes("GIF"),
        _image_bytes("PNG")[:60],  # truncated
    ],
)
def test_unsupported_or_corrupt_data_is_rejected(raw: bytes) -> None:
    with pytest.raises(ImageRejectedError):
        to_webp(raw)


def test_decompression_bomb_is_rejected() -> None:
    # A tiny file that claims enormous dimensions: rejected from the header, never decoded.
    bomb = io.BytesIO()
    Image.new("1", (8000, 8000)).save(bomb, format="PNG")
    with pytest.raises(ImageRejectedError, match="dimensions"):
        to_webp(bomb.getvalue())


# --- endpoints ------------------------------------------------------------------------------


async def test_upload_stores_a_webp_under_media_root(
    client: AsyncClient, db_session: AsyncSession, media_root: Path
) -> None:
    product_id, variant_id = await _product(db_session, "UP-1")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes()),
        data={"variant_id": str(variant_id), "position": "3"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["url"].startswith("/media/products/") and body["url"].endswith(".webp")
    assert body["variant_id"] == variant_id
    assert body["position"] == 3
    stored = media_root / body["url"].removeprefix("/media/")
    assert Image.open(stored).format == "WEBP"


async def test_the_client_filename_is_ignored(
    client: AsyncClient, db_session: AsyncSession, media_root: Path
) -> None:
    product_id, _ = await _product(db_session, "UP-2")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes(), name="../../evil.php", content_type="text/x-php"),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 201
    assert "evil" not in response.json()["url"]
    assert [p.name for p in media_root.rglob("*") if p.is_file()][0].endswith(".webp")


async def test_non_image_upload_is_400_and_stores_nothing(
    client: AsyncClient, db_session: AsyncSession, media_root: Path
) -> None:
    product_id, _ = await _product(db_session, "UP-3")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(b"<?php system($_GET['c']); ?>", name="shell.jpg"),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 400
    assert not any(p.is_file() for p in media_root.rglob("*"))


async def test_oversized_upload_is_413(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    product_id, _ = await _product(db_session, "UP-4")
    monkeypatch.setattr("app.api.routes.internal_products.MAX_UPLOAD_BYTES", 100)

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes()),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 413


async def test_unreachable_photo_storage_is_502_and_adds_no_image(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    product_id, _ = await _product(db_session, "UP-R2")

    class DownStorage:
        def save(self, key: str, data: bytes) -> None:
            raise MediaStorageError("R2 is down")

        def remove(self, key: str) -> None:
            pass

    monkeypatch.setattr(media_storage, "from_settings", lambda _settings: DownStorage())

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes()),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 502
    assert response.json()["code"] == "media_unavailable"
    images = await client.get(f"/internal/products/{product_id}", headers=INTERNAL_HEADERS)
    assert images.json()["images"] == []


async def test_upload_without_a_file_is_400(client: AsyncClient, db_session: AsyncSession) -> None:
    product_id, _ = await _product(db_session, "UP-5")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files={"other": ("x.txt", b"x", "text/plain")},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 400


async def test_upload_with_a_bad_position_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    product_id, _ = await _product(db_session, "UP-5B")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes()),
        data={"position": "-1"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422


async def test_upload_to_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/products/999999/images", files=_upload(_image_bytes()), headers=INTERNAL_HEADERS
    )
    assert response.status_code == 404


async def test_variant_of_another_product_is_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    product_id, _ = await _product(db_session, "UP-6")
    _, foreign_variant = await _product(db_session, "UP-7")

    for kwargs in (
        {"files": _upload(_image_bytes()), "data": {"variant_id": str(foreign_variant)}},
        {"json": {"url": "https://cdn.test/a.jpg", "variant_id": foreign_variant}},
    ):
        response = await client.post(
            f"/internal/products/{product_id}/images", headers=INTERNAL_HEADERS, **kwargs
        )
        assert response.status_code == 400


async def test_json_url_images_still_work(client: AsyncClient, db_session: AsyncSession) -> None:
    product_id, _ = await _product(db_session, "UP-8")

    response = await client.post(
        f"/internal/products/{product_id}/images",
        json={"url": "https://cdn.test/a.jpg", "position": 1},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["url"] == "https://cdn.test/a.jpg"


async def test_json_without_url_is_422(client: AsyncClient, db_session: AsyncSession) -> None:
    product_id, _ = await _product(db_session, "UP-9")

    response = await client.post(
        f"/internal/products/{product_id}/images", json={"position": 1}, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 422


async def test_patch_reorders_and_reassigns_an_image(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    product_id, variant_id = await _product(db_session, "UP-10")
    image = (
        await client.post(
            f"/internal/products/{product_id}/images",
            json={"url": "https://cdn.test/a.jpg"},
            headers=INTERNAL_HEADERS,
        )
    ).json()

    moved = await client.patch(
        f"/internal/images/{image['id']}",
        json={"position": 5, "variant_id": variant_id},
        headers=INTERNAL_HEADERS,
    )
    back = await client.patch(
        f"/internal/images/{image['id']}", json={"variant_id": None}, headers=INTERNAL_HEADERS
    )

    assert moved.status_code == 200
    assert (moved.json()["position"], moved.json()["variant_id"]) == (5, variant_id)
    assert (back.json()["position"], back.json()["variant_id"]) == (5, None)


async def test_patch_unknown_image_is_404(client: AsyncClient) -> None:
    response = await client.patch(
        "/internal/images/999999", json={"position": 1}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 404


async def test_delete_removes_the_row_and_the_file(
    client: AsyncClient, db_session: AsyncSession, media_root: Path
) -> None:
    product_id, _ = await _product(db_session, "UP-11")
    image = (
        await client.post(
            f"/internal/products/{product_id}/images",
            files=_upload(_image_bytes()),
            headers=INTERNAL_HEADERS,
        )
    ).json()
    stored = media_root / image["url"].removeprefix("/media/")
    assert stored.exists()

    response = await client.delete(f"/internal/images/{image['id']}", headers=INTERNAL_HEADERS)

    assert response.status_code == 204
    assert not stored.exists()
    detail = await client.get(f"/internal/products/{product_id}", headers=INTERNAL_HEADERS)
    assert detail.json()["images"] == []


async def test_delete_tolerates_an_already_missing_file(
    client: AsyncClient, db_session: AsyncSession, media_root: Path
) -> None:
    product_id, _ = await _product(db_session, "UP-12")
    image = (
        await client.post(
            f"/internal/products/{product_id}/images",
            files=_upload(_image_bytes()),
            headers=INTERNAL_HEADERS,
        )
    ).json()
    (media_root / image["url"].removeprefix("/media/")).unlink()

    response = await client.delete(f"/internal/images/{image['id']}", headers=INTERNAL_HEADERS)

    assert response.status_code == 204


async def test_delete_unknown_image_is_404(client: AsyncClient) -> None:
    assert (
        await client.delete("/internal/images/999999", headers=INTERNAL_HEADERS)
    ).status_code == 404


async def test_dispatchers_cannot_touch_images(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    product_id, _ = await _product(db_session, "UP-13")
    await add_admin(db_session, 730_001, AdminRole.dispatcher)

    response = await client.post(
        f"/internal/products/{product_id}/images",
        files=_upload(_image_bytes()),
        headers=admin_tma(730_001),
    )

    assert response.status_code == 403
