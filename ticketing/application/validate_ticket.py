"""Сценарій «Валідація квитка»: контролер сканує QR на вході."""

from dataclasses import dataclass
from uuid import UUID

from ticketing.domain.repositories import TicketRepository


@dataclass(frozen=True)
class ValidateTicketCommand:
    """Вхідні дані: код із QR і захід, на вході якого стоїть контролер."""

    code: str
    event_id: UUID


@dataclass(frozen=True)
class ValidateTicketResult:
    """Вихідні дані: місце, на яке пропущено відвідувача."""

    sector: str
    row: int
    number: int


class ValidateTicket:
    """Пропускає відвідувача за дійсним квитком; повторний QR відхиляється (С-07)."""

    def __init__(self, tickets: TicketRepository) -> None:
        self._tickets = tickets

    def execute(self, command: ValidateTicketCommand) -> ValidateTicketResult:
        ticket = self._tickets.get_by_code(command.code)
        ticket.validate(command.event_id)
        self._tickets.save(ticket)

        position = ticket.position
        return ValidateTicketResult(position.sector, position.row, position.number)