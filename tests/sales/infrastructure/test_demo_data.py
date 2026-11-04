"""Характеризаційні тести ЛР 4: демонстраційний захід до рефакторингу створення Event.

Фіксують усе, що бачить покупець і що залежить від порядку: ідентифікатор, назву, дати,
ціни категорій, склад і порядок місць (від нього залежить схема залу на сторінці).
"""

from datetime import datetime, timezone
from decimal import Decimal

from sales.domain.event import SeatStatus
from sales.domain.value_objects import Money, SeatPosition
from sales.infrastructure.demo_data import DEMO_EVENT_ID, seed_demo_event
from sales.infrastructure.in_memory import InMemoryEventRepository


def demo_event():
    events = InMemoryEventRepository()
    seed_demo_event(events)
    return events.get(DEMO_EVENT_ID)


def test_demo_event_identity_and_dates():
    event = demo_event()

    assert str(DEMO_EVENT_ID) == "00000000-0000-0000-0000-000000000018"
    assert event.title == "Концерт симфонічного оркестру"
    assert event.sales_start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert event.starts_at == datetime(2026, 12, 20, 17, 0, tzinfo=timezone.utc)


def test_demo_event_price_categories():
    event = demo_event()

    assert list(event.categories) == ["Партер", "VIP"]
    assert {name: category.name for name, category in event.categories.items()} == {"Партер": "Партер", "VIP": "VIP"}
    assert event.categories["Партер"].price == Money(Decimal("600"))
    assert event.categories["VIP"].price == Money(Decimal("1500"))


def test_demo_event_seats_in_hall_order():
    event = demo_event()
    expected = [SeatPosition("Партер", row, number) for row in range(1, 6) for number in range(1, 11)]
    expected += [SeatPosition("VIP", 1, number) for number in range(1, 7)]

    assert list(event.seats) == expected
    assert all(position == seat.position for position, seat in event.seats.items())
    assert [seat.category for seat in event.seats.values()] == ["Партер"] * 50 + ["VIP"] * 6
    assert all(seat.status is SeatStatus.AVAILABLE for seat in event.seats.values())
