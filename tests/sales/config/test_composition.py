"""Тест складання sales без мережі (патерн Factory Method, ЛР 4).

Підклас контейнера перевизначає фабричні методи й підставляє заглушки payments і брокера.
Решта складання – справжня, тож тест перевіряє зв'язки між об'єктами: оплата через
контейнер кладе подію у ту саму вихідну чергу, з якої її публікує «поштар».
"""

from types import SimpleNamespace

from sales.application.pay_order import PayOrderCommand
from sales.application.reserve_seats import ReserveSeatsCommand
from sales.config.composition import Container
from sales.domain.event_publisher import EventPublisher
from sales.domain.order_paid import OrderPaid
from sales.infrastructure.demo_data import DEMO_EVENT_ID
from sales.infrastructure.payment import StubPaymentGateway

CONFIG = SimpleNamespace(PAYMENTS_URL="http://unused", PAYMENTS_TIMEOUT_SECONDS=2, REDIS_URL="redis://unused")
BUYER_ID = DEMO_EVENT_ID


class RecordingPublisher(EventPublisher):
    def __init__(self) -> None:
        self.published: list[OrderPaid] = []

    def publish(self, event: OrderPaid) -> None:
        self.published.append(event)


class OfflineContainer(Container):
    """Контейнер без мережевих залежностей: змінено лише два фабричні методи."""

    def create_payment_gateway(self):
        self.gateway = StubPaymentGateway()
        return self.gateway

    def create_event_publisher(self):
        self.publisher = RecordingPublisher()
        return self.publisher


def test_reserved_and_paid_order_is_published_through_the_relay():
    container = OfflineContainer(CONFIG)

    reserved = container.reserve_seats.execute(ReserveSeatsCommand(DEMO_EVENT_ID, BUYER_ID, (("VIP", 1, 2),)))
    container.pay_order.execute(PayOrderCommand(reserved.order_id))
    container.outbox_relay._publish_pending.execute()

    assert [order_id for order_id, _ in container.gateway.charges] == [reserved.order_id]
    assert [event.order_id for event in container.publisher.published] == [reserved.order_id]
    assert container.outbox.pending() == []
    assert not container.outbox_relay.is_alive(), "контейнер не запускає потік сам – це робить container.py"


def test_default_factory_methods_use_config():
    container = Container(CONFIG)

    gateway = container.pay_order._payment_gateway
    assert str(gateway._client.base_url) == "http://unused"
    assert gateway._client.timeout.read == 2
