"""Тести сценарію ValidateTicket: вхід за QR і повторне сканування (С-07)."""

from uuid import uuid4

import pytest

from ticketing.application.validate_ticket import ValidateTicket, ValidateTicketCommand
from ticketing.domain.exceptions import NotFoundError, TicketAlreadyUsedError
from ticketing.domain.ticket import Ticket, TicketStatus
from ticketing.domain.value_objects import SeatPosition
from ticketing.infrastructure.in_memory import InMemoryTicketRepository

EVENT_ID = uuid4()
CODE = "qr-test-code"


@pytest.fixture
def tickets():
    repository = InMemoryTicketRepository()
    repository.save(Ticket(uuid4(), uuid4(), EVENT_ID, SeatPosition("Партер", 5, 12), CODE))
    return repository


def test_valid_ticket_lets_visitor_in_and_becomes_used(tickets):
    result = ValidateTicket(tickets).execute(ValidateTicketCommand(CODE, EVENT_ID))

    assert (result.sector, result.row, result.number) == ("Партер", 5, 12)
    assert tickets.get_by_code(CODE).status is TicketStatus.USED


def test_second_scan_of_same_qr_is_rejected(tickets):
    validate_ticket = ValidateTicket(tickets)
    validate_ticket.execute(ValidateTicketCommand(CODE, EVENT_ID))

    with pytest.raises(TicketAlreadyUsedError):
        validate_ticket.execute(ValidateTicketCommand(CODE, EVENT_ID))


def test_unknown_qr_code_is_rejected(tickets):
    with pytest.raises(NotFoundError):
        ValidateTicket(tickets).execute(ValidateTicketCommand("forged-code", EVENT_ID))