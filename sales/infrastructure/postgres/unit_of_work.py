"""Одиниця роботи на PostgreSQL: транзакція бази на весь блок сценарію."""

from collections.abc import Iterator
from contextlib import contextmanager

from sales.application.unit_of_work import UnitOfWork
from sales.infrastructure.postgres.database import Database


class PostgresUnitOfWork(UnitOfWork):
    """Репозиторії, викликані всередині transaction(), працюють в одній транзакції бази sales."""

    def __init__(self, database: Database) -> None:
        self._db = database

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._db.transaction():
            yield
