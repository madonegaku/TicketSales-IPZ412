"""Запит «Отримати платіж»: звірка стану оплати за замовленням."""

from uuid import UUID

from payments.application.dto import PaymentResult, to_result
from payments.domain.exceptions import NotFoundError
from payments.domain.repositories import PaymentRepository


class GetPayment:
    """Повертає платіж за замовленням; стан сховища не змінює."""

    def __init__(self, payments: PaymentRepository) -> None:
        self._payments = payments

    def execute(self, order_id: UUID) -> PaymentResult:
        payment = self._payments.find_by_order(order_id)
        if payment is None:
            raise NotFoundError("Платежу за цим замовленням немає.")
        return to_result(payment, replayed=False)