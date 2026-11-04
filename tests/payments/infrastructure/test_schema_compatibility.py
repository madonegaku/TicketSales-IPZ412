"""Сумісність міграцій «розширення – скорочення»: після кожної міграції працює попередня версія коду.

Запити кожної версії сховища платежів зафіксовано тут рядками («заморожено»), тому тести не
змінюються, коли робочий код переходить на наступну версію. Під час поступового розгортання
дві сусідні версії працюють одночасно, тож кожна має читати рядки, записані іншою.

  v1 – ЛР 3: пише й читає amount (текст).
  v2 – розширення: пише amount і amount_minor, читає amount.
"""

import sqlite3
from contextlib import closing

import pytest

from payments.infrastructure.migrate import migrate

COLUMNS = "order_id, payment_id, {amount}, currency, status, decline_reason, created_at"
CONSTANT = "'UAH', 'succeeded', NULL, '2026-11-04T12:00:00+00:00'"

V1_WRITE = f"INSERT INTO payments ({COLUMNS.format(amount='amount')}) VALUES (?, ?, ?, {CONSTANT})"
V2_WRITE = f"INSERT INTO payments ({COLUMNS.format(amount='amount, amount_minor')}) VALUES (?, ?, ?, ?, {CONSTANT})"
READ_AMOUNT = "SELECT amount FROM payments WHERE order_id = ?"


@pytest.fixture
def db(tmp_path):
    with closing(sqlite3.connect(tmp_path / "payments.sqlite3")) as connection:
        yield connection


def v1_write(db, order_id, amount):
    db.execute(V1_WRITE, (order_id, f"p-{order_id}", amount))
    db.commit()


def v2_write(db, order_id, amount, amount_minor):
    db.execute(V2_WRITE, (order_id, f"p-{order_id}", amount, amount_minor))
    db.commit()


def read_amount(db, order_id):
    return db.execute(READ_AMOUNT, (order_id,)).fetchone()[0]


def test_0002_keeps_rows_written_before_it(db):
    migrate(db, target=1)
    v1_write(db, "o1", "1200.00")

    migrate(db, target=2)

    assert db.execute("SELECT amount, amount_minor FROM payments").fetchall() == [("1200.00", None)]


def test_after_0002_v1_still_works(db):
    migrate(db, target=2)

    v1_write(db, "o1", "600")

    assert read_amount(db, "o1") == "600"


def test_after_0002_v1_and_v2_read_each_others_rows(db):
    migrate(db, target=2)

    v1_write(db, "o1", "600")
    v2_write(db, "o2", "1500.00", 150000)

    assert (read_amount(db, "o1"), read_amount(db, "o2")) == ("600", "1500.00")


def test_after_0002_row_without_any_amount_is_rejected(db):
    migrate(db, target=2)

    with pytest.raises(sqlite3.IntegrityError):
        v2_write(db, "o1", None, None)
