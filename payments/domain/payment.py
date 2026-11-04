"""Платіж: факт списання коштів (або відмови) за замовлення."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from payments.domain.exceptions import IdempotencyConflictError, InvalidPaymentError
from payments.domain.value_objects import Money


class PaymentStatus(Enum):
    """Результат платежу; значення збігаються з полем status у контракті."""

    SUCCEEDED = "succeeded"
    DECLINED = "declined"


@dataclass(eq=False)
class Payment:
    """Платіж – агрегат сервісу payments.

    Інваріанти: сума більша за нуль; відхилений платіж має причину відмови, успішний – ні;
    на одне замовлення – не більше одного платежу, повторний запит із тим самим order_id
    приймається лише з тією самою сумою й валютою (С-04, С-05).
    """

    id: UUID
    order_id: UUID
    amount: Money
    status: PaymentStatus
    created_at: datetime
    decline_reason: str | None = None

    def __post_init__(self) -> None:
        if self.amount.amount <= 0:
            raise InvalidPaymentError("Сума платежу має бути більшою за нуль.")
        if self.status is PaymentStatus.DECLINED and not self.decline_reason:
            raise InvalidPaymentError("Відхилений платіж має містити причину відмови.")
        if self.status is PaymentStatus.SUCCEEDED and self.decline_reason:
            raise InvalidPaymentError("Успішний платіж не може мати причини відмови.")

    @classmethod
    def succeeded(cls, order_id: UUID, amount: Money, now: datetime) -> "Payment":
        return cls(uuid4(), order_id, amount, PaymentStatus.SUCCEEDED, now)

    @classmethod
    def declined(cls, order_id: UUID, amount: Money, reason: str, now: datetime) -> "Payment":
        return cls(uuid4(), order_id, amount, PaymentStatus.DECLINED, now, reason)

    @property
    def is_final(self) -> bool:
        """Успішний платіж остаточний: повтор лише повертає його. Після відмови дозволено нову спробу."""
        return self.status is PaymentStatus.SUCCEEDED

    def ensure_same_request(self, amount: Money) -> None:
        """Повтор запиту з тим самим order_id допустимий лише з тією самою сумою й валютою."""
        if amount != self.amount:
            raise IdempotencyConflictError(
                "Замовлення вже оплачувалося на іншу суму – повторний запит відхилено."
            )