"""Заглушка платіжного шлюзу: імітує сервіс payments без мережевих викликів (для тестів)."""

from uuid import UUID

from sales.domain.exceptions import PaymentDeclinedError, PaymentUnavailableError
from sales.domain.payment_gateway import PaymentGateway
from sales.domain.value_objects import Money


class StubPaymentGateway(PaymentGateway):
    """Приймає платежі й запам'ятовує їх; за потреби імітує відмову банку чи недоступність сервісу."""

    def __init__(self, decline: bool = False, unavailable: bool = False) -> None:
        self.decline = decline
        self.unavailable = unavailable
        self.charges: list[tuple[UUID, Money]] = []

    def charge(self, order_id: UUID, amount: Money) -> None:
        if self.unavailable:
            raise PaymentUnavailableError("Платіжний сервіс не відповів – оплата обробляється, спробуйте ще раз.")
        if self.decline:
            raise PaymentDeclinedError("Банк відхилив платіж – спробуйте іншу картку.")
        self.charges.append((order_id, amount))