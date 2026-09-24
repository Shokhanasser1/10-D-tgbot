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


# A courier is "working" while they hold a shipment in one of these states.
ACTIVE_SHIPMENT_STATUSES = (ShipmentStatus.assigned, ShipmentStatus.shipped)
