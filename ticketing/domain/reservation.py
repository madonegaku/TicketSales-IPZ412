"""Резервування: тимчасове закріплення місць заходу за покупцем."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ticketing.domain.exceptions import ReservationLimitError
from ticketing.domain.value_objects import SeatPosition

RESERVATION_TTL = timedelta(minutes=15)
MAX_SEATS_PER_BUYER = 6


@dataclass(eq=False)
class Reservation:
    """Резервування – окремий агрегат, посилається на захід лише за ідентифікатором.

    Інваріанти: від 1 до 6 місць; разом з місцями, які покупець уже утримує, –
    не більше 6 (С-06); діє 15 хвилин від створення, потім прострочене.
    """

    id: UUID
    event_id: UUID
    buyer_id: UUID
    positions: tuple[SeatPosition, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not 1 <= len(self.positions) <= MAX_SEATS_PER_BUYER:
            raise ReservationLimitError(
                f"Резервування має містити від 1 до {MAX_SEATS_PER_BUYER} місць."
            )

    @classmethod
    def create(
        cls,
        event_id: UUID,
        buyer_id: UUID,
        positions: list[SeatPosition],
        now: datetime,
        seats_already_held: int,
    ) -> "Reservation":
        """Створює резервування з урахуванням місць, які покупець уже утримує."""
        if seats_already_held + len(positions) > MAX_SEATS_PER_BUYER:
            raise ReservationLimitError(
                f"Один покупець може утримувати не більше {MAX_SEATS_PER_BUYER} місць."
            )
        return cls(uuid4(), event_id, buyer_id, tuple(positions), now)

    @property
    def expires_at(self) -> datetime:
        return self.created_at + RESERVATION_TTL

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at