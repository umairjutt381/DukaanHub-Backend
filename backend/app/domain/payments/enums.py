try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class PaymentMethod(StrEnum):
    CASH_ON_DELIVERY = "cash_on_delivery"
    JAZZCASH = "jazzcash"
    EASYPAISA = "easypaisa"
    CARD = "card"
    STRIPE = "stripe"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    FAILED_DELIVERY = "failed_delivery"


class GatewayName(StrEnum):
    CASH_ON_DELIVERY = "cash_on_delivery"
    JAZZCASH = "jazzcash"
    EASYPAISA = "easypaisa"
    CARD = "card"
    STRIPE = "stripe"


class WebhookProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
