from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

MEALS = ("breakfast", "lunch", "dinner", "snack")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Per-user secret for the Apple Health ingest endpoint.
    ingest_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Daily goals (0 = unset). Calories is an intake target; macros in grams.
    goal_calories: Mapped[float] = mapped_column(Float, default=0)
    goal_protein: Mapped[float] = mapped_column(Float, default=0)
    goal_carbs: Mapped[float] = mapped_column(Float, default=0)
    goal_fat: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
    history. `*_per100` keep the unscaled values so the food can be re-logged."""

    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    log_date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(20), default="snack")

    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_g: Mapped[float] = mapped_column(Float, default=0)

    # totals (scaled to quantity_g)
    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)

    # per-100 g snapshot (for re-logging from history)
    cal_per100: Mapped[float] = mapped_column(Float, default=0)
    pro_per100: Mapped[float] = mapped_column(Float, default=0)
    carb_per100: Mapped[float] = mapped_column(Float, default=0)
    fat_per100: Mapped[float] = mapped_column(Float, default=0)

    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Favorite(Base):
    """A user-saved food for one-tap logging. Nutrition stored per 100 g."""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "name", "brand", name="uq_fav_user_food"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)

    serving_size_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_qty_g: Mapped[float] = mapped_column(Float, default=100)

    # per 100 g
    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)

    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CustomFood(Base):
    """A food the user created by hand (or from a scanned nutrition label) when it
    wasn't in any database. Nutrition is stored per 100 g; it shows up in search."""

    __tablename__ = "custom_foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)

    serving_size_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    # per 100 g
    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EnergyRecord(Base):
    """Per-day energy expenditure. TDEE = active + resting, typically pushed from
    Apple Health (Active Energy + Resting Energy) but editable by hand."""

    __tablename__ = "energy_records"
    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_energy_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    record_date: Mapped[date] = mapped_column(Date, index=True)
    active_kcal: Mapped[float] = mapped_column(Float, default=0)
    resting_kcal: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | apple_health
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def tdee(self) -> float:
        return (self.active_kcal or 0) + (self.resting_kcal or 0)
