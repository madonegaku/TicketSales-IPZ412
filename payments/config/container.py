"""Єдина точка складання залежностей сервісу payments (composition root)."""

from datetime import datetime, timezone

from django.conf import settings

from payments.application.create_payment import CreatePayment
from payments.application.get_payment import GetPayment
from payments.infrastructure.provider import StubPaymentProvider
from payments.infrastructure.sqlite import SqlitePaymentRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self) -> None:
        payments = SqlitePaymentRepository(settings.PAYMENTS_DB_PATH)
        provider = StubPaymentProvider(settings.PROVIDER_DECLINE_REASON, settings.PROVIDER_UNAVAILABLE)

        self.create_payment = CreatePayment(payments, provider, utc_now)
        self.get_payment = GetPayment(payments)


container = Container()