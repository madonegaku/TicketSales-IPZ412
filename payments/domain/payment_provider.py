"""Інтерфейс зовнішнього платіжного провайдера (у реальній системі – LiqPay)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from payments.domain.value_objects import Money


@dataclass(frozen=True)
class ProviderResult:
    """Відповідь провайдера: успіх або причина відмови."""

    succeeded: bool
    decline_reason: str | None = None


class PaymentProvider(ABC):
    """Списує кошти в банку покупця."""

    @abstractmethod
    def charge(self, order_id: UUID, amount: Money) -> ProviderResult:
        """Списує кошти; якщо провайдер недоступний – кидає ProviderUnavailableError."""