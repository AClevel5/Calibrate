"""Rollups for the daily and weekly views (scoped to a user)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EnergyRecord, FoodEntry
from .nutrition import Macros


@dataclass
class DaySummary:
    day: date
    consumed: Macros = field(default_factory=Macros)
    active_kcal: float = 0.0
    resting_kcal: float = 0.0
    entries: list[FoodEntry] = field(default_factory=list)

    @property
    def tdee(self) -> float:
        return self.active_kcal + self.resting_kcal

    @property
    def net(self) -> float:
        """Consumed minus burned. Negative = deficit, positive = surplus."""
        return self.consumed.calories - self.tdee


def get_day_summary(
    db: Session, user_id: int, day: date, resting_bmr: float = 0.0
) -> DaySummary:
    entries = list(
        db.scalars(
            select(FoodEntry)
            .where(FoodEntry.user_id == user_id, FoodEntry.log_date == day)
            .order_by(FoodEntry.created_at)
        )
    )
    consumed = Macros()
    for e in entries:
        consumed = consumed + Macros(e.calories, e.protein, e.carbs, e.fat)

    energy = db.scalar(
        select(EnergyRecord).where(
            EnergyRecord.user_id == user_id, EnergyRecord.record_date == day
        )
    )
    active = energy.active_kcal if energy else 0.0
    if resting_bmr > 0:
        # Fixed-BMR mode: use the user's BMR for resting on any real day and
        # ignore the watch's (unreliable) resting reading — only Active energy
        # comes from Apple Health. Empty/future days stay at 0.
        resting = resting_bmr if (energy is not None or entries) else 0.0
    else:
        # No BMR set → fall back to whatever resting the watch synced.
        resting = energy.resting_kcal if energy else 0.0
    return DaySummary(
        day=day,
        consumed=consumed,
        active_kcal=active,
        resting_kcal=resting,
        entries=entries,
    )


def week_bounds(day: date) -> tuple[date, date]:
    """Monday-to-Sunday week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def get_week_summaries(
    db: Session, user_id: int, day: date, resting_bmr: float = 0.0
) -> list[DaySummary]:
    monday, _ = week_bounds(day)
    return [
        get_day_summary(db, user_id, monday + timedelta(days=i), resting_bmr)
        for i in range(7)
    ]
