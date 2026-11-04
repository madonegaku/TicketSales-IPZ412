"""Порівняння часу відповіді схеми залу без кешу й з кешем за однакових умов (ЛР 5, крок 7).

Запуск з кореня репозиторію (Docker Compose запущено, .venv активовано):
    python tools/compare_cache.py > docs/lab5/latency-comparison.txt

Перед кожною серією sales перестворюється з потрібним HALL_LAYOUT_CACHE_TTL (0 – кеш вимкнено),
а шлюз перезапускається (nginx визначає адресу sales лише під час старту). На Docker Desktop для
Windows час відповіді поступово зростає від серії до серії незалежно від кешу, тож без
перезапуску пізніша серія опинялася б у гірших умовах. Режими чергуються (без кешу, з кешем,
без, з), щоб вплив порядку запуску розподілився порівну.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

DATABASE_URL = "postgresql://sales:sales@127.0.0.1:5433/sales"
LATENCY = str(Path(__file__).with_name("latency.py"))
MODES = [("0", "без кешу"), ("30", "з кешем"), ("0", "без кешу"), ("30", "з кешем")]


def compose(*args: str, ttl: str | None = None) -> None:
    env = dict(os.environ)
    if ttl is not None:
        env["HALL_LAYOUT_CACHE_TTL"] = ttl
    subprocess.run(["docker", "compose", *args], env=env, check=True, capture_output=True)


def latency(label: str, *args: str) -> None:
    command = [sys.executable, LATENCY, "--label", label, "--database-url", DATABASE_URL, *args]
    print(subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for ttl, label in MODES:
        compose("up", "-d", "--force-recreate", "sales", ttl=ttl)
        compose("restart", "gateway")
        time.sleep(5)
        latency(f"{label}, 1 клієнт", "--requests", "500")
        latency(f"{label}, 10 клієнтів", "--requests", "2000", "--concurrency", "10")
    compose("up", "-d", "--force-recreate", "sales")
    compose("restart", "gateway")


if __name__ == "__main__":
    main()
