"""Тести міграцій PostgreSQL сервісу sales (потрібен контейнер sales-db)."""

import pytest

psycopg = pytest.importorskip("psycopg")

from sales.infrastructure.postgres.migrate import applied_versions, available, migrate, migrate_database  # noqa: E402

TABLES = {"events", "price_categories", "seats", "reservations", "reservation_seats", "orders", "order_lines"}


def tables_of(connection) -> set[str]:
    rows = connection.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    ).fetchall()
    return {row[0] for row in rows}


def test_migrations_are_numbered_without_gaps():
    numbers = [int(version[:4]) for version, _ in available()]

    assert numbers == list(range(1, len(numbers) + 1))


def test_fresh_database_gets_all_migrations_once(pg_conninfo):
    first = migrate_database(pg_conninfo)
    second = migrate_database(pg_conninfo)

    assert first == [version for version, _ in available()]
    assert second == []
    with psycopg.connect(pg_conninfo) as connection:
        assert applied_versions(connection) == first
        assert TABLES <= tables_of(connection)


def test_failed_migration_changes_nothing(pg_conninfo, tmp_path):
    (tmp_path / "0001_good.sql").write_text("CREATE TABLE a (x INTEGER);", encoding="utf-8")
    (tmp_path / "0002_broken.sql").write_text("CREATE TABLE b (x INTEGER);\nSELECT * FROM missing;", encoding="utf-8")

    with psycopg.connect(pg_conninfo, autocommit=True) as connection:
        with pytest.raises(psycopg.errors.UndefinedTable):
            migrate(connection, directory=tmp_path)

        assert applied_versions(connection) == ["0001_good"]
        assert {"a", "schema_migrations"} == tables_of(connection)


def test_schema_rejects_status_outside_known_codes(pg_conninfo):
    migrate_database(pg_conninfo)

    with psycopg.connect(pg_conninfo) as connection, pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "INSERT INTO events VALUES ('00000000-0000-0000-0000-000000000001', 'Концерт', now(), now())"
        )
        connection.execute(
            "INSERT INTO price_categories VALUES ('00000000-0000-0000-0000-000000000001', 'Партер', 600, 'UAH')"
        )
        connection.execute(
            "INSERT INTO seats VALUES ('00000000-0000-0000-0000-000000000001', 'Партер', 1, 1, 1, 'Партер', 'вільне')"
        )
