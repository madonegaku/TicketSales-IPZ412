"""Тести сутності Seat: дозволені та заборонені переходи стану."""

import pytest

from ticketing.domain.event import Seat, SeatStatus
from ticketing.domain.exceptions import InvalidSeatTransitionError, SeatNotAvailableError
from ticketing.domain.value_objects import SeatPosition


def make_seat(status=SeatStatus.AVAILABLE):
    return Seat(SeatPosition("Партер", 5, 12), "Партер", status)


def test_available_seat_can_be_reserved():
    seat = make_seat()

    seat.reserve()

    assert seat.status is SeatStatus.RESERVED


@pytest.mark.parametrize("status", [SeatStatus.RESERVED, SeatStatus.SOLD])
def test_occupied_seat_cannot_be_reserved_again(status):
    seat = make_seat(status)

    with pytest.raises(SeatNotAvailableError, match="Партер, ряд 5, № 12"):
        seat.reserve()


@pytest.mark.parametrize("status", [SeatStatus.AVAILABLE, SeatStatus.SOLD])
def test_only_reserved_seat_can_be_sold(status):
    seat = make_seat(status)

    with pytest.raises(InvalidSeatTransitionError):
        seat.sell()


@pytest.mark.parametrize("status", [SeatStatus.RESERVED, SeatStatus.SOLD])
def test_occupied_seat_can_be_released(status):
    seat = make_seat(status)

    seat.release()

    assert seat.status is SeatStatus.AVAILABLE


def test_available_seat_cannot_be_released():
    seat = make_seat()

    with pytest.raises(InvalidSeatTransitionError):
        seat.release()