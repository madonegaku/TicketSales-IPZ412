"""Тести сценаріїв CreatePayment і GetPayment: ідемпотентність, відмова банку, збій провайдера."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payments.application.create_payment import CreatePayment, CreatePaymentCommand
from payments.application.get_payment import GetPayment
from payments.domain.exceptions import (
    IdempotencyConflictError,
    NotFoundError,
    ProviderUnavailableError,
)
from payments.infrastructure.in_memory import InMemoryPaymentRepository
from payments.infrastructure.provider import StubPaymentProvider

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
ORDER_ID = uuid4()


@pytest.fixture
def payments():
    return InMemoryPaymentRepository()


def create(payments, provider):
    return CreatePayment(payments, provider, lambda: NOW)


def command(amount="1200.00"):
    return CreatePaymentCommand(ORDER_ID, Decimal(amount), "UAH")


def test_first_request_charges_once_and_saves_payment(payments):
    provider = StubPaymentProvider()

    result = create(payments, provider).execute(command())

    assert result.status == "succeeded"
    assert result.replayed is False
    assert len(provider.charges) == 1
    assert payments.find_by_order(ORDER_ID) is not None


def test_repeated_request_returns_saved_payment_without_second_charge(payments):
    provider = StubPaymentProvider()
    first = create(payments, provider).execute(command())

    second = create(payments, provider).execute(command("1200"))

    assert second.replayed is True
    assert second.payment_id == first.payment_id
    assert len(provider.charges) == 1


def test_repeated_request_with_other_amount_is_conflict(payments):
    provider = StubPaymentProvider()
    create(payments, provider).execute(command())

    with pytest.raises(IdempotencyConflictError):
        create(payments, provider).execute(command("1500.00"))

    assert len(provider.charges) == 1


def test_after_decline_new_attempt_is_allowed(payments):
    declined = create(payments, StubPaymentProvider(decline_reason="Недостатньо коштів")).execute(command())

    retry = create(payments, StubPaymentProvider()).execute(command())

    assert declined.status == "declined"
    assert retry.status == "succeeded"
    assert retry.replayed is False


def test_unavailable_provider_saves_nothing_and_retry_succeeds(payments):
    with pytest.raises(ProviderUnavailableError):
        create(payments, StubPaymentProvider(unavailable=True)).execute(command())

    assert payments.find_by_order(ORDER_ID) is None
    assert create(payments, StubPaymentProvider()).execute(command()).status == "succeeded"


def test_get_payment_returns_saved_payment(payments):
    created = create(payments, StubPaymentProvider()).execute(command())

    assert GetPayment(payments).execute(ORDER_ID).payment_id == created.payment_id


def test_get_payment_without_payment_is_not_found(payments):
    with pytest.raises(NotFoundError):
        GetPayment(payments).execute(uuid4())