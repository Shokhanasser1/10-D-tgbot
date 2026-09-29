import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_telegram_webhook_secret
from app.config import get_settings
from app.db.session import get_db
from app.schemas.telegram_update import TelegramUpdate
from app.services import (
    bot_service,
    location_service,
    order_admin_service,
    order_service,
    stripe_service,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Refunds started from the admin panel report their outcome through these.
_REFUND_EVENTS = frozenset({"refund.created", "refund.updated", "refund.failed"})


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature"
        ) from exc

    event_object = event["data"]["object"]

    if event["type"] in _REFUND_EVENTS:
        await order_admin_service.apply_refund_event(
            db,
            event_object.get("payment_intent"),
            event_object.get("id"),
            event_object.get("status"),
        )
        return {"status": "ok"}

    order_id_raw = event_object.get("metadata", {}).get("order_id")

    if order_id_raw is not None:
        order_id = int(order_id_raw)
        if event["type"] == "payment_intent.succeeded":
            await order_service.mark_order_paid(db, order_id)
        elif event["type"] == "payment_intent.payment_failed":
            await order_service.mark_order_payment_failed(db, order_id)

    return {"status": "ok"}


@router.post("/telegram", dependencies=[Depends(verify_telegram_webhook_secret)])
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        update = TelegramUpdate.model_validate(await request.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed update"
        ) from exc

    reply = bot_service.start_reply(update, get_settings().webapp_url)
    if reply is not None:
        return reply  # Telegram performs the Bot API call given in the webhook answer

    await location_service.handle_update(db, update)
    return {"status": "ok"}
