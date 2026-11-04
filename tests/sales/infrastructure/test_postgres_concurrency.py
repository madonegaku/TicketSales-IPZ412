"""Одночасні сценарії на справжньому PostgreSQL: жодного подвійного продажу місця (С-03).

Два покупці в двох потоках одночасно резервують те саме місце. Щоб гонитва справді
відбулася, лічильник ліміту С-06 навмисно сповільнено: обидва потоки встигають прочитати
захід, перш ніж будь-який збереже зміни. З блокуванням FOR UPDATE другий потік чекає, доки
перший зафіксує транзакцію, і бачить місце вже зайнятим. Без блокування обидва побачили б
місце вільним і обидва його зарезервували б.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from sales.application.reserve_seats import ReserveSeats, ReserveSeatsCommand  # noqa: E402
from sales.domain.event import SeatStatus  # noqa: E402
from sales.domain.event_builder import EventBuilder  # noqa: E402
from sales.domain.exceptions import SeatNotAvailableError  # noqa: E402
from sales.domain.value_objects import Money, SeatPosition  # noqa: E402
from sales.infrastructure.hall_layout_cache import NoHallLayoutCache  # noqa: E402
from sales.infrastructure.postgres.database import Database  # noqa: E402
from sales.infrastructure.postgres.migrate import migrate_database  # noqa: E402
from sales.infrastructure.postgres.repositories import (  # noqa: E402
    PostgresEventRepository,
    PostgresOrderRepository,
    PostgresReservationRepository,
)
from sales.infrastructure.postgres.unit_of_work import PostgresUnitOfWork  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
SEAT = SeatPosition("Партер", 1, 1)


class SlowReservationRepository(PostgresReservationRepository):
    """Лічильник ліміту з паузою: розширює вікно між читанням заходу та збереженням."""

    def count_seats_held(self, buyer_id, event_id, now):
        held = super().count_seats_held(buyer_id, event_id, now)
        time.sleep(0.3)
        return held


@pytest.fixture
def database(pg_conninfo):
    migrate_database(pg_conninfo)
    database = Database(pg_conninfo, max_size=4)
    yield database
    database.close()


def test_two_buyers_cannot_reserve_the_same_seat(database):
    events = PostgresEventRepository(database)
    event = (
        EventBuilder(uuid4(), "Концерт")
        .sales_start(NOW - timedelta(days=1))
        .starts_at(NOW + timedelta(days=30))
        .category("Партер", Money(Decimal("600")))
        .seats("Партер", rows=[1], numbers=[1, 2])
        .build()
    )
    events.save(event)
    reserve_seats = ReserveSeats(
        events,
        SlowReservationRepository(database),
        PostgresOrderRepository(database),
        lambda: NOW,
        PostgresUnitOfWork(database),
        NoHallLayoutCache(),
    )
    start = threading.Barrier(2)
    outcomes = []

    def buyer():
        start.wait()
        try:
            reserve_seats.execute(ReserveSeatsCommand(event.id, uuid4(), (("Партер", 1, 1),)))
            outcomes.append("зарезервовано")
        except SeatNotAvailableError:
            outcomes.append("місце зайняте")

    threads = [threading.Thread(target=buyer) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(outcomes) == ["зарезервовано", "місце зайняте"]
    assert events.get(event.id).seats[SEAT].status is SeatStatus.RESERVED
    with database.connection() as connection:
        assert connection.execute("SELECT count(*) FROM orders").fetchone() == (1,)
