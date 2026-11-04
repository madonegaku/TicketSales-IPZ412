"""Тести сховища квитків у SQLite: збереження, пошук за замовленням, атомарність, перезапуск."""

import sqlite3
from uuid import uuid4

import pytest

from tickets.domain.exceptions import NotFoundError
from tickets.domain.paid_order import PaidOrder
from tickets.domain.ticket import Ticket, TicketStatus
from tickets.domain.value_objects import SeatPosition
from tickets.infrastructure.sqlite import SqliteTicketRepository

A1 = SeatPosition("Партер", 3, 7)
A2 = SeatPosition("Партер", 3, 8)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "tickets.sqlite3"


def issue_tickets():
    return Ticket.issue_for(PaidOrder(uuid4(), uuid4(), (A1, A2)))


def test_tickets_of_order_are_listed_in_issue_order(db_path):
    repository = SqliteTicketRepository(db_path)
    tickets = issue_tickets()

    repository.add_all(tickets)

    found = repository.list_by_order(tickets[0].order_id)
    assert [ticket.code for ticket in found] == [ticket.code for ticket in tickets]
    assert (found[0].position, found[0].status) == (A1, TicketStatus.VALID)
    assert repository.exists_for_order(tickets[0].order_id)
    assert not repository.exists_for_order(uuid4())


def test_used_ticket_stays_used_after_restart(db_path):
    tickets = issue_tickets()
    SqliteTicketRepository(db_path).add_all(tickets)
    ticket = SqliteTicketRepository(db_path).get_by_code(tickets[0].code)
    ticket.validate(ticket.event_id)

    SqliteTicketRepository(db_path).save(ticket)

    assert SqliteTicketRepository(db_path).get_by_code(ticket.code).status is TicketStatus.USED


def test_unknown_code_is_not_found(db_path):
    with pytest.raises(NotFoundError):
        SqliteTicketRepository(db_path).get_by_code("forged-code")


def test_tickets_of_order_are_added_all_or_nothing(db_path):
    repository = SqliteTicketRepository(db_path)
    first, second = issue_tickets()
    second.code = first.code

    with pytest.raises(sqlite3.IntegrityError):
        repository.add_all([first, second])

    assert not repository.exists_for_order(first.order_id)