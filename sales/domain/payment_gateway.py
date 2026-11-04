"""Інтерфейс платіжного шлюзу: що домену потрібно від зовнішньої платіжної системи."""

from abc import ABC, abstractmethod
from uuid import UUID

from sales.domain.value_objects import Money


class PaymentGateway(ABC):
    """Платіжний шлюз; у ЛР 3 – сервіс payments, доступний через HTTP."""

    @abstractmethod
    def charge(self, order_id: UUID, amount: Money) -> None:
        """Списує суму за замовлення.

        Кидає PaymentDeclinedError, якщо банк відхилив платіж, і PaymentUnavailableError,
        якщо платіжний сервіс не відповів або недоступний (результат оплати не підтверджено).
        """