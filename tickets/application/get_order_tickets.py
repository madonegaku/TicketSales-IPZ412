"""Запит «Квитки замовлення»: дані для сторінки «Мої квитки»."""

from dataclasses import dataclass
from uuid import UUID

from tickets.domain.repositories import TicketRepository


@dataclass(frozen=True)
class TicketView:
    """Квиток у вигляді, потрібному для відображення покупцеві."""

    code: str
    sector: str
    row: int
    number: int
    status: str


class GetOrderTickets:
    """Повертає квитки замовлення; порожній список – квитки ще не видано (подія в дорозі)."""

    def __init__(self, tickets: TicketRepository) -> None:
        self._tickets = tickets

    def execute(self, order_id: UUID) -> list[TicketView]:
        return [
            TicketView(
                ticket.code,
                ticket.position.sector,
                ticket.position.row,
                ticket.position.number,
                ticket.status.value,
            )
            for ticket in self._tickets.list_by_order(order_id)
        ]