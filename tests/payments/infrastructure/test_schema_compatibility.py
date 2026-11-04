"""Сумісність міграцій «розширення – скорочення»: після кожної міграції працює попередня версія коду.

Запити кожної версії сховища платежів зафіксовано тут рядками («заморожено»), тому тести не
змінюються, коли робочий код переходить на наступну версію. Під час поступового розгортання
дві сусідні версії працюють одночасно, тож кожна має читати рядки, записані іншою.

  v1 – ЛР 3: пише й читає amount (текст).
  v2 – розширення: пише amount і amount_minor, читає amount.
  v3 – перенесення: пише amount і amount_minor, читає amount_minor.

Порядок розгортання: 0002 → усі екземпляри на v2 → 0003 → v3. Тому після 0003 поруч можуть
працювати лише v2 і v3 (v1 уже немає).
"""

import sqlite3
from contextlib import closing

import pytest

from payments.infrastructure.migrate import migrate

COLUMNS = "order_id, payment_id, {amount}, currency, status, decline_reason, created_at"
CONSTANT = "'UAH', 'succeeded', NULL, '2026-11-04T12:00:00+00:00'"

V1_WRITE = f"INSERT INTO payments ({COLUMNS.format(amount='amount')}) VALUES (?, ?, ?, {CONSTANT})"
V2_WRITE = f"INSERT INTO payments ({COLUMNS.format(amount='amount, amount_minor')}) VALUES (?, ?, ?, ?, {CONSTANT})"
V3_WRITE = V2_WRITE
READ_AMOUNT = "SELECT amount FROM payments WHERE order_id = ?"
READ_AMOUNT_MINOR = "SELECT amount_minor FROM payments WHERE order_id = ?"


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


def read_amount_minor(db, order_id):
    return db.execute(READ_AMOUNT_MINOR, (order_id,)).fetchone()[0]


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


@pytest.mark.parametrize(
    ("amount", "expected_minor"),
    [("1200.00", 120000), ("600", 60000), ("0.10", 10), ("12.5", 1250), ("99999.99", 9999999), ("0", 0)],
)
def test_0003_fills_minor_units_for_rows_written_by_v1(db, amount, expected_minor):
    migrate(db, target=2)
    v1_write(db, "o1", amount)

    migrate(db, target=3)

    assert read_amount_minor(db, "o1") == expected_minor


def test_0003_does_not_touch_rows_written_by_v2(db):
    migrate(db, target=2)
    v2_write(db, "o1", "1500.00", 150000)

    migrate(db, target=3)

    assert (read_amount(db, "o1"), read_amount_minor(db, "o1")) == ("1500.00", 150000)


def test_after_0003_v2_and_v3_read_each_others_rows(db):
    migrate(db, target=3)

    v2_write(db, "o2", "600.00", 60000)
    db.execute(V3_WRITE, ("o3", "p-o3", "1500.00", 150000))
    db.commit()

    assert read_amount(db, "o3") == "1500.00", "v2 читає рядок, записаний v3"
    assert read_amount_minor(db, "o2") == 60000, "v3 читає рядок, записаний v2"
