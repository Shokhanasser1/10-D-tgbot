import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.courier import CourierLocation
from app.models.enums import OrderStatus, ShipmentStatus
from tests.courier_factories import add_courier, add_paid_order, tma_headers

SECRET = "test-webhook-secret"
HEADER = "X-Telegram-Bot-Api-Secret-Token"
COURIER = 860_001


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", SECRET)


def update(
    *,
    sender: int = COURIER,
    kind: str = "message",
    chat_type: str = "private",
    latitude: float = 52.5,
    longitude: float = 13.4,
    is_bot: bool = False,
    with_location: bool = True,
    update_id: int = 1,
) -> dict:
    message: dict = {
        "message_id": 10,
        "date": 1_758_700_000,
        "from": {"id": sender, "is_bot": is_bot, "first_name": "Ali"},
        "chat": {"id": sender, "type": chat_type},
    }
    if with_location:
        message["location"] = {"latitude": latitude, "longitude": longitude, "live_period": 3600}
    else:
        message["text"] = "hello"
    return {"update_id": update_id, kind: message}


async def post(client: AsyncClient, body: dict | bytes, secret: str | None = SECRET):
    headers = {"content-type": "application/json"}
    if secret is not None:
        headers[HEADER] = secret
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return await client.post("/webhooks/telegram", content=content, headers=headers)


async def positions(db: AsyncSession) -> list[tuple[int, float, float]]:
    rows = (
        await db.execute(
            select(CourierLocation.courier_id, CourierLocation.latitude, CourierLocation.longitude)
        )
    ).all()
    return [tuple(row) for row in rows]


async def working_courier(db: AsyncSession, telegram_id: int = COURIER):
    """A courier who has claimed an order, which is what makes their position worth storing."""
    courier = await add_courier(db, telegram_id)
    order, shipment = await add_paid_order(db, customer_id=telegram_id + 500_000)
    shipment.courier_id = courier.id
    shipment.status = ShipmentStatus.assigned
    order.status = OrderStatus.processing  # what a real claim leaves behind
    await db.commit()
    return courier


async def test_the_feature_is_off_without_a_configured_secret(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")

    assert (await post(client, update())).status_code == 404
    assert (await post(client, update(), secret="")).status_code == 404


@pytest.mark.parametrize("secret", [None, "", "wrong-secret", SECRET + "x"])
async def test_a_missing_or_wrong_secret_is_forbidden(
    client: AsyncClient, secret: str | None
) -> None:
    assert (await post(client, update(), secret=secret)).status_code == 403


async def test_a_non_ascii_secret_is_forbidden_not_a_server_error(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/telegram",
        content=b"{}",
        headers={HEADER: "sécret".encode("latin-1"), "content-type": "application/json"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'"text"', b"{}"])
async def test_a_body_that_is_not_an_update_is_a_bad_request(
    client: AsyncClient, body: bytes
) -> None:
    assert (await post(client, body)).status_code == 400


async def test_a_position_from_a_working_courier_is_stored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await working_courier(db_session)

    response = await post(client, update(latitude=52.5, longitude=13.4))

    assert response.status_code == 200
    assert await positions(db_session) == [(courier.id, 52.5, 13.4)]


async def test_a_later_live_location_edit_replaces_the_stored_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await working_courier(db_session)
    await post(client, update(latitude=52.5, longitude=13.4))
    first = await db_session.scalar(select(CourierLocation.updated_at))

    await post(client, update(kind="edited_message", latitude=52.6, longitude=13.5, update_id=2))

    assert await positions(db_session) == [(courier.id, 52.6, 13.5)]
    await db_session.refresh(await db_session.get(CourierLocation, courier.id))
    assert await db_session.scalar(select(CourierLocation.updated_at)) > first


@pytest.mark.parametrize(
    "ignored",
    [
        update(sender=999_999),  # not a courier at all
        update(chat_type="group"),
        update(chat_type="supergroup"),
        update(chat_type="channel"),
        update(is_bot=True),
        update(with_location=False),
        update(latitude=91.0),
        update(latitude=-91.0),
        update(longitude=181.0),
        update(longitude=-181.0),
        {"update_id": 5, "callback_query": {"id": "1"}},  # a kind of update we do not read
    ],
    ids=[
        "unknown-sender",
        "group",
        "supergroup",
        "channel",
        "bot",
        "no-location",
        "lat-high",
        "lat-low",
        "lng-high",
        "lng-low",
        "other-update-type",
    ],
)
async def test_updates_we_do_not_act_on_are_acknowledged_without_storing_anything(
    client: AsyncClient, db_session: AsyncSession, ignored: dict
) -> None:
    await working_courier(db_session)

    response = await post(client, ignored)

    assert response.status_code == 200  # a non-200 would make Telegram retry it
    assert await positions(db_session) == []


async def test_a_non_finite_coordinate_is_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await working_courier(db_session)
    body = json.dumps(update()).replace("52.5", "NaN").encode()

    assert (await post(client, body)).status_code == 200
    assert await positions(db_session) == []


async def test_an_idle_courier_has_no_position_stored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER)  # registered, but holds no delivery

    assert (await post(client, update())).status_code == 200
    assert await positions(db_session) == []


async def test_an_inactive_courier_is_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER, is_active=False)

    assert (await post(client, update())).status_code == 200
    assert await positions(db_session) == []


async def test_finishing_the_last_delivery_removes_the_position_the_webhook_stored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await working_courier(db_session)
    await post(client, update())
    assert len(await positions(db_session)) == 1
    (delivery,) = (
        await client.get("/courier/deliveries", headers=tma_headers(COURIER))
    ).json()["deliveries"]

    for step in ("pickup", "deliver"):
        response = await client.post(
            f"/courier/deliveries/{delivery['shipment_id']}/{step}", headers=tma_headers(COURIER)
        )
        assert response.status_code == 200

    assert await positions(db_session) == []
    # And a straggling update after the delivery is over is not stored again.
    await post(client, update(update_id=9))
    assert await positions(db_session) == []


async def test_a_position_arriving_after_deactivation_is_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await working_courier(db_session)
    courier.is_active = False
    await db_session.commit()

    assert (await post(client, update())).status_code == 200
    assert await positions(db_session) == []


# --- /start ----------------------------------------------------------------------------------


def start_update(text: str = "/start", chat_type: str = "private", language: str | None = "ru"):
    sender: dict = {"id": 870_001, "is_bot": False, "first_name": "Aziza"}
    if language is not None:
        sender["language_code"] = language
    return {
        "update_id": 7,
        "message": {
            "message_id": 1,
            "date": 1_758_700_000,
            "from": sender,
            "chat": {"id": 870_001, "type": chat_type},
            "text": text,
        },
    }


async def test_start_answers_with_a_button_that_opens_the_shop(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", "https://shop.example.com/")

    response = await post(client, start_update())

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "sendMessage"
    assert body["chat_id"] == 870_001
    assert body["text"].startswith("Добро пожаловать")
    assert body["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "Открыть магазин", "web_app": {"url": "https://shop.example.com/"}}]
        ]
    }


@pytest.mark.parametrize(("language", "greeting"), [("uz", "Xush kelibsiz"), ("de", "Welcome")])
async def test_start_speaks_the_users_language_or_english(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, language: str, greeting: str
) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", "https://shop.example.com/")

    body = (await post(client, start_update(language=language))).json()

    assert body["text"].startswith(greeting)


async def test_start_with_a_payload_or_bot_name_is_still_start(client: AsyncClient) -> None:
    for text in ("/start promo42", "/start@shop_bot"):
        assert (await post(client, start_update(text=text))).json()["method"] == "sendMessage"


async def test_start_without_an_https_webapp_url_has_no_button(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", "http://localhost:8080/")

    body = (await post(client, start_update(language=None))).json()

    assert body["text"].startswith("Welcome")
    assert "reply_markup" not in body


@pytest.mark.parametrize(
    "update_body",
    [
        start_update(text="/help"),
        start_update(text="start"),
        start_update(chat_type="group"),
    ],
)
async def test_other_messages_get_no_reply(client: AsyncClient, update_body: dict) -> None:
    assert (await post(client, update_body)).json() == {"status": "ok"}
