from datetime import date

from pydantic import BaseModel, Field


class Product(BaseModel):
    """Normalized product nutrition (per 100 g) from any source."""

    source: str
    source_id: str | None = None
    name: str
    brand: str | None = None
    serving_size_g: float | None = None
    serving_label: str | None = None
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0


class EntryCreate(BaseModel):
    log_date: date
    meal: str = "snack"
    name: str
    brand: str | None = None
    quantity_g: float = Field(gt=0)
    # per-100 g nutrition; the server scales it to quantity_g on save
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    source: str | None = None
    source_id: str | None = None


class EntryUpdate(BaseModel):
    quantity_g: float = Field(gt=0)
    meal: str | None = None


class EnergyUpdate(BaseModel):
    record_date: date
    active_kcal: float = 0
    resting_kcal: float = 0
    source: str = "manual"


class FavoriteCreate(BaseModel):
    name: str
    brand: str | None = None
    serving_size_g: float | None = None
    default_qty_g: float = 100
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    source: str | None = None
    source_id: str | None = None


class CustomFoodCreate(BaseModel):
    name: str
    brand: str | None = None
    serving_size_g: float = Field(gt=0, default=100)
    # nutrition entered PER SERVING (as printed on the label); the server stores
    # it normalized to per 100 g.
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0


class GoalUpdate(BaseModel):
    goal_calories: float = 0
    goal_protein: float = 0
    goal_carbs: float = 0
    goal_fat: float = 0
