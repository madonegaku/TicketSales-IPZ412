"""Репозиторій квитків у пам'яті – тимчасова реалізація до власного сховища SQLite.

Зберігає копії агрегатів: як і справжнє сховище, бачить зміни лише після save().
"""

from copy import deepcopy
from uuid import UUID

from tickets.domain.exceptions import NotFoundError
from tickets.domain.repositories import TicketRepository
from tickets.domain.ticket import Ticket


class InMemoryTicketRepository(TicketRepository):
    """Квитки у словнику за кодом із QR."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}

    def get_by_code(self, code: str) -> Ticket:
        if code not in self._tickets:
            raise NotFoundError("Квиток не знайдено.")
        return deepcopy(self._tickets[code])

    def save(self, ticket: Ticket) -> None:
        self._tickets[ticket.code] = deepcopy(ticket)

    def add_all(self, tickets: list[Ticket]) -> None:
        for ticket in tickets:
            self._tickets[ticket.code] = deepcopy(ticket)

    def exists_for_order(self, order_id: UUID) -> bool:
        return any(ticket.order_id == order_id for ticket in self._tickets.values())

    def list_by_order(self, order_id: UUID) -> list[Ticket]:
        return [deepcopy(ticket) for ticket in self._tickets.values() if ticket.order_id == order_id]