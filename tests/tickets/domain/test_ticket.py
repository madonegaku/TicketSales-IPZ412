"""Тести агрегату Ticket: видача за оплаченим замовленням, валідація (С-07) та повернення."""

from uuid import uuid4

import pytest

from tickets.domain.exceptions import (
    InvalidPaidOrderError,
    InvalidTicketError,
    TicketAlreadyUsedError,
)
from tickets.domain.paid_order import PaidOrder
from tickets.domain.ticket import Ticket, TicketStatus
from tickets.domain.value_objects import SeatPosition

EVENT_ID = uuid4()
A1 = SeatPosition("Партер", 1, 1)
A2 = SeatPosition("Партер", 1, 2)


def make_paid_order():
    return PaidOrder(uuid4(), EVENT_ID, (A1, A2))


def make_ticket():
    return Ticket.issue_for(make_paid_order())[0]


def test_one_ticket_with_unique_code_is_issued_per_seat():
    tickets = Ticket.issue_for(make_paid_order())

    assert {ticket.position for ticket in tickets} == {A1, A2}
    assert len({ticket.code for ticket in tickets}) == 2


@pytest.mark.parametrize("positions", [(), (A1, A1)])
def test_paid_order_without_seats_or_with_repeated_seat_is_rejected(positions):
    with pytest.raises(InvalidPaidOrderError):
        PaidOrder(uuid4(), EVENT_ID, positions)


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