"""Обробники HTTP-запитів: перетворюють дані форм на DTO і викликають сценарії.

Бізнес-умов тут немає: правила перевіряє домен, а view лише показує
користувачеві повідомлення доменного винятку.
"""

from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST


from ticketing.application.get_hall_layout import GetHallLayout
from ticketing.application.pay_order import PayOrder, PayOrderCommand
from ticketing.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from ticketing.domain.exceptions import DomainError, NotFoundError

# У ЛР 2 автентифікації ще немає, тому всі запити – від одного демонстраційного покупця.
DEMO_BUYER_ID = UUID("00000000-0000-0000-0000-0000000000b1")


def parse_seats(values: list[str]) -> tuple[tuple[str, int, int], ...]:
    """Перетворює значення чекбоксів «Партер|3|7» на (сектор, ряд, номер)."""
    seats = []
    for value in values:
        sector, row, number = value.split("|")
        seats.append((sector, int(row), int(number)))
    return tuple(seats)


def hall(
    request: HttpRequest,
    event_id: UUID,
    *,
    get_hall_layout: GetHallLayout,
    reserve_seats: ReserveSeats,
) -> HttpResponse:
    """Сторінка вибору місць: показує схему залу й резервує обрані місця."""
    error = None
    if request.method == "POST":
        try:
            seats = parse_seats(request.POST.getlist("seat"))
            result = reserve_seats.execute(ReserveSeatsCommand(event_id, DEMO_BUYER_ID, seats))
            return render(request, "presentation/order.html", {"order": result})
        except ValueError:
            error = "Некоректний формат вибору місць."
        except DomainError as exc:
            error = str(exc)

    try:
        layout = get_hall_layout.execute(event_id)
    except NotFoundError:
        raise Http404("Захід не знайдено.")
    return render(request, "presentation/hall.html", {"layout": layout, "error": error})


@require_POST
def pay(request: HttpRequest, order_id: UUID, *, pay_order: PayOrder) -> HttpResponse:
    """Оплачує замовлення та показує коди квитків або причину відмови."""
    try:
        result = pay_order.execute(PayOrderCommand(order_id))
    except DomainError as exc:
        return render(request, "presentation/payment.html", {"error": str(exc)})
    return render(request, "presentation/payment.html", {"ticket_codes": result.ticket_codes})