"""Заглушка платіжного шлюзу для ЛР 2: імітує LiqPay без мережевих викликів."""

from uuid import UUID

from ticketing.domain.exceptions import PaymentDeclinedError
from ticketing.domain.payment_gateway import PaymentGateway
from ticketing.domain.value_objects import Money


class StubPaymentGateway(PaymentGateway):
    """Приймає платежі й запам'ятовує їх; за потреби імітує відмову банку."""

    def __init__(self, decline: bool = False) -> None:
        self.decline = decline
        self.charges: list[tuple[UUID, Money]] = []

    def charge(self, order_id: UUID, amount: Money) -> None:
        if self.decline:
            raise PaymentDeclinedError("Банк відхилив платіж – спробуйте іншу картку.")
        self.charges.append((order_id, amount))