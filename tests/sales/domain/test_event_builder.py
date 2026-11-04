"""Тести будівника заходу (патерн Builder, ЛР 4)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.domain.event_builder import EventBuilder
from sales.domain.exceptions import UnknownPriceCategoryError
from sales.domain.value_objects import Money, SeatPosition

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SHOW = datetime(2026, 12, 20, 17, 0, tzinfo=timezone.utc)


def builder():
    return EventBuilder(uuid4(), "Концерт").sales_start(START).starts_at(SHOW)


def test_keys_match_identity_of_categories_and_seats():
    event = builder().category("Партер", Money(Decimal("600"))).seats("Партер", rows=[1, 2], numbers=range(1, 3)).build()

    assert all(name == category.name for name, category in event.categories.items())
    assert all(position == seat.position for position, seat in event.seats.items())
    assert list(event.seats) == [SeatPosition("Партер", 1, 1), SeatPosition("Партер", 1, 2),
                                 SeatPosition("Партер", 2, 1), SeatPosition("Партер", 2, 2)]


def test_seat_category_can_differ_from_sector():
    event = (builder().category("Балкон дешево", Money(Decimal("300")))
             .seats("Балкон", rows=[1], numbers=[1], category="Балкон дешево").build())

    assert event.price_of(SeatPosition("Балкон", 1, 1)) == Money(Decimal("300"))


def test_unknown_category_is_rejected_by_event_invariant():
    with pytest.raises(UnknownPriceCategoryError):
        builder().seats("VIP", rows=[1], numbers=[1]).build()


def test_same_seat_twice_is_rejected():
    with pytest.raises(ValueError, match="уже додано"):
        builder().category("VIP", Money(Decimal("1500"))).seats("VIP", [1], [1]).seats("VIP", [1], [1])


def test_dates_are_required():
    with pytest.raises(ValueError, match="старт продажу"):
        EventBuilder(uuid4(), "Концерт").category("VIP", Money(Decimal("1500"))).build()
