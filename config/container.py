"""Єдина точка складання залежностей (composition root).

Тут – і лише тут – створюються конкретні реалізації інфраструктури
та передаються в сценарії використання. Жоден шар не створює їх самостійно.
У ЛР 5 достатньо буде замінити тут InMemory-репозиторії на Django ORM.
"""

from datetime import datetime, timezone

from ticketing.application.get_hall_layout import GetHallLayout
from ticketing.application.pay_order import PayOrder
from ticketing.application.reserve_seats import ReserveSeats
from ticketing.application.validate_ticket import ValidateTicket
from ticketing.infrastructure.demo_data import seed_demo_event
from ticketing.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
    InMemoryTicketRepository,
)
from ticketing.infrastructure.payment import StubPaymentGateway


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self) -> None:
        events = InMemoryEventRepository()
        reservations = InMemoryReservationRepository()
        orders = InMemoryOrderRepository()
        tickets = InMemoryTicketRepository()
        seed_demo_event(events)

        self.get_hall_layout = GetHallLayout(events)
        self.reserve_seats = ReserveSeats(events, reservations, orders, utc_now)
        self.pay_order = PayOrder(events, orders, tickets, StubPaymentGateway(), utc_now)
        self.validate_ticket = ValidateTicket(tickets)


container = Container()