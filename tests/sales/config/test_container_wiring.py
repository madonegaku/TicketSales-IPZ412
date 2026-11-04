"""Характеризаційний тест ЛР 4: як складається сервіс sales у config/container.py.

Контейнер створюється під час імпорту модуля й читає налаштування Django, а налаштувати
Django в одному процесі можна лише раз (тести payments уже налаштовують його на свій сервіс).
Тому складання виконується в окремому процесі, який друкує факти про зв'язки між об'єктами.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PROBE = r"""
import json, django
django.setup()
from sales.config.container import container
from sales.application.reserve_seats import ReserveSeatsCommand
from sales.infrastructure.demo_data import DEMO_EVENT_ID

pay = container.pay_order
gateway = pay._payment_gateway
relay = container.outbox_relay
publisher = relay._publish_pending._publisher
pool = publisher._client.connection_pool.connection_kwargs
result = container.reserve_seats.execute(ReserveSeatsCommand(DEMO_EVENT_ID, DEMO_EVENT_ID, (("VIP", 1, 1),)))
layout = container.get_hall_layout.execute(DEMO_EVENT_ID)
print(json.dumps({
    "gateway": type(gateway).__name__,
    "base_url": str(gateway._client.base_url),
    "timeout": gateway._client.timeout.read,
    "publisher": type(publisher).__name__,
    "stream": publisher._stream,
    "redis_host": pool["host"],
    "redis_connect_timeout": pool["socket_connect_timeout"],
    "redis_timeout": pool["socket_timeout"],
    "same_outbox": pay._outbox is container.outbox is relay._publish_pending._outbox,
    "same_orders": pay._orders is container.reserve_seats._orders,
    "same_events": pay._events is container.reserve_seats._events is container.get_hall_layout._events,
    "relay_started": relay.is_alive(),
    "relay_daemon": relay.daemon,
    "relay_interval": relay._interval,
    "reserved_total": str(result.total_amount),
    "vip_1_1_available": [s.is_available for s in layout.seats if (s.sector, s.row, s.number) == ("VIP", 1, 1)][0],
    "seats": len(layout.seats),
}))
"""


def build_container() -> dict:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "sales.config.settings",
        "PAYMENTS_URL": "http://payments.test:8000",
        "PAYMENTS_TIMEOUT_SECONDS": "2",
        "REDIS_URL": "redis://redis.test:6379/0",
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
    }
    completed = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_sales_container_wiring():
    facts = build_container()

    assert facts == {
        "gateway": "HttpPaymentGateway",
        "base_url": "http://payments.test:8000",
        "timeout": 2.0,
        "publisher": "RedisStreamPublisher",
        "stream": "sales.order-paid.v1",
        "redis_host": "redis.test",
        "redis_connect_timeout": 1,
        "redis_timeout": 1,
        "same_outbox": True,
        "same_orders": True,
        "same_events": True,
        "relay_started": True,
        "relay_daemon": True,
        "relay_interval": 1.0,
        "reserved_total": "1500",
        "vip_1_1_available": False,
        "seats": 56,
    }
