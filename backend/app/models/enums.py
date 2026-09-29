import enum


class AttributeValueType(enum.StrEnum):
    text = "text"
    number = "number"
    boolean = "boolean"
    color = "color"


class ProductStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"


class CartStatus(enum.StrEnum):
    active = "active"
    checked_out = "checked_out"
    abandoned = "abandoned"


class OrderStatus(enum.StrEnum):
    pending_payment = "pending_payment"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentStatus(enum.StrEnum):
    requires_payment_method = "requires_payment_method"
    requires_action = "requires_action"
    processing = "processing"
    succeeded = "succeeded"
    canceled = "canceled"


class ShipmentStatus(enum.StrEnum):
    processing = "processing"  # paid, waiting in the courier pool
    assigned = "assigned"  # claimed by a courier, not yet picked up
    shipped = "shipped"  # picked up, out for delivery
    delivered = "delivered"
    cancelled = "cancelled"  # the order was cancelled before pickup


class AdminRole(enum.StrEnum):
    owner = "owner"
    manager = "manager"  # the owner's deputy: everything except admins and manual refunds
    catalog_manager = "catalog_manager"
    dispatcher = "dispatcher"
    accountant = "accountant"  # money: summary, orders, refunds
    viewer = "viewer"  # sees almost everything, changes nothing


class Permission(enum.StrEnum):
    summary_view = "summary.view"
    catalog_view = "catalog.view"
    catalog_edit = "catalog.edit"
    orders_view = "orders.view"
    orders_cancel_unpaid = "orders.cancel_unpaid"
    orders_cancel_paid = "orders.cancel_paid"
    refunds_manage = "refunds.manage"
    couriers_view = "couriers.view"
    couriers_manage = "couriers.manage"
    admins_manage = "admins.manage"


class RefundStatus(enum.StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    # The provider has no refund API (Telegram Payments): an owner refunds in its cabinet.
    manual_required = "manual_required"


class PaymentMethod(enum.StrEnum):
    telegram = "telegram"  # Telegram Payments with Click or Payme as the provider
    cash = "cash"  # paid to the courier on delivery
    stripe = "stripe"


class NotificationStatus(enum.StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"  # gave up: retries exhausted, or Telegram rejected the message itself
    undeliverable = "undeliverable"  # the user blocked the bot or never opened a chat with it


# A courier is "working" while they hold a shipment in one of these states.
ACTIVE_SHIPMENT_STATUSES = (ShipmentStatus.assigned, ShipmentStatus.shipped)
