"""Контракт репозиторіїв sales: однакові тести для реалізації в пам'яті й у PostgreSQL.

Якщо реалізація в PostgreSQL проходить ті самі тести, що й у пам'яті, сценарії та домен
можна перевести на неї без змін (ADR-003). PostgreSQL-варіант потребує контейнера sales-db,
інакше пропускається.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.domain.event import SeatStatus
from sales.domain.event_builder import EventBuilder
from sales.domain.exceptions import NotFoundError
from sales.domain.order import Order
from sales.domain.order_state import OrderStatus
from sales.domain.repositories import EventRepository, OrderRepository, ReservationRepository
from sales.domain.reservation import Reservation
from sales.domain.value_objects import Money, SeatPosition
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
)

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
VIP1, P1, P2 = SeatPosition("VIP", 1, 1), SeatPosition("Партер", 1, 1), SeatPosition("Партер", 1, 2)


@dataclass
class Storage:
    events: EventRepository
    reservations: ReservationRepository
    orders: OrderRepository
    database: object = None


@pytest.fixture(params=["memory", "postgres"])
def storage(request):
    if request.param == "memory":
        yield Storage(InMemoryEventRepository(), InMemoryReservationRepository(), InMemoryOrderRepository())
        return
    conninfo = request.getfixturevalue("pg_conninfo")
    from sales.infrastructure.postgres.database import Database
    from sales.infrastructure.postgres.migrate import migrate_database
    from sales.infrastructure.postgres.repositories import (
        PostgresEventRepository,
        PostgresOrderRepository,
        PostgresReservationRepository,
    )

    migrate_database(conninfo)
    database = Database(conninfo, max_size=2)
    try:
        yield Storage(
            PostgresEventRepository(database),
            PostgresReservationRepository(database),
            PostgresOrderRepository(database),
            database,
        )
    finally:
        database.close()


def make_event():
    """VIP додано першим: порядок місць – порядок додавання, а не алфавіт («VIP» < «Партер»)."""
    return (
        EventBuilder(uuid4(), "Концерт")
        .sales_start(NOW - timedelta(days=1))
        .starts_at(NOW + timedelta(days=30))
        .category("VIP", Money(Decimal("1500")))
        .category("Партер", Money(Decimal("600.50")))
        .seats("VIP", rows=[1], numbers=[1])
        .seats("Партер", rows=[1], numbers=[1, 2])
        .build()
    )


def test_event_round_trip_keeps_categories_seat_order_and_dates(storage):
    event = make_event()

    storage.events.save(event)
    loaded = storage.events.get(event.id)

    assert (loaded.title, loaded.sales_start, loaded.starts_at) == (event.title, event.sales_start, event.starts_at)
    assert list(loaded.seats) == [VIP1, P1, P2]
    assert loaded.price_of(P1) == Money(Decimal("600.50"))
    assert {seat.status for seat in loaded.seats.values()} == {SeatStatus.AVAILABLE}


def test_saved_seat_statuses_are_returned(storage):
    event = make_event()
    storage.events.save(event)

    event.reserve_seats([P1, P2], NOW)
    event.sell_seats([P2])
    storage.events.save(event)

    statuses = {position: seat.status for position, seat in storage.events.get(event.id).seats.items()}
    assert statuses == {VIP1: SeatStatus.AVAILABLE, P1: SeatStatus.RESERVED, P2: SeatStatus.SOLD}


def test_changes_are_not_stored_without_save(storage):
    event = make_event()
    storage.events.save(event)

    storage.events.get(event.id).reserve_seats([P1], NOW)

    assert storage.events.get(event.id).seats[P1].status is SeatStatus.AVAILABLE


def test_missing_event_and_order_raise_not_found(storage):
    with pytest.raises(NotFoundError):
        storage.events.get(uuid4())
    with pytest.raises(NotFoundError):
        storage.orders.get(uuid4())


def test_count_seats_held_ignores_expired_reservations_other_buyers_and_events(storage):
    event, other_event = make_event(), make_event()
    storage.events.save(event)
    storage.events.save(other_event)
    buyer = uuid4()
    storage.reservations.save(Reservation.create(event.id, buyer, [P1, P2], NOW, 0))
    storage.reservations.save(Reservation.create(event.id, uuid4(), [VIP1], NOW, 0))
    storage.reservations.save(Reservation.create(other_event.id, buyer, [VIP1], NOW, 0))
    storage.reservations.save(Reservation.create(event.id, buyer, [VIP1], NOW - timedelta(minutes=15), 0))

    assert storage.reservations.count_seats_held(buyer, event.id, NOW) == 2


def test_order_round_trip_keeps_lines_prices_and_status(storage):
    event = make_event()
    storage.events.save(event)
    reservation = Reservation.create(event.id, uuid4(), [P2, VIP1], NOW, 0)
    storage.reservations.save(reservation)
    order = Order.for_reservation(reservation, event)
    storage.orders.save(order)

    order.start_payment(NOW)
    storage.orders.save(order)
    loaded = storage.orders.get(order.id)

    assert [line.position for line in loaded.lines] == [P2, VIP1]
    assert loaded.total == Money(Decimal("2100.50"))
    assert (loaded.status, loaded.payment_deadline) == (OrderStatus.PAYMENT_PENDING, order.payment_deadline)
    assert (loaded.reservation_id, loaded.event_id) == (reservation.id, event.id)


def test_postgres_transaction_is_rolled_back_on_error(storage):
    if storage.database is None:
        pytest.skip("транзакції є лише в PostgreSQL")
    event = make_event()

    with pytest.raises(RuntimeError), storage.database.transaction():
        storage.events.save(event)
        raise RuntimeError("збій посеред сценарію")

    with pytest.raises(NotFoundError):
        storage.events.get(event.id)
