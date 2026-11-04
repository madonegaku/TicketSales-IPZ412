"""Сховище платежів у пам'яті – для тестів сценаріїв; сервіс використовуватиме SQLite."""

from copy import deepcopy
from uuid import UUID

from payments.domain.payment import Payment
from payments.domain.repositories import PaymentRepository


class InMemoryPaymentRepository(PaymentRepository):
    """Платежі у словнику за ідентифікатором замовлення; нова спроба замінює відхилений платіж."""

    def __init__(self) -> None:
        self._payments: dict[UUID, Payment] = {}

    def find_by_order(self, order_id: UUID) -> Payment | None:
        payment = self._payments.get(order_id)
        return deepcopy(payment) if payment is not None else None

    def save(self, payment: Payment) -> None:
        self._payments[payment.order_id] = deepcopy(payment)