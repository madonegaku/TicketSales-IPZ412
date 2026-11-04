"""Інтерфейси репозиторіїв: колекції агрегатів у термінах предметної області.

Домен лише оголошує, що йому потрібно; реалізації – в інфраструктурному шарі
(у ЛР 2 – у пам'яті, у ЛР 5 – PostgreSQL).

get_for_update() – завантаження агрегату, який сценарій збирається змінити: у PostgreSQL
рядок блокується до кінця транзакції, тож два одночасні сценарії змінюють агрегат по черзі,
а не затирають зміни один одного (С-03 – жодного подвійного продажу місця).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sales.domain.event import Event
from sales.domain.order import Order
from sales.domain.reservation import Reservation


class EventRepository(ABC):
    """Колекція заходів."""

    @abstractmethod
    def get(self, event_id: UUID) -> Event:
        """Повертає захід; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def list_all(self) -> list[Event]:
        """Усі заходи за часом початку (афіша)."""

    @abstractmethod
    def get_for_update(self, event_id: UUID) -> Event:
        """Як get(), але захід заблоковано для змін іншими сценаріями до кінця транзакції."""

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
    def list_by_buyer(self, buyer_id: UUID) -> list[Order]:
        """Замовлення покупця, новіші першими."""

    @abstractmethod
    def list_by_event(self, event_id: UUID) -> list[Order]:
        """Усі замовлення заходу – для статистики продажу організатора."""

    @abstractmethod
    def get_for_update(self, order_id: UUID) -> Order:
        """Як get(), але замовлення заблоковано для змін іншими сценаріями до кінця транзакції."""

    @abstractmethod
    def save(self, order: Order) -> None:
        """Додає нове або оновлює наявне замовлення."""
