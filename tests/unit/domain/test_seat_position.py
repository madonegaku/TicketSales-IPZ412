"""Тести об'єкта-значення SeatPosition: рівність за значенням та інваріанти."""

import pytest

from ticketing.domain.exceptions import InvalidSeatPositionError
from ticketing.domain.value_objects import SeatPosition


def test_same_positions_are_equal_and_usable_as_dict_key():
    seats = {SeatPosition("Партер", 5, 12): "вільне"}

    assert SeatPosition("Партер", 5, 12) in seats


@pytest.mark.parametrize("row, number", [(0, 1), (1, 0), (-3, 5)])
def test_row_or_number_below_one_is_rejected(row, number):
    with pytest.raises(InvalidSeatPositionError):
        SeatPosition("Партер", row, number)


@pytest.mark.parametrize("sector", ["", "   "])
def test_blank_sector_is_rejected(sector):
    with pytest.raises(InvalidSeatPositionError):
        SeatPosition(sector, 1, 1)