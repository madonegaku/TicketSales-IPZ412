"""Тести сценаріїв IssueTickets і GetOrderTickets: видача за подією, ідемпотентність повторної доставки."""

from uuid import uuid4

from tickets.application.get_order_tickets import GetOrderTickets
from tickets.application.issue_tickets import IssueTickets, IssueTicketsCommand
from tickets.infrastructure.in_memory import InMemoryTicketRepository

ORDER_ID = uuid4()
EVENT_ID = uuid4()
SEATS = (("Партер", 3, 7), ("Партер", 3, 8))


def test_one_ticket_is_issued_per_seat():
    tickets = InMemoryTicketRepository()

    issued = IssueTickets(tickets).execute(IssueTicketsCommand(ORDER_ID, EVENT_ID, SEATS))

    views = GetOrderTickets(tickets).execute(ORDER_ID)
    assert issued == 2
    assert {(view.sector, view.row, view.number) for view in views} == set(SEATS)
    assert {view.status for view in views} == {"дійсний"}


def test_repeated_event_does_not_issue_tickets_twice():
    tickets = InMemoryTicketRepository()
    issue_tickets = IssueTickets(tickets)
    issue_tickets.execute(IssueTicketsCommand(ORDER_ID, EVENT_ID, SEATS))

    repeated = issue_tickets.execute(IssueTicketsCommand(ORDER_ID, EVENT_ID, SEATS))

    assert repeated == 0
    assert len(GetOrderTickets(tickets).execute(ORDER_ID)) == 2


def test_order_without_tickets_yet_gives_empty_list():
    assert GetOrderTickets(InMemoryTicketRepository()).execute(uuid4()) == []