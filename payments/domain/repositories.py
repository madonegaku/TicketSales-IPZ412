"""Інтерфейс сховища платежів. Реалізації – в інфраструктурному шарі."""

from abc import ABC, abstractmethod
from uuid import UUID

from payments.domain.payment import Payment


class PaymentRepository(ABC):
    """Колекція платежів; на одне замовлення – не більше одного платежу."""

    @abstractmethod
    def find_by_order(self, order_id: UUID) -> Payment | None:
        """Повертає платіж за замовленням або None, якщо оплати ще не було."""

    @abstractmethod
    def save(self, payment: Payment) -> None:
        """Зберігає новий платіж."""