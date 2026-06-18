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


def get_day_summary(db: Session, user_id: int, day: date) -> DaySummary:
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
    return DaySummary(
        day=day,
        consumed=consumed,
        active_kcal=energy.active_kcal if energy else 0.0,
        resting_kcal=energy.resting_kcal if energy else 0.0,
        entries=entries,
    )


def week_bounds(day: date) -> tuple[date, date]:
    """Monday-to-Sunday week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def get_week_summaries(db: Session, user_id: int, day: date) -> list[DaySummary]:
    monday, _ = week_bounds(day)
    return [get_day_summary(db, user_id, monday + timedelta(days=i)) for i in range(7)]
