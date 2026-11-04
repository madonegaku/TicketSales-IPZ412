"""Репозиторій квитків у пам'яті – тимчасова реалізація до власного сховища SQLite.

Зберігає копії агрегатів: як і справжнє сховище, бачить зміни лише після save().
"""

from copy import deepcopy

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