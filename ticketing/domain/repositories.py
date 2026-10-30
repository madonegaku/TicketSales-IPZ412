"""Інтерфейси репозиторіїв: колекції агрегатів у термінах предметної області.

Домен лише оголошує, що йому потрібно; реалізації – в інфраструктурному шарі
(у ЛР 2 – у пам'яті, у ЛР 5 – Django ORM і PostgreSQL).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ticketing.domain.event import Event
from ticketing.domain.order import Order
from ticketing.domain.reservation import Reservation
from ticketing.domain.ticket import Ticket


class EventRepository(ABC):
    """Колекція заходів."""

    @abstractmethod
    def get(self, event_id: UUID) -> Event:
        """Повертає захід; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def save(self, event: Event) -> None:
        """Зберігає захід разом зі станом його місць."""


class ReservationRepository(ABC):
    """Колекція резервувань."""

    @abstractmethod
    def save(self, reservation: Reservation) -> None:
        """Додає нове або оновлює наявне резервування."""

    @abstractmethod
    def count_seats_held(self, buyer_id: UUID, event_id: UUID, now: datetime) -> int:
        """Кількість місць у непрострочених резервуваннях покупця на захід (С-06)."""


class OrderRepository(ABC):
    """Колекція замовлень."""

    @abstractmethod
    def get(self, order_id: UUID) -> Order:
        """Повертає замовлення; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def save(self, order: Order) -> None:
        """Додає нове або оновлює наявне замовлення."""


class TicketRepository(ABC):
    """Колекція квитків."""

    @abstractmethod
    def get_by_code(self, code: str) -> Ticket:
        """Повертає квиток за кодом із QR; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def save(self, ticket: Ticket) -> None:
        """Додає новий або оновлює наявний квиток."""