"""Сценарій «Створити платіж»: списання коштів за замовлення з ідемпотентністю за order_id."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from payments.application.dto import PaymentResult, to_result
from payments.domain.payment import Payment
from payments.domain.payment_provider import PaymentProvider
from payments.domain.repositories import PaymentRepository
from payments.domain.value_objects import Money


@dataclass(frozen=True)
class CreatePaymentCommand:
    """Вхідні дані: замовлення (ключ ідемпотентності), сума й валюта."""

    order_id: UUID
    amount: Decimal
    currency: str


class CreatePayment:
    """Списує кошти за замовлення не більше одного разу.

    Повторний запит із тим самим order_id після успішного платежу до провайдера не звертається:
    повертається збережений платіж, а за іншої суми – IdempotencyConflictError. Після відмови
    провайдера дозволено нову спробу. Якщо провайдер недоступний (ProviderUnavailableError),
    нічого не зберігається – кошти не списано, запит можна повторити.
    """

    def __init__(
        self,
        payments: PaymentRepository,
        provider: PaymentProvider,
        clock: Callable[[], datetime],
    ) -> None:
        self._payments = payments
        self._provider = provider
        self._clock = clock

    def execute(self, command: CreatePaymentCommand) -> PaymentResult:
        amount = Money(command.amount, command.currency)
        existing = self._payments.find_by_order(command.order_id)
        if existing is not None:
            existing.ensure_same_request(amount)
            if existing.is_final:
                return to_result(existing, replayed=True)

        outcome = self._provider.charge(command.order_id, amount)
        if outcome.succeeded:
            payment = Payment.succeeded(command.order_id, amount, self._clock())
        else:
            payment = Payment.declined(command.order_id, amount, outcome.decline_reason, self._clock())
        self._payments.save(payment)
        return to_result(payment, replayed=False)