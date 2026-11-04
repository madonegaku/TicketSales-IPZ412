"""Вимірювання вікна неузгодженості sales → tickets (ЛР 5): від «Оплату виконано» до появи квитка.

Запуск (Docker Compose запущено): python tools/order_paid_lag.py [--purchases N]

Через шлюз купує N вільних місць по одному (резервування → оплата) і після відповіді на оплату
щоп'ятнадцять мілісекунд опитує сторінку «Мої квитки», доки не з'явиться код квитка. Час між
ними – скільки покупець бачить «Квитки ще видаються»: замовлення в sales уже оплачене, а в
tickets квитка ще немає. Демо-покупець один, а ліміт – 6 місць за 15 хвилин (С-06), тож N ≤ 6.
"""

import argparse
import re
import time

import httpx

BASE = "http://localhost:8080"
EVENT = "00000000-0000-0000-0000-000000000018"
FREE_SEAT = re.compile(r'value="([^"|]+\|\d+\|\d+)"(?![^>]*disabled)')


def csrf(html: str) -> str:
    return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)


def purchase_lag(client: httpx.Client) -> tuple[str, float]:
    hall = client.get(f"/events/{EVENT}/").text
    seat = FREE_SEAT.findall(hall)[-1]
    headers = {"Referer": f"{BASE}/events/{EVENT}/"}
    reserved = client.post(f"/events/{EVENT}/", data={"seat": seat, "csrfmiddlewaretoken": csrf(hall)}, headers=headers)
    order_id = re.search(r"/orders/([0-9a-f-]{36})/pay/", reserved.text).group(1)
    paid = client.post(f"/orders/{order_id}/pay/", data={"csrfmiddlewaretoken": csrf(reserved.text)}, headers=headers)
    paid_at = time.perf_counter()
    if "Оплату виконано" not in paid.text:
        raise RuntimeError(f"Оплата не пройшла для {seat}")
    while "<code>" not in client.get(f"/tickets/orders/{order_id}/").text:
        if time.perf_counter() - paid_at > 30:
            raise RuntimeError("Квиток не з'явився за 30 с – чи працюють tickets-consumer і Redis?")
        time.sleep(0.015)
    return seat, (time.perf_counter() - paid_at) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--purchases", type=int, default=5)
    args = parser.parse_args()
    lags = []
    with httpx.Client(base_url=BASE, timeout=15) as client:
        for _ in range(args.purchases):
            seat, lag = purchase_lag(client)
            lags.append(lag)
            print(f"{seat}: квиток з'явився через {lag:.0f} мс після «Оплату виконано»")
    print(f"мінімум {min(lags):.0f} мс, середнє {sum(lags) / len(lags):.0f} мс, максимум {max(lags):.0f} мс")


if __name__ == "__main__":
    main()
