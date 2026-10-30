"""Тести агрегату Ticket: видача, валідація (С-07) та повернення."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.domain.exceptions import (
    InvalidTicketError,
    OrderNotPaidError,
    TicketAlreadyUsedError,
)
from ticketing.domain.order import Order, OrderLine
from ticketing.domain.ticket import Ticket, TicketStatus
from ticketing.domain.value_objects import Money, SeatPosition

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
EVENT_ID = uuid4()
PRICE = Money(Decimal("600"))
A1 = SeatPosition("Партер", 1, 1)
A2 = SeatPosition("Партер", 1, 2)


def make_order():
    lines = (OrderLine(A1, PRICE), OrderLine(A2, PRICE))
    return Order(uuid4(), uuid4(), EVENT_ID, lines, NOW + timedelta(minutes=15))


def make_paid_order():
    order = make_order()
    order.start_payment(NOW)
    order.confirm_payment()
    return order


def make_ticket():
    return Ticket.issue_for(make_paid_order())[0]


def test_one_ticket_with_unique_code_is_issued_per_seat():
    tickets = Ticket.issue_for(make_paid_order())

    assert {ticket.position for ticket in tickets} == {A1, A2}
    assert len({ticket.code for ticket in tickets}) == 2


def test_tickets_are_not_issued_for_unpaid_order():
    with pytest.raises(OrderNotPaidError):
        Ticket.issue_for(make_order())


def test_valid_ticket_becomes_used_after_validation():
    ticket = make_ticket()

    ticket.validate(EVENT_ID)

    assert ticket.status is TicketStatus.USED


def test_used_ticket_is_rejected_on_second_scan():
    ticket = make_ticket()
    ticket.validate(EVENT_ID)

    with pytest.raises(TicketAlreadyUsedError):
        ticket.validate(EVENT_ID)


def test_ticket_for_another_event_is_rejected():
    ticket = make_ticket()

    with pytest.raises(InvalidTicketError):
        ticket.validate(uuid4())

    assert ticket.status is TicketStatus.VALID


def test_refunded_ticket_is_rejected_at_entrance():
    ticket = make_ticket()
    ticket.refund()

    with pytest.raises(InvalidTicketError):
        ticket.validate(EVENT_ID)


def test_used_ticket_cannot_be_refunded():
    ticket = make_ticket()
    ticket.validate(EVENT_ID)

    with pytest.raises(InvalidTicketError):
        ticket.refund()