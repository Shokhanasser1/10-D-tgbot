import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_telegram_webhook_secret
from app.db.session import get_db
from app.schemas.telegram_update import TelegramUpdate
from app.services import location_service, order_service, stripe_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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

    await location_service.handle_update(db, update)
    return {"status": "ok"}
