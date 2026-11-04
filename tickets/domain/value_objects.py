"""Об'єкти-значення доменної моделі tickets."""

from dataclasses import dataclass

from tickets.domain.exceptions import InvalidSeatPositionError


@dataclass(frozen=True)
class SeatPosition:
    """Позиція місця, на яке видано квиток.

    Інваріанти: сектор – непорожня назва; ряд і номер місця – цілі числа, не менші за 1.
    """

    sector: str
    row: int
    number: int

    def __post_init__(self) -> None:
        if not self.sector.strip():
            raise InvalidSeatPositionError("Сектор має бути непорожньою назвою.")
        if self.row < 1 or self.number < 1:
            raise InvalidSeatPositionError("Ряд і номер місця мають бути не меншими за 1.")

    def __str__(self) -> str:
        return f"{self.sector}, ряд {self.row}, № {self.number}"