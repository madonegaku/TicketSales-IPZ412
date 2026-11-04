"""З'єднання з PostgreSQL: пул з'єднань і транзакція поточного потоку.

Django обслуговує кожен запит в окремому потоці, тож транзакція прив'язується до потоку:
усі репозиторії, викликані всередині transaction(), працюють в одному з'єднанні й одній
транзакції. Поза транзакцією кожна операція репозиторію – окрема коротка транзакція.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool


class Database:
    """Пул з'єднань бази sales; transaction() – межа транзакції для одиниці роботи."""

    def __init__(self, conninfo: str, min_size: int = 1, max_size: int = 5, timeout: float = 5.0) -> None:
        self._pool = ConnectionPool(conninfo, min_size=min_size, max_size=max_size, timeout=timeout, open=True)
        self._local = threading.local()

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        """Транзакція: COMMIT, якщо блок завершився без винятку, інакше ROLLBACK."""
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("Вкладені транзакції не підтримуються: межа транзакції – сценарій.")
        with self._pool.connection() as connection:
            self._local.connection = connection
            try:
                yield connection
            finally:
                self._local.connection = None

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        """З'єднання поточної транзакції або нова коротка транзакція, якщо її немає."""
        current = getattr(self._local, "connection", None)
        if current is not None:
            yield current
        else:
            with self.transaction() as connection:
                yield connection

    @property
    def in_transaction(self) -> bool:
        return getattr(self._local, "connection", None) is not None

    def close(self) -> None:
        self._pool.close()
