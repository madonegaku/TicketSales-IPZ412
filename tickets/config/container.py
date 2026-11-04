"""Єдина точка складання залежностей сервісу tickets (composition root).

Тут – і лише тут – створюються конкретні реалізації інфраструктури
та передаються в сценарії використання.
"""

from tickets.application.validate_ticket import ValidateTicket
from tickets.infrastructure.in_memory import InMemoryTicketRepository


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self) -> None:
        tickets = InMemoryTicketRepository()

        self.validate_ticket = ValidateTicket(tickets)


container = Container()