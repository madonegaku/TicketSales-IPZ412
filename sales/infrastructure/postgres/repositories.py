"""Репозиторії sales у PostgreSQL – реалізації доменних інтерфейсів (ЛР 5).

Кожен репозиторій перетворює агрегат на рядки своїх таблиць і назад (схема –
migrations/0001_initial.sql). Домен про SQL не знає: змінюється лише інфраструктура й
складання в composition.py (ADR-003). Стани зберігаються назвами елементів enum
(AVAILABLE, PAID), а не їхніми значеннями – текстом для інтерфейсу.
"""

from datetime import datetime
from uuid import UUID

from sales.domain.event import Event, PriceCategory, Seat, SeatStatus
from sales.domain.exceptions import NotFoundError
from sales.domain.order import Order, OrderLine
from sales.domain.order_state import OrderStatus
from sales.domain.repositories import EventRepository, OrderRepository, ReservationRepository
from sales.domain.reservation import RESERVATION_TTL, Reservation
from sales.domain.value_objects import Money, SeatPosition
from sales.infrastructure.postgres.database import Database

UPSERT_EVENT = """
INSERT INTO events (id, title, sales_start, starts_at) VALUES (%s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET title = excluded.title, sales_start = excluded.sales_start,
                               starts_at = excluded.starts_at
"""
UPSERT_CATEGORY = """
INSERT INTO price_categories (event_id, name, price_amount, price_currency) VALUES (%s, %s, %s, %s)
ON CONFLICT (event_id, name) DO UPDATE SET price_amount = excluded.price_amount,
                                           price_currency = excluded.price_currency
"""
UPSERT_SEAT = """
INSERT INTO seats (event_id, sector, seat_row, seat_number, ordinal, category, status)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id, sector, seat_row, seat_number) DO UPDATE SET status = excluded.status
"""


class PostgresEventRepository(EventRepository):
    """Заходи: таблиця events, цінові категорії й місця – частини агрегату Event."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, event_id: UUID) -> Event:
        return self._load(event_id, lock=False)

    def get_for_update(self, event_id: UUID) -> Event:
        """SELECT … FOR UPDATE на рядку events: усі сценарії, що змінюють місця заходу, блокують
        цей рядок першими, тож змінюють місця одного заходу по черзі (С-03)."""
        return self._load(event_id, lock=True)

    def _load(self, event_id: UUID, lock: bool) -> Event:
        sql = "SELECT id, title, sales_start, starts_at FROM events WHERE id = %s" + (" FOR UPDATE" if lock else "")
        with self._db.connection() as connection:
            row = connection.execute(sql, (event_id,)).fetchone()
            if row is None:
                raise NotFoundError("Захід не знайдено.")
            categories = connection.execute(
                "SELECT name, price_amount, price_currency FROM price_categories WHERE event_id = %s", (event_id,)
            ).fetchall()
            seats = connection.execute(
                "SELECT sector, seat_row, seat_number, category, status FROM seats "
                "WHERE event_id = %s ORDER BY ordinal",
                (event_id,),
            ).fetchall()
        return to_event(row, categories, seats)

    def save(self, event: Event) -> None:
        with self._db.connection() as connection, connection.cursor() as cursor:
            cursor.execute(UPSERT_EVENT, (event.id, event.title, event.sales_start, event.starts_at))
            cursor.executemany(
                UPSERT_CATEGORY,
                [(event.id, c.name, c.price.amount, c.price.currency) for c in event.categories.values()],
            )
            cursor.executemany(
                UPSERT_SEAT,
                [
                    (event.id, s.position.sector, s.position.row, s.position.number, ordinal, s.category, s.status.name)
                    for ordinal, s in enumerate(event.seats.values())
                ],
            )


def to_event(row: tuple, categories: list[tuple], seats: list[tuple]) -> Event:
    event_id, title, sales_start, starts_at = row
    return Event(
        event_id,
        title,
        sales_start,
        {name: PriceCategory(name, Money(amount, currency)) for name, amount, currency in categories},
        {
            SeatPosition(sector, seat_row, number): Seat(SeatPosition(sector, seat_row, number), category, SeatStatus[status])
            for sector, seat_row, number, category, status in seats
        },
        starts_at,
    )


class PostgresReservationRepository(ReservationRepository):
    """Резервування: таблиця reservations і місця резервування в reservation_seats.

    Резервування після створення не змінюється, тож повторне save() нічого не перезаписує.
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    def save(self, reservation: Reservation) -> None:
        with self._db.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO reservations (id, event_id, buyer_id, created_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (reservation.id, reservation.event_id, reservation.buyer_id, reservation.created_at),
            )
            cursor.executemany(
                "INSERT INTO reservation_seats (reservation_id, line_no, sector, seat_row, seat_number) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [(reservation.id, n, p.sector, p.row, p.number) for n, p in enumerate(reservation.positions)],
            )

    def count_seats_held(self, buyer_id: UUID, event_id: UUID, now: datetime) -> int:
        """Непрострочене резервування: now < created_at + TTL, тобто created_at > now − TTL (С-06)."""
        with self._db.connection() as connection:
            row = connection.execute(
                "SELECT count(*) FROM reservation_seats s JOIN reservations r ON r.id = s.reservation_id "
                "WHERE r.buyer_id = %s AND r.event_id = %s AND r.created_at > %s",
                (buyer_id, event_id, now - RESERVATION_TTL),
            ).fetchone()
        return row[0]


class PostgresOrderRepository(OrderRepository):
    """Замовлення: таблиця orders і рядки з цінами в order_lines (рядки після створення не змінюються)."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, order_id: UUID) -> Order:
        return self._load(order_id, lock=False)

    def get_for_update(self, order_id: UUID) -> Order:
        """SELECT … FOR UPDATE: два одночасні запити оплати одного замовлення виконуються по черзі."""
        return self._load(order_id, lock=True)

    def _load(self, order_id: UUID, lock: bool) -> Order:
        sql = "SELECT id, reservation_id, event_id, payment_deadline, status FROM orders WHERE id = %s"
        with self._db.connection() as connection:
            row = connection.execute(sql + (" FOR UPDATE" if lock else ""), (order_id,)).fetchone()
            if row is None:
                raise NotFoundError("Замовлення не знайдено.")
            lines = connection.execute(
                "SELECT sector, seat_row, seat_number, price_amount, price_currency FROM order_lines "
                "WHERE order_id = %s ORDER BY line_no",
                (order_id,),
            ).fetchall()
        return to_order(row, lines)

    def save(self, order: Order) -> None:
        with self._db.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO orders (id, reservation_id, event_id, payment_deadline, status) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET status = excluded.status",
                (order.id, order.reservation_id, order.event_id, order.payment_deadline, order.status.name),
            )
            cursor.executemany(
                "INSERT INTO order_lines (order_id, line_no, sector, seat_row, seat_number, price_amount, "
                "price_currency) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [
                    (order.id, n, line.position.sector, line.position.row, line.position.number,
                     line.price.amount, line.price.currency)
                    for n, line in enumerate(order.lines)
                ],
            )


def to_order(row: tuple, lines: list[tuple]) -> Order:
    order_id, reservation_id, event_id, payment_deadline, status = row
    return Order(
        order_id,
        reservation_id,
        event_id,
        tuple(
            OrderLine(SeatPosition(sector, seat_row, number), Money(amount, currency))
            for sector, seat_row, number, amount, currency in lines
        ),
        payment_deadline,
        OrderStatus[status],
    )
