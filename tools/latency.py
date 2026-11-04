"""Вимірювання часу відповіді сценарію читання (ЛР 5, крок 7 методички).

Запуск: python tools/latency.py [URL] [--requests N] [--warmup N] [--concurrency N] [--label TEXT]
                                [--database-url URL]

Надсилає GET на URL (за замовчуванням – схема залу демо-заходу через шлюз) і виводить
середнє, медіану (p50), p95, p99 і максимум у мілісекундах. Перші --warmup запитів не
враховуються: вони прогрівають з'єднання, пул бази й кеш. Вимірювання до і після кешу
виконуються з однаковими параметрами на тій самій машині – так їх можна порівнювати.

З --database-url (база sales, з хоста – postgresql://sales:sales@127.0.0.1:5433/sales) ще
рахує навантаження на базу за час вимірювання: транзакції та прочитані рядки зі статистики
pg_stat_database. До них домішуються щосекундні запити «поштаря» до таблиці outbox.
"""

import argparse
import statistics
import threading
import time
from datetime import datetime

import httpx

DEFAULT_URL = "http://localhost:8080/events/00000000-0000-0000-0000-000000000018/"


def percentile(values: list[float], share: float) -> float:
    """Перцентиль за методом найближчого рангу: значення, не менше за яке share усіх вимірів."""
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(share * len(ordered)) - 1))
    return ordered[index]


def measure(url: str, requests: int, concurrency: int) -> list[float]:
    """Часи відповідей у мілісекундах; кожен потік має власне з'єднання (як окремий браузер)."""
    timings: list[float] = []
    lock = threading.Lock()
    per_thread = [requests // concurrency + (1 if i < requests % concurrency else 0) for i in range(concurrency)]

    def worker(count: int) -> None:
        with httpx.Client(timeout=10) as client:
            for _ in range(count):
                started = time.perf_counter()
                response = client.get(url)
                elapsed = (time.perf_counter() - started) * 1000
                response.raise_for_status()
                with lock:
                    timings.append(elapsed)

    threads = [threading.Thread(target=worker, args=(count,)) for count in per_thread]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return timings


def database_counters(database_url: str) -> tuple[int, int]:
    """(транзакції, прочитані рядки) бази sales з початку роботи PostgreSQL."""
    import psycopg

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("SELECT pg_stat_clear_snapshot()")
        return connection.execute(
            "SELECT xact_commit + xact_rollback, tup_returned + tup_fetched FROM pg_stat_database "
            "WHERE datname = current_database()"
        ).fetchone()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--label", default="")
    parser.add_argument("--database-url")
    args = parser.parse_args()

    measure(args.url, args.warmup, 1)
    before = database_counters(args.database_url) if args.database_url else None
    started = time.perf_counter()
    timings = measure(args.url, args.requests, args.concurrency)
    duration = time.perf_counter() - started
    if before:
        time.sleep(11)  # з'єднання пулу, що простоюють, передають статистику не частіше ніж раз на 10 с
        after = database_counters(args.database_url)

    print(f"# {args.label} – {datetime.now().isoformat(timespec='seconds')}")
    print(f"URL: {args.url}")
    print(f"запитів: {len(timings)}, паралельно: {args.concurrency}, прогрів: {args.warmup}")
    print(f"середнє: {statistics.fmean(timings):.1f} мс")
    print(f"p50: {percentile(timings, 0.50):.1f} мс")
    print(f"p95: {percentile(timings, 0.95):.1f} мс")
    print(f"p99: {percentile(timings, 0.99):.1f} мс")
    print(f"максимум: {max(timings):.1f} мс")
    print(f"пропускна здатність: {len(timings) / duration:.0f} запитів/с")
    if before:
        transactions, rows = after[0] - before[0], after[1] - before[1]
        print(f"база sales: {transactions} транзакцій ({transactions / len(timings):.2f} на запит), "
              f"{rows} прочитаних рядків ({rows / len(timings):.1f} на запит)")


if __name__ == "__main__":
    main()
