"""Міграції схеми PostgreSQL сервісу sales.

Кожна міграція – пронумерований SQL-файл у каталозі migrations/. Застосовані версії
записуються в таблицю schema_migrations, тож кожна виконується рівно один раз. PostgreSQL
підтримує транзакції для DDL, тому міграція й запис про неї – одна транзакція: якщо скрипт
падає, схема й журнал лишаються як були. Рекомендаційне блокування (advisory lock) не дає
двом екземплярам sales, що стартують одночасно, застосувати ту саму міграцію двічі.

Механізм повторює payments/infrastructure/migrate.py, але не імпортує його: сервіси не
ділять код (контракт independence).
"""

from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
LOCK_KEY = 5_000_001  # довільне число – ключ блокування міграцій sales

JOURNAL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def number_of(version: str) -> int:
    """Номер міграції з назви: «0002_outbox» → 2."""
    return int(version.split("_", 1)[0])


def available(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, Path]]:
    """Усі міграції за зростанням номера: (версія, шлях до файлу)."""
    return sorted(((path.stem, path) for path in directory.glob("*.sql")), key=lambda item: number_of(item[0]))


def applied_versions(connection: psycopg.Connection) -> list[str]:
    with connection.transaction():
        connection.execute(JOURNAL)
    rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [row[0] for row in rows]


def migrate(connection: psycopg.Connection, target: int | None = None, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Застосовує ще не застосовані міграції по порядку (до номера target включно); повертає їхні версії.

    З'єднання має бути в режимі autocommit: кожна міграція відкриває власну транзакцію.
    """
    applied_versions(connection)
    applied = []
    for version, path in available(directory):
        if target is not None and number_of(version) > target:
            break
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
            exists = connection.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,)).fetchone()
            if exists:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        applied.append(version)
    return applied


def migrate_database(conninfo: str) -> list[str]:
    """Застосовує всі міграції до бази за рядком підключення – викликається під час старту sales."""
    with psycopg.connect(conninfo, autocommit=True) as connection:
        return migrate(connection)
