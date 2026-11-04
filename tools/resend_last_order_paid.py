"""Демонстрація ідемпотентності обробника OrderPaid (ЛР 5, крок 6): повторно надсилає останню подію.

Виконується всередині контейнера tickets-consumer (там є redis-py і база квитків):
    docker compose cp tools/resend_last_order_paid.py tickets-consumer:/tmp/resend.py
    docker compose exec tickets-consumer python /tmp/resend.py
    docker compose logs tickets-consumer --tail 3

Бере останній запис потоку sales.order-paid.v1, додає його знову (XADD тих самих полів – та сама
подія з тим самим message_id усередині) і порівнює коди квитків замовлення до й після обробки.
"""

import json
import sqlite3
import time

import redis

STREAM = "sales.order-paid.v1"
TICKETS_DB = "/data/tickets.sqlite3"

client = redis.Redis.from_url("redis://redis:6379/0", decode_responses=True)
entries = client.xrevrange(STREAM, count=1)
if not entries:
    raise SystemExit("Потік порожній: спершу оплатіть замовлення через http://localhost:8080/")
last_id, fields = entries[0]
order_id = json.loads(fields["payload"])["order_id"]
database = sqlite3.connect(TICKETS_DB)


def codes() -> list[str]:
    return sorted(code for (code,) in database.execute("SELECT code FROM tickets WHERE order_id = ?", (order_id,)))


before = codes()
new_id = client.xadd(STREAM, fields)
print(f"Замовлення {order_id}: подію {last_id} надіслано повторно як {new_id}")
time.sleep(3)
after = codes()
print(f"Квитки до повтору:    {before}")
print(f"Квитки після повтору: {after}")
print("Результат не змінився." if before == after else "УВАГА: повтор змінив результат!")
group = client.xinfo_groups(STREAM)[0]
print(f"Група {group['name']}: lag = {group['lag']}, pending = {group['pending']}")
