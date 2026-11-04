"""Транзакційна вихідна черга sales на справжньому PostgreSQL (потрібен контейнер sales-db).

Головна властивість: статус «оплачене», продані місця й подія OrderPaid фіксуються в одній
транзакції – або всі, або жоден. Тоді подія не губиться при перезапуску sales (борг ЛР 3), а
подія про неоплачене замовлення не з'являється.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from sales.application.pay_order import PayOrderCommand  # noqa: E402
from sales.application.publish_pending_events import PublishPendingEvents  # noqa: E402
from sales.application.reserve_seats import ReserveSeatsCommand  # noqa: E402
from sales.config.composition import Container  # noqa: E402
from sales.domain.event import SeatStatus  # noqa: E402
from sales.domain.event_publisher import EventPublisher  # noqa: E402
from sales.domain.order_paid import OrderPaid  # noqa: E402
from sales.domain.order_state import OrderStatus  # noqa: E402
from sales.domain.value_objects import SeatPosition  # noqa: E402
from sales.infrastructure.demo_data import DEMO_EVENT_ID, ensure_demo_event  # noqa: E402
from sales.infrastructure.payment import StubPaymentGateway  # noqa: E402
from sales.infrastructure.postgres.database import Database  # noqa: E402
from sales.infrastructure.postgres.migrate import migrate_database  # noqa: E402
from sales.infrastructure.postgres.outbox import PostgresOutbox  # noqa: E402
from sales.infrastructure.postgres.repositories import PostgresEventRepository  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
VIP1, VIP2 = SeatPosition("VIP", 1, 1), SeatPosition("VIP", 1, 2)


class RecordingPublisher(EventPublisher):
    def __init__(self) -> None:
        self.published: list[OrderPaid] = []

    def publish(self, event: OrderPaid) -> None:
        self.published.append(event)


class OfflineContainer(Container):
    """Справжнє сховище PostgreSQL; payments і брокер замінено заглушками."""

    def create_payment_gateway(self):
        self.gateway = StubPaymentGateway()
        return self.gateway

    def create_event_publisher(self):
        self.publisher = RecordingPublisher()
        return self.publisher


@pytest.fixture
def container(pg_conninfo):
    config = SimpleNamespace(
        PAYMENTS_URL="http://unused", PAYMENTS_TIMEOUT_SECONDS=2, REDIS_URL="redis://unused",
        SALES_DATABASE_URL=pg_conninfo,
    )
    return OfflineContainer(config)


@pytest.fixture
def database(pg_conninfo):
    migrate_database(pg_conninfo)
    database = Database(pg_conninfo, max_size=2)
    yield database
    database.close()


def reserve_and_pay(container) -> object:
    reserved = container.reserve_seats.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 1),)))
    container.pay_order.execute(PayOrderCommand(reserved.order_id))
    return reserved.order_id


def test_outbox_returns_pending_events_in_order_until_published(database):
    outbox = PostgresOutbox(database)
    first, second = (
        OrderPaid(uuid4(), NOW, uuid4(), uuid4(), "Концерт", NOW + timedelta(days=30), (VIP1, VIP2)) for _ in range(2)
    )
    outbox.add(first)
    outbox.add(second)

    assert outbox.pending() == [first, second]

    outbox.mark_published(first.message_id)

    assert outbox.pending() == [second]


def test_paid_order_and_its_event_are_committed_together(container, pg_conninfo):
    order_id = reserve_and_pay(container)

    [event] = container.outbox.pending()
    assert (event.order_id, event.seats) == (order_id, (VIP1,))
    assert container.pay_order._orders.get(order_id).status is OrderStatus.PAID

    published = PublishPendingEvents(container.outbox, container.publisher).execute()

    assert published == 1
    assert container.outbox.pending() == []
    assert [e.order_id for e in container.publisher.published] == [order_id]


def test_failure_after_payment_rolls_back_status_seats_and_event_together(container):
    """Якщо запис події впав, транзакція кроку 3 відкочується повністю: ні статусу «оплачене», ні проданих місць."""
    reserved = container.reserve_seats.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 1),)))
    outbox = container.pay_order._outbox

    def failing_add(event):
        raise RuntimeError("збій під час запису події")

    outbox.add = failing_add
    with pytest.raises(RuntimeError):
        container.pay_order.execute(PayOrderCommand(reserved.order_id))

    assert container.pay_order._orders.get(reserved.order_id).status is OrderStatus.PAYMENT_PENDING
    assert container.pay_order._events.get(DEMO_EVENT_ID).seats[VIP1].status is SeatStatus.RESERVED
    del outbox.add
    assert outbox.pending() == []


def test_demo_event_is_not_reset_by_restart(database):
    events = PostgresEventRepository(database)
    ensure_demo_event(events)
    event = events.get(DEMO_EVENT_ID)
    event.reserve_seats([VIP1], NOW)
    events.save(event)

    ensure_demo_event(events)

    assert events.get(DEMO_EVENT_ID).seats[VIP1].status is SeatStatus.RESERVED
