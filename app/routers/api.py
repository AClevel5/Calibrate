from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import EnergyRecord, FoodEntry, FoodItem
from ..schemas import EnergyUpdate, EntryCreate, Product
from ..services import foodfacts
from ..services.nutrition import Macros, scale_per_100g

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- food lookup


@router.get("/foods/barcode/{barcode}", response_model=Product)
async def barcode_lookup(barcode: str):
    product = await foodfacts.lookup_barcode(barcode.strip())
    if not product:
        raise HTTPException(404, detail="No product found for that barcode.")
    return product


@router.get("/foods/search", response_model=list[Product])
async def food_search(q: str = Query(min_length=2)):
    return await foodfacts.search_foods(q.strip())


# ---------------------------------------------------------------- entries


def _cache_food_item(db: Session, e: EntryCreate) -> int | None:
    """Upsert a FoodItem cache row for sourced products (so repeat lookups are local)."""
    if e.food_item_id:
        return e.food_item_id
    return None


@router.post("/entries")
def create_entry(e: EntryCreate, db: Session = Depends(get_db)):
    if e.meal not in ("breakfast", "lunch", "dinner", "snack"):
        e.meal = "snack"
    scaled = scale_per_100g(
        Macros(e.calories, e.protein, e.carbs, e.fat), e.quantity_g
    ).rounded()
    entry = FoodEntry(
        log_date=e.log_date,
        meal=e.meal,
        name=e.name,
        brand=e.brand,
        quantity_g=e.quantity_g,
        calories=scaled.calories,
        protein=scaled.protein,
        carbs=scaled.carbs,
        fat=scaled.fat,
        food_item_id=_cache_food_item(db, e),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(FoodEntry, entry_id)
    if not entry:
        raise HTTPException(404, detail="Entry not found.")
    db.delete(entry)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- energy / TDEE


def _upsert_energy(db: Session, payload: EnergyUpdate) -> EnergyRecord:
    record = db.scalar(
        select(EnergyRecord).where(EnergyRecord.record_date == payload.record_date)
    )
    if record is None:
        record = EnergyRecord(record_date=payload.record_date)
        db.add(record)
    record.active_kcal = payload.active_kcal
    record.resting_kcal = payload.resting_kcal
    record.source = payload.source
    db.commit()
    db.refresh(record)
    return record


@router.post("/energy")
def update_energy(payload: EnergyUpdate, db: Session = Depends(get_db)):
    record = _upsert_energy(db, payload)
    return {"date": record.record_date.isoformat(), "tdee": record.tdee}


@router.post("/health/energy")
def ingest_apple_health(
    payload: EnergyUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Ingest endpoint for an Apple Shortcuts automation that pushes daily
    Active Energy + Resting Energy. Guard with HEALTH_INGEST_TOKEN when public."""
    if settings.health_ingest_token:
        expected = f"Bearer {settings.health_ingest_token}"
        if authorization != expected:
            raise HTTPException(401, detail="Invalid or missing ingest token.")
    payload.source = "apple_health"
    record = _upsert_energy(db, payload)
    return {
        "date": record.record_date.isoformat(),
        "active_kcal": record.active_kcal,
        "resting_kcal": record.resting_kcal,
        "tdee": record.tdee,
    }
