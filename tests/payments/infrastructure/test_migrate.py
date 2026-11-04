"""Тести механізму міграцій payments: порядок, одноразовість, базова схема, відкат невдалої міграції."""

import sqlite3
from contextlib import closing

import pytest

from payments.infrastructure.migrate import applied_versions, available, migrate

LAB3_SCHEMA = """
CREATE TABLE payments (
    order_id TEXT PRIMARY KEY, payment_id TEXT NOT NULL UNIQUE, amount TEXT NOT NULL, currency TEXT NOT NULL,
    status TEXT NOT NULL, decline_reason TEXT, created_at TEXT NOT NULL
)
"""


def connect(path):
    return closing(sqlite3.connect(path))


def test_migrations_are_numbered_without_gaps():
    numbers = [int(version[:4]) for version, _ in available()]

    assert numbers == list(range(1, len(numbers) + 1))


def test_fresh_database_gets_all_migrations_once(tmp_path):
    with connect(tmp_path / "db.sqlite3") as connection:
        first = migrate(connection)
        second = migrate(connection)

        assert first == [version for version, _ in available()]
        assert second == []
        assert applied_versions(connection) == first


def test_database_created_before_migrations_keeps_its_rows(tmp_path):
    with connect(tmp_path / "db.sqlite3") as connection:
        connection.execute(LAB3_SCHEMA)
        connection.execute("INSERT INTO payments VALUES ('o1', 'p1', '600', 'UAH', 'succeeded', NULL, '2026-11-04')")
        connection.commit()

        migrate(connection, target=1)

        assert applied_versions(connection) == ["0001_initial"]
        assert connection.execute("SELECT payment_id FROM payments").fetchall() == [("p1",)]


def test_failed_migration_changes_nothing(tmp_path):
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "0001_good.sql").write_text("CREATE TABLE a (x INTEGER);", encoding="utf-8")
    (directory / "0002_broken.sql").write_text("CREATE TABLE b (x INTEGER);\nSELECT * FROM missing;", encoding="utf-8")

    with connect(tmp_path / "db.sqlite3") as connection:
        with pytest.raises(sqlite3.OperationalError):
            migrate(connection, directory=directory)

        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert applied_versions(connection) == ["0001_good"]
        assert "a" in tables and "b" not in tables
