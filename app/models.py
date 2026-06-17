from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

MEALS = ("breakfast", "lunch", "dinner", "snack")


class FoodItem(Base):
    """A cached, canonical food/product. Nutrition is stored per 100 g so any
    logged quantity can be scaled from it."""

    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))  # off | usda | manual
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)  # barcode / fdcId
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)

    serving_size_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    serving_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # per 100 g
    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FoodEntry(Base):
    """A single logged consumption. Nutrition is snapshotted (already scaled to
    the logged quantity) so editing/refreshing the cached FoodItem never rewrites
    history."""

    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(20), default="snack")

    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_g: Mapped[float] = mapped_column(Float, default=0)

    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)

    food_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EnergyRecord(Base):
    """Per-day energy expenditure. TDEE = active + resting, typically pushed from
    Apple Health (Active Energy + Resting Energy) but editable by hand."""

    __tablename__ = "energy_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    active_kcal: Mapped[float] = mapped_column(Float, default=0)
    resting_kcal: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | apple_health
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def tdee(self) -> float:
        return (self.active_kcal or 0) + (self.resting_kcal or 0)
