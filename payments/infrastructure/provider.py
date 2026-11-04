"""Імітація платіжного провайдера для ЛР 3; інтеграція з LiqPay – поза межами роботи."""

from uuid import UUID

from payments.domain.exceptions import ProviderUnavailableError
from payments.domain.payment_provider import PaymentProvider, ProviderResult
from payments.domain.value_objects import Money


class StubPaymentProvider(PaymentProvider):
    """decline_reason – відхиляти платежі з цією причиною; unavailable – імітувати збій провайдера.

    Кожне звернення, що дійшло до «банку», записується в charges – тести перевіряють за ним,
    скільки разів насправді списувалися кошти.
    """

    def __init__(self, decline_reason: str | None = None, unavailable: bool = False) -> None:
        self.decline_reason = decline_reason
        self.unavailable = unavailable
        self.charges: list[tuple[UUID, Money]] = []

    def charge(self, order_id: UUID, amount: Money) -> ProviderResult:
        if self.unavailable:
            raise ProviderUnavailableError("Платіжний провайдер недоступний – кошти не списано.")
        self.charges.append((order_id, amount))
        if self.decline_reason:
            return ProviderResult(False, self.decline_reason)
        return ProviderResult(True)