"""Тести сценарію PayOrder: оплата й продаж місць (С-04, С-05). Квитки видає сервіс tickets."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.application.pay_order import PayOrder, PayOrderCommand
from sales.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from sales.domain.event import Event, PriceCategory, Seat, SeatStatus
from sales.domain.exceptions import (
    OrderAlreadyPaidError,
    PaymentDeclinedError,
    PaymentUnavailableError,
    ReservationExpiredError,
)
from sales.domain.order import OrderStatus
from sales.domain.value_objects import Money, SeatPosition
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
    InMemoryOutbox,
    InMemoryUnitOfWork,
)
from sales.infrastructure.payment import StubPaymentGateway

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
EVENT_ID = uuid4()
A1 = SeatPosition("Партер", 1, 1)
A2 = SeatPosition("Партер", 1, 2)


@pytest.fixture
def events():
    repository = InMemoryEventRepository()
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    seats = {A1: Seat(A1, "Партер"), A2: Seat(A2, "Партер")}
    repository.save(Event(EVENT_ID, "Концерт", NOW - timedelta(days=1), categories, seats, NOW + timedelta(days=30)))
    return repository


@pytest.fixture
def orders():
    return InMemoryOrderRepository()


@pytest.fixture
def gateway():
    return StubPaymentGateway()


@pytest.fixture
def order_id(events, orders):
    reserve_seats = ReserveSeats(events, InMemoryReservationRepository(), orders, lambda: NOW, InMemoryUnitOfWork())
    command = ReserveSeatsCommand(EVENT_ID, uuid4(), (("Партер", 1, 1), ("Партер", 1, 2)))
    return reserve_seats.execute(command).order_id


def make_pay_order(events, orders, gateway, minutes_later=1, outbox=None):
    outbox = outbox if outbox is not None else InMemoryOutbox()
    clock = lambda: NOW + timedelta(minutes=minutes_later)  # noqa: E731
    return PayOrder(events, orders, gateway, outbox, clock, InMemoryUnitOfWork())


def test_paid_order_sells_seats_and_is_charged(events, orders, gateway, order_id):
    pay_order = make_pay_order(events, orders, gateway)

    result = pay_order.execute(PayOrderCommand(order_id))

    assert result.order_id == order_id
    assert orders.get(order_id).status is OrderStatus.PAID
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.SOLD
    assert gateway.charges == [(order_id, Money(Decimal("1200")))]


def test_order_is_charged_only_once(events, orders, gateway, order_id):
    pay_order = make_pay_order(events, orders, gateway)
    pay_order.execute(PayOrderCommand(order_id))

    with pytest.raises(OrderAlreadyPaidError):
        pay_order.execute(PayOrderCommand(order_id))

    assert len(gateway.charges) == 1


def test_declined_payment_leaves_storage_unchanged(events, orders, order_id):
    pay_order = make_pay_order(events, orders, StubPaymentGateway(decline=True))

    with pytest.raises(PaymentDeclinedError):
        pay_order.execute(PayOrderCommand(order_id))

    assert orders.get(order_id).status is OrderStatus.AWAITING_PAYMENT
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.RESERVED


def test_expired_reservation_is_not_charged(events, orders, gateway, order_id):
    pay_order = make_pay_order(events, orders, gateway, minutes_later=16)

    with pytest.raises(ReservationExpiredError):
        pay_order.execute(PayOrderCommand(order_id))

    assert gateway.charges == []


def test_unavailable_payment_service_keeps_order_pending(events, orders, order_id):
    pay_order = make_pay_order(events, orders, StubPaymentGateway(unavailable=True))

    with pytest.raises(PaymentUnavailableError):
        pay_order.execute(PayOrderCommand(order_id))

    assert orders.get(order_id).status is OrderStatus.PAYMENT_PENDING
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.RESERVED


def test_payment_is_completed_on_retry_after_reservation_expires(events, orders, gateway, order_id):
    with pytest.raises(PaymentUnavailableError):
        make_pay_order(events, orders, StubPaymentGateway(unavailable=True)).execute(PayOrderCommand(order_id))

    make_pay_order(events, orders, gateway, minutes_later=20).execute(PayOrderCommand(order_id))

    assert orders.get(order_id).status is OrderStatus.PAID
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.SOLD
    assert len(gateway.charges) == 1


def test_paid_order_puts_order_paid_event_into_outbox(events, orders, gateway, order_id):
    outbox = InMemoryOutbox()

    make_pay_order(events, orders, gateway, outbox=outbox).execute(PayOrderCommand(order_id))

    [event] = outbox.pending()
    assert (event.order_id, event.event_id) == (order_id, EVENT_ID)
    assert set(event.seats) == {A1, A2}


def test_reservation_made_during_payment_call_is_not_overwritten(events, orders, order_id):
    """Поки триває виклик payments, інший покупець резервує вільне місце того самого заходу.

    Якщо PayOrder зберіг би копію заходу, прочитану до виклику, резервування сусіда зникло б,
    і місце продали б удруге (С-03). Тому після оплати захід перечитується.
    """
    a3 = SeatPosition("Партер", 1, 3)
    event = events.get(EVENT_ID)
    event.seats[a3] = Seat(a3, "Партер")
    events.save(event)
    neighbour = ReserveSeats(events, InMemoryReservationRepository(), orders, lambda: NOW, InMemoryUnitOfWork())

    class GatewayWithConcurrentBuyer(StubPaymentGateway):
        def charge(self, order_id, amount):
            neighbour.execute(ReserveSeatsCommand(EVENT_ID, uuid4(), (("Партер", 1, 3),)))
            super().charge(order_id, amount)

    make_pay_order(events, orders, GatewayWithConcurrentBuyer()).execute(PayOrderCommand(order_id))

    seats = events.get(EVENT_ID).seats
    assert (seats[A1].status, seats[A2].status) == (SeatStatus.SOLD, SeatStatus.SOLD)
    assert seats[a3].status is SeatStatus.RESERVED


@pytest.mark.parametrize("failing_gateway", [StubPaymentGateway(decline=True), StubPaymentGateway(unavailable=True)])
def test_failed_payment_puts_nothing_into_outbox(events, orders, order_id, failing_gateway):
    outbox = InMemoryOutbox()

    with pytest.raises((PaymentDeclinedError, PaymentUnavailableError)):
        make_pay_order(events, orders, failing_gateway, outbox=outbox).execute(PayOrderCommand(order_id))

    assert outbox.pending() == []