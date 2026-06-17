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
    food_item_id: int | None = None


class EnergyUpdate(BaseModel):
    record_date: date
    active_kcal: float = 0
    resting_kcal: float = 0
    source: str = "manual"
