"""Єдина точка складання залежностей сервісу tickets (composition root).

Тут – і лише тут – створюються конкретні реалізації інфраструктури
та передаються в сценарії використання.
"""

import redis
from django.conf import settings

from tickets.application.get_order_tickets import GetOrderTickets
from tickets.application.issue_tickets import IssueTickets
from tickets.application.validate_ticket import ValidateTicket
from tickets.infrastructure.order_paid_consumer import OrderPaidConsumer
from tickets.infrastructure.sqlite import SqliteTicketRepository


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self) -> None:
        tickets = SqliteTicketRepository(settings.TICKETS_DB_PATH)

        self.validate_ticket = ValidateTicket(tickets)
        self.get_order_tickets = GetOrderTickets(tickets)
        # socket_timeout більший за блокування XREADGROUP (5 с), інакше очікування подій обірветься помилкою.
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=10
        )
        self.order_paid_consumer = OrderPaidConsumer(redis_client, IssueTickets(tickets))


container = Container()