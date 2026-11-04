"""Кеш схеми залу на рівні сценаріїв: влучання, промах і інвалідизація подією після фіксації транзакції."""

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sales.application.get_hall_layout import GetHallLayout
from sales.application.pay_order import PayOrder, PayOrderCommand
from sales.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from sales.application.unit_of_work import UnitOfWork
from sales.domain.exceptions import SeatNotAvailableError
from sales.infrastructure.demo_data import DEMO_EVENT_ID, seed_demo_event
from sales.infrastructure.hall_layout_cache import InMemoryHallLayoutCache
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryOutbox,
    InMemoryReservationRepository,
)
from sales.infrastructure.payment import StubPaymentGateway

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


class CountingEventRepository(InMemoryEventRepository):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def get(self, event_id):
        self.reads += 1
        return super().get(event_id)


class RecordingUnitOfWork(UnitOfWork):
    """Записує момент фіксації транзакції в спільний журнал подій."""

    def __init__(self, journal: list[str]) -> None:
        self._journal = journal

    @contextmanager
    def transaction(self):
        yield
        self._journal.append("commit")


class JournalCache(InMemoryHallLayoutCache):
    def __init__(self, journal: list[str]) -> None:
        super().__init__()
        self._journal = journal

    def invalidate(self, event_id):
        self._journal.append("invalidate")
        super().invalidate(event_id)


@pytest.fixture
def system():
    journal: list[str] = []
    events = CountingEventRepository()
    seed_demo_event(events)
    events.reads = 0
    orders = InMemoryOrderRepository()
    cache = JournalCache(journal)
    unit_of_work = RecordingUnitOfWork(journal)
    reserve = ReserveSeats(events, InMemoryReservationRepository(), orders, lambda: NOW, unit_of_work, cache)
    pay = PayOrder(events, orders, StubPaymentGateway(), InMemoryOutbox(), lambda: NOW, unit_of_work, cache)
    return events, cache, journal, GetHallLayout(events, cache), reserve, pay


def availability(layout, sector, row, number):
    return next(s.is_available for s in layout.seats if (s.sector, s.row, s.number) == (sector, row, number))


def test_repeated_reads_are_served_from_cache(system):
    events, cache, _, get_layout, _, _ = system

    first = get_layout.execute(DEMO_EVENT_ID)
    second = get_layout.execute(DEMO_EVENT_ID)

    assert second == first
    assert events.reads == 1
    assert (cache.misses, cache.hits) == (1, 1)


def test_reservation_invalidates_cached_layout_after_commit(system):
    _, cache, journal, get_layout, reserve, _ = system
    assert availability(get_layout.execute(DEMO_EVENT_ID), "VIP", 1, 1) is True

    reserve.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 1),)))

    assert journal == ["commit", "invalidate"], "запис видаляється лише після фіксації транзакції"
    assert availability(get_layout.execute(DEMO_EVENT_ID), "VIP", 1, 1) is False


def test_payment_invalidates_cached_layout(system):
    _, cache, journal, get_layout, reserve, pay = system
    order_id = reserve.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 2),))).order_id
    get_layout.execute(DEMO_EVENT_ID)
    journal.clear()

    pay.execute(PayOrderCommand(order_id))

    assert journal[-2:] == ["commit", "invalidate"]
    assert DEMO_EVENT_ID not in cache.entries


def test_failed_reservation_keeps_cache(system):
    _, cache, _, get_layout, reserve, _ = system
    reserve.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 3),)))
    get_layout.execute(DEMO_EVENT_ID)
    cache.invalidated.clear()

    with pytest.raises(SeatNotAvailableError):
        reserve.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 3),)))

    assert cache.invalidated == []
    assert DEMO_EVENT_ID in cache.entries
