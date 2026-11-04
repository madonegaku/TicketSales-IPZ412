"""Вихідні DTO сервісу payments: платіж у простих типах для відповіді API."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from payments.domain.payment import Payment


@dataclass(frozen=True)
class PaymentResult:
    """Платіж; replayed=True – повторний запит, повернено збережений платіж (контракт: 200)."""

    payment_id: UUID
    order_id: UUID
    amount: Decimal
    currency: str
    status: str
    decline_reason: str | None
    created_at: datetime
    replayed: bool


def to_result(payment: Payment, replayed: bool) -> PaymentResult:
    return PaymentResult(
        payment.id,
        payment.order_id,
        payment.amount.amount,
        payment.amount.currency,
        payment.status.value,
        payment.decline_reason,
        payment.created_at,
        replayed,
    )