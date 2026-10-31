"""Тести сценарію PayOrder: оплата, продаж місць, видача квитків (С-04, С-05)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.application.pay_order import PayOrder, PayOrderCommand
from ticketing.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from ticketing.domain.event import Event, PriceCategory, Seat, SeatStatus
from ticketing.domain.exceptions import (
    OrderAlreadyPaidError,
    PaymentDeclinedError,
    ReservationExpiredError,
)
from ticketing.domain.order import OrderStatus
from ticketing.domain.value_objects import Money, SeatPosition
from ticketing.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
    InMemoryTicketRepository,
)
from ticketing.infrastructure.payment import StubPaymentGateway

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
EVENT_ID = uuid4()
A1 = SeatPosition("Партер", 1, 1)
A2 = SeatPosition("Партер", 1, 2)


@pytest.fixture
def events():
    repository = InMemoryEventRepository()
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    seats = {A1: Seat(A1, "Партер"), A2: Seat(A2, "Партер")}
    repository.save(Event(EVENT_ID, "Концерт", NOW - timedelta(days=1), categories, seats))
    return repository


@pytest.fixture
def orders():
    return InMemoryOrderRepository()


@pytest.fixture
def tickets():
    return InMemoryTicketRepository()


@pytest.fixture
def gateway():
    return StubPaymentGateway()


@pytest.fixture
def order_id(events, orders):
    reserve_seats = ReserveSeats(events, InMemoryReservationRepository(), orders, lambda: NOW)
    command = ReserveSeatsCommand(EVENT_ID, uuid4(), (("Партер", 1, 1), ("Партер", 1, 2)))
    return reserve_seats.execute(command).order_id


def make_pay_order(events, orders, tickets, gateway, minutes_later=1):
    return PayOrder(
        events, orders, tickets, gateway, lambda: NOW + timedelta(minutes=minutes_later)
    )


def test_paid_order_sells_seats_and_issues_tickets(events, orders, tickets, gateway, order_id):
    pay_order = make_pay_order(events, orders, tickets, gateway)

    result = pay_order.execute(PayOrderCommand(order_id))

    assert len(result.ticket_codes) == 2
    assert {tickets.get_by_code(code).position for code in result.ticket_codes} == {A1, A2}
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.SOLD
    assert gateway.charges == [(order_id, Money(Decimal("1200")))]


def test_order_is_charged_only_once(events, orders, tickets, gateway, order_id):
    pay_order = make_pay_order(events, orders, tickets, gateway)
    pay_order.execute(PayOrderCommand(order_id))

    with pytest.raises(OrderAlreadyPaidError):
        pay_order.execute(PayOrderCommand(order_id))

    assert len(gateway.charges) == 1


def test_declined_payment_leaves_storage_unchanged(events, orders, tickets, order_id):
    pay_order = make_pay_order(events, orders, tickets, StubPaymentGateway(decline=True))

    with pytest.raises(PaymentDeclinedError):
        pay_order.execute(PayOrderCommand(order_id))

    assert orders.get(order_id).status is OrderStatus.AWAITING_PAYMENT
    assert events.get(EVENT_ID).seats[A1].status is SeatStatus.RESERVED


def test_expired_reservation_is_not_charged(events, orders, tickets, gateway, order_id):
    pay_order = make_pay_order(events, orders, tickets, gateway, minutes_later=16)

    with pytest.raises(ReservationExpiredError):
        pay_order.execute(PayOrderCommand(order_id))

    assert gateway.charges == []