"""Інтерфейс платіжного шлюзу: що домену потрібно від зовнішньої платіжної системи."""

from abc import ABC, abstractmethod
from uuid import UUID

from ticketing.domain.value_objects import Money


class PaymentGateway(ABC):
    """Платіжний шлюз (у реальній системі – LiqPay)."""

    @abstractmethod
    def charge(self, order_id: UUID, amount: Money) -> None:
        """Списує суму за замовлення; якщо платіж відхилено – кидає PaymentDeclinedError."""