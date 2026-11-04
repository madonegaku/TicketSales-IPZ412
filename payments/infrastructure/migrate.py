"""Міграції схеми SQLite сервісу payments.

Кожна міграція – пронумерований SQL-файл у каталозі migrations/ (0001_initial.sql, 0002_…).
Застосовані версії записуються в таблицю schema_migrations, тож кожна міграція виконується
рівно один раз. Міграція разом із записом про неї виконується в одній транзакції: якщо
SQL-скрипт падає, схема й журнал лишаються як були.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")

JOURNAL = "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"


def number_of(version: str) -> int:
    """Номер міграції з назви: «0002_add_amount_minor» → 2."""
    return int(version.split("_", 1)[0])


def available(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, Path]]:
    """Усі міграції за зростанням номера: (версія, шлях до файлу)."""
    return sorted(((path.stem, path) for path in directory.glob("*.sql")), key=lambda item: number_of(item[0]))


def applied_versions(connection: sqlite3.Connection) -> list[str]:
    connection.execute(JOURNAL)
    connection.commit()
    return [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]


def migrate(connection: sqlite3.Connection, target: int | None = None, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Застосовує ще не застосовані міграції по порядку (до номера target включно); повертає їхні версії."""
    done = set(applied_versions(connection))
    applied = []
    for version, path in available(directory):
        if target is not None and number_of(version) > target:
            break
        if version in done:
            continue
        moment = datetime.now(timezone.utc).isoformat()
        script = path.read_text(encoding="utf-8")
        try:
            connection.executescript(
                f"BEGIN;\n{script}\nINSERT INTO schema_migrations VALUES ('{version}', '{moment}');\nCOMMIT;"
            )
        except sqlite3.Error:
            if connection.in_transaction:
                connection.rollback()
            raise
        applied.append(version)
    return applied
