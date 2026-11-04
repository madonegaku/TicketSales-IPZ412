"""Сценарій «Видати квитки за оплаченим замовленням» – реакція tickets на подію OrderPaid."""

from dataclasses import dataclass
from uuid import UUID

from tickets.domain.exceptions import TicketsAlreadyIssuedError
from tickets.domain.paid_order import PaidOrder
from tickets.domain.repositories import TicketRepository
from tickets.domain.ticket import Ticket
from tickets.domain.value_objects import SeatPosition


@dataclass(frozen=True)
class IssueTicketsCommand:
    """Вхідні дані з події OrderPaid: замовлення, захід і місця (сектор, ряд, номер)."""

    order_id: UUID
    event_id: UUID
    seats: tuple[tuple[str, int, int], ...]


class IssueTickets:
    """Видає по квитку на кожне місце оплаченого замовлення.

    Ідемпотентність за ключем order_id: подія може надійти повторно (доставка «щонайменше один
    раз»; та сама подія вдруге з outbox після збою sales до позначки «опубліковано»), тож якщо
    квитки за замовленням уже видано, повторна обробка нічого не змінює. Ключ – саме замовлення,
    а не message_id: повтор із новим ідентифікатором повідомлення теж розпізнається.
    Два рівні захисту: перевірка exists_for_order (швидкий шлях) і унікальність квитка на місце
    замовлення в сховищі – на випадок, коли дві обробки однієї події пройшли перевірку одночасно.
    Квитки замовлення зберігаються атомарно.
    """

    def __init__(self, tickets: TicketRepository) -> None:
        self._tickets = tickets

    def execute(self, command: IssueTicketsCommand) -> int:
        """Повертає кількість виданих квитків; 0 – подію вже оброблено раніше."""
        if self._tickets.exists_for_order(command.order_id):
            return 0
        positions = tuple(SeatPosition(*seat) for seat in command.seats)
        tickets = Ticket.issue_for(PaidOrder(command.order_id, command.event_id, positions))
        try:
            self._tickets.add_all(tickets)
        except TicketsAlreadyIssuedError:
            return 0
        return len(tickets)