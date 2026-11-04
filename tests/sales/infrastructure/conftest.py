"""Фікстура інтеграційних тестів sales з PostgreSQL: окрема порожня схема на кожен тест.

База – контейнер sales-db (docker compose up -d sales-db), адреса – змінна
SALES_TEST_DATABASE_URL або localhost:5433. Кожен тест отримує власну схему (search_path),
тож тести не бачать даних один одного й робочих даних демо-заходу. Якщо драйвера чи бази
немає, тест пропускається з поясненням, а не падає: доменні тести від бази не залежать.
"""

import os
from uuid import uuid4

import pytest

BASE_URL = os.environ.get("SALES_TEST_DATABASE_URL", "postgresql://sales:sales@127.0.0.1:5433/sales")


@pytest.fixture
def pg_conninfo():
    """Рядок підключення до нової порожньої схеми; після тесту схема видаляється."""
    psycopg = pytest.importorskip("psycopg", reason="драйвер psycopg не встановлено (pip install -r requirements.txt)")
    from psycopg.conninfo import make_conninfo

    schema = f"test_{uuid4().hex[:12]}"
    try:
        admin = psycopg.connect(BASE_URL, autocommit=True, connect_timeout=2)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL недоступний ({BASE_URL}): запустіть docker compose up -d sales-db – {exc}")
    with admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
        try:
            yield make_conninfo(BASE_URL, options=f"-c search_path={schema}")
        finally:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
