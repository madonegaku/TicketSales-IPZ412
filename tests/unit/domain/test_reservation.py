"""Тести агрегату Reservation: ліміт місць (С-06) і строк дії 15 хвилин."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ticketing.domain.exceptions import ReservationLimitError
from ticketing.domain.reservation import Reservation
from ticketing.domain.value_objects import SeatPosition

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def reserve(seat_count, already_held=0):
    positions = [SeatPosition("Партер", 1, number) for number in range(1, seat_count + 1)]
    return Reservation.create(uuid4(), uuid4(), positions, NOW, already_held)


@pytest.mark.parametrize("seat_count", [1, 6])
def test_reservation_with_one_to_six_seats_is_created(seat_count):
    reservation = reserve(seat_count)

    assert len(reservation.positions) == seat_count


@pytest.mark.parametrize("seat_count", [0, 7])
def test_reservation_with_zero_or_more_than_six_seats_is_rejected(seat_count):
    with pytest.raises(ReservationLimitError):
        reserve(seat_count)


def test_buyer_can_hold_exactly_six_seats_in_total():
    reservation = reserve(2, already_held=4)

    assert len(reservation.positions) == 2


def test_buyer_cannot_hold_more_than_six_seats_in_total():
    with pytest.raises(ReservationLimitError):
        reserve(2, already_held=5)


def test_reservation_expires_exactly_after_fifteen_minutes():
    reservation = reserve(1)

    assert not reservation.is_expired(NOW + timedelta(minutes=14, seconds=59))
    assert reservation.is_expired(NOW + timedelta(minutes=15))