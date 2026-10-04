"""The texts of Telegram notifications in each supported language (Spec 5).

Templates use str.format placeholders. `render` falls back to English for an unknown language,
so a recipient whose locale is not translated still gets a message.
"""

from decimal import Decimal

FALLBACK = "en"

TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "order_paid": "Order #{order_id} is paid. We're finding a courier.",
        "pool_new": "New order in the pool: {place}, {items}.",
        "pool_again": "Order back in the pool: {place}, {items}.",
        "admin_new_order": "New order #{order_id}, {total}.",
        "admin_shortfall": " ⚠ Not enough stock.",
        "order_claimed": "Courier {courier} has taken order #{order_id}.",
        "order_picked_up": "Order #{order_id} is on its way. Follow the courier on the map.",
        "order_delivered": "Order #{order_id} has been delivered. Thank you!",
        "order_expired": (
            "Payment time for order #{order_id} ran out. Your items are back in the cart."
        ),
        "order_cancelled": (
            "Order #{order_id} was cancelled by the shop: {reason}. Your money will be refunded."
        ),
        "refund_succeeded": "The payment for order #{order_id} has been refunded.",
        "refund_failed": "⚠ The refund for order #{order_id} failed. Retry it in the admin panel.",
        "order_confirmed_cash": (
            "Order #{order_id} is confirmed. Pay in cash on delivery: {total}."
        ),
        "pool_cash": " Cash: {total}.",
        "pool_pickup": " Pickup: {pickup}.",
        "seller_new_order": (
            "New order #{order_id}: {items}. Collect it and press Ready, then a courier comes."
        ),
        "button_seller_order": "Open order",
        "payout_recorded": "Payout recorded: {amount}. Balance: {balance}.",
        "button_money": "Open my money",
        "order_cancelled_unpaid": "Order #{order_id} was cancelled by the shop: {reason}.",
        "refund_manual": (
            "Refund {total} for order #{order_id} by hand in the Click/Payme cabinet "
            '(payment ID {charge}), then press "Refund done" in the admin panel.'
        ),
        "button_order": "Open order",
        "button_courier": "Open deliveries",
        "button_admin": "Open in admin",
        "button_cart": "Open cart",
    },
    "ru": {
        "order_paid": "Заказ №{order_id} оплачен. Ищем курьера.",
        "pool_new": "Новый заказ в пуле: {place}, {items}.",
        "pool_again": "Заказ снова в пуле: {place}, {items}.",
        "admin_new_order": "Новый заказ №{order_id}, {total}.",
        "admin_shortfall": " ⚠ Не хватает товара.",
        "order_claimed": "Курьер {courier} принял заказ №{order_id}.",
        "order_picked_up": "Заказ №{order_id} в пути. Следите за курьером на карте.",
        "order_delivered": "Заказ №{order_id} доставлен. Спасибо!",
        "order_expired": "Время оплаты заказа №{order_id} истекло. Товары вернулись в корзину.",
        "order_cancelled": "Магазин отменил заказ №{order_id}: {reason}. Деньги вернутся вам.",
        "refund_succeeded": "Оплата за заказ №{order_id} возвращена.",
        "refund_failed": "⚠ Возврат по заказу №{order_id} не прошёл. Повторите его в админке.",
        "order_confirmed_cash": (
            "Заказ №{order_id} принят. Оплата наличными при получении: {total}."
        ),
        "pool_cash": " Наличные: {total}.",
        "pool_pickup": " Забрать: {pickup}.",
        "seller_new_order": (
            "Новый заказ №{order_id}: {items}. Соберите его и нажмите «Готов», "
            "после этого приедет курьер."
        ),
        "button_seller_order": "Открыть заказ",
        "payout_recorded": "Записана выплата: {amount}. Остаток к выплате: {balance}.",
        "button_money": "Мои деньги",
        "order_cancelled_unpaid": "Магазин отменил заказ №{order_id}: {reason}.",
        "refund_manual": (
            "Верните {total} за заказ №{order_id} вручную в кабинете Click/Payme "
            "(ID платежа {charge}), затем нажмите «Возврат сделан» в админке."
        ),
        "button_order": "Открыть заказ",
        "button_courier": "Открыть доставки",
        "button_admin": "Открыть в админке",
        "button_cart": "Открыть корзину",
    },
    "uz": {
        "order_paid": "№{order_id} buyurtma to'landi. Kuryer qidirilmoqda.",
        "pool_new": "Navbatda yangi buyurtma: {place}, {items}.",
        "pool_again": "Buyurtma yana navbatda: {place}, {items}.",
        "admin_new_order": "Yangi buyurtma №{order_id}, {total}.",
        "admin_shortfall": " ⚠ Mahsulot yetarli emas.",
        "order_claimed": "Kuryer {courier} №{order_id} buyurtmani qabul qildi.",
        "order_picked_up": "№{order_id} buyurtma yo'lda. Kuryerni xaritada kuzating.",
        "order_delivered": "№{order_id} buyurtma yetkazildi. Rahmat!",
        "order_expired": (
            "№{order_id} buyurtma uchun to'lov vaqti tugadi. Mahsulotlar savatga qaytarildi."
        ),
        "order_cancelled": (
            "Do'kon №{order_id} buyurtmani bekor qildi: {reason}. Pulingiz qaytariladi."
        ),
        "refund_succeeded": "№{order_id} buyurtma uchun to'lov qaytarildi.",
        "refund_failed": (
            "⚠ №{order_id} buyurtma bo'yicha qaytarish amalga oshmadi. Admin panelda qayta urining."
        ),
        "order_confirmed_cash": (
            "№{order_id} buyurtma qabul qilindi. Yetkazilganda naqd to'lov: {total}."
        ),
        "pool_cash": " Naqd: {total}.",
        "pool_pickup": " Olib ketish: {pickup}.",
        "seller_new_order": (
            "Yangi buyurtma №{order_id}: {items}. Uni yig'ing va «Tayyor» tugmasini bosing, "
            "shundan keyin kuryer keladi."
        ),
        "button_seller_order": "Buyurtmani ochish",
        "payout_recorded": "To'lov qayd etildi: {amount}. To'lanadigan qoldiq: {balance}.",
        "button_money": "Mening pullarim",
        "order_cancelled_unpaid": "Do'kon №{order_id} buyurtmani bekor qildi: {reason}.",
        "refund_manual": (
            "№{order_id} buyurtma uchun {total} ni Click/Payme kabinetida qo'lda qaytaring "
            "(to'lov ID {charge}), so'ng admin panelda «Qaytarildi» tugmasini bosing."
        ),
        "button_order": "Buyurtmani ochish",
        "button_courier": "Yetkazishlarni ochish",
        "button_admin": "Admin panelda ochish",
        "button_cart": "Savatni ochish",
    },
}

_CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
# Currencies priced in whole units in practice: shown without decimals.
_WHOLE_UNIT = {"UZS"}
_SUM_WORD = {"ru": "сум", "uz": "so'm"}


def language_of(locale: str | None) -> str:
    return locale if locale in TEMPLATES else FALLBACK


def render(key: str, locale: str | None, **values: object) -> str:
    return TEMPLATES[language_of(locale)][key].format(**values)


def money(amount: Decimal, currency: str, locale: str | None = None) -> str:
    code = currency.upper()
    language = language_of(locale)
    if code in _WHOLE_UNIT:
        whole = int(amount.quantize(Decimal("1")))
        if language == "en":
            return f"{code} {whole:,}"
        return f"{whole:,}".replace(",", " ") + f" {_SUM_WORD.get(language, code)}"
    symbol = _CURRENCY_SYMBOLS.get(code)
    return f"{symbol}{amount:.2f}" if symbol else f"{amount:.2f} {code}"


def items(count: int, locale: str | None) -> str:
    language = language_of(locale)
    if language == "ru":
        if count % 10 == 1 and count % 100 != 11:
            word = "товар"
        elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            word = "товара"
        else:
            word = "товаров"
        return f"{count} {word}"
    if language == "uz":
        return f"{count} ta mahsulot"
    return f"{count} item" if count == 1 else f"{count} items"
