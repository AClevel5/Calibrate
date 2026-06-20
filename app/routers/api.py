from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_api_user
from ..models import EnergyRecord, Favorite, FoodEntry, User
from ..schemas import EnergyUpdate, EntryCreate, EntryUpdate, FavoriteCreate, Product
from ..services import foodfacts
from ..services.nutrition import Macros, scale_per_100g

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- food lookup


@router.get("/foods/barcode/{barcode}", response_model=Product)
async def barcode_lookup(barcode: str, user: User = Depends(require_api_user)):
    product = await foodfacts.lookup_barcode(barcode.strip())
    if not product:
        raise HTTPException(404, detail="No product found for that barcode.")
    return product


@router.get("/foods/search", response_model=list[Product])
async def food_search(q: str = Query(min_length=2), user: User = Depends(require_api_user)):
    return await foodfacts.search_foods(q.strip())


# ---------------------------------------------------------------- entries


@router.post("/entries")
def create_entry(
    e: EntryCreate, user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    if e.meal not in ("breakfast", "lunch", "dinner", "snack"):
        e.meal = "snack"
    scaled = scale_per_100g(
        Macros(e.calories, e.protein, e.carbs, e.fat), e.quantity_g
    ).rounded()
    entry = FoodEntry(
        user_id=user.id,
        log_date=e.log_date,
        meal=e.meal,
        name=e.name,
        brand=e.brand,
        quantity_g=e.quantity_g,
        calories=scaled.calories,
        protein=scaled.protein,
        carbs=scaled.carbs,
        fat=scaled.fat,
        cal_per100=e.calories,
        pro_per100=e.protein,
        carb_per100=e.carbs,
        fat_per100=e.fat,
        source=e.source,
        source_id=e.source_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.patch("/entries/{entry_id}")
def update_entry(
    entry_id: int,
    payload: EntryUpdate,
    user: User = Depends(require_api_user),
    db: Session = Depends(get_db),
):
    entry = db.get(FoodEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, detail="Entry not found.")
    # Re-scale from the stored per-100 g snapshot; fall back to back-calculating
    # it from the existing totals if the snapshot is missing (older entries).
    def per100(snapshot: float, total: float) -> float:
        if snapshot:
            return snapshot
        return (total / entry.quantity_g * 100) if entry.quantity_g else 0.0

    base = Macros(
        per100(entry.cal_per100, entry.calories),
        per100(entry.pro_per100, entry.protein),
        per100(entry.carb_per100, entry.carbs),
        per100(entry.fat_per100, entry.fat),
    )
    scaled = scale_per_100g(base, payload.quantity_g).rounded()
    entry.quantity_g = payload.quantity_g
    entry.calories = scaled.calories
    entry.protein = scaled.protein
    entry.carbs = scaled.carbs
    entry.fat = scaled.fat
    if payload.meal in ("breakfast", "lunch", "dinner", "snack"):
        entry.meal = payload.meal
    db.commit()
    return {"id": entry.id, "calories": entry.calories}


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int, user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    entry = db.get(FoodEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, detail="Entry not found.")
    db.delete(entry)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- recent & favorites


@router.get("/recent", response_model=list[Product])
def recent_foods(
    user: User = Depends(require_api_user),
    db: Session = Depends(get_db),
    limit: int = 12,
):
    """Distinct recently-logged foods (most recent first), as per-100 g products."""
    rows = db.scalars(
        select(FoodEntry)
        .where(FoodEntry.user_id == user.id)
        .order_by(FoodEntry.created_at.desc())
        .limit(120)
    )
    seen: set[tuple[str, str]] = set()
    out: list[Product] = []
    for e in rows:
        key = (e.name.lower(), (e.brand or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Product(
                source=e.source or "manual",
                source_id=e.source_id,
                name=e.name,
                brand=e.brand,
                serving_size_g=e.quantity_g,
                calories=e.cal_per100,
                protein=e.pro_per100,
                carbs=e.carb_per100,
                fat=e.fat_per100,
            )
        )
        if len(out) >= limit:
            break
    return out


@router.get("/favorites")
def list_favorites(
    user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    favs = db.scalars(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.name)
    )
    return [
        {
            "id": f.id, "name": f.name, "brand": f.brand,
            "serving_size_g": f.serving_size_g, "default_qty_g": f.default_qty_g,
            "calories": f.calories, "protein": f.protein, "carbs": f.carbs, "fat": f.fat,
            "source": f.source, "source_id": f.source_id,
        }
        for f in favs
    ]


@router.post("/favorites")
def add_favorite(
    f: FavoriteCreate, user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.name == f.name,
            Favorite.brand == f.brand,
        )
    )
    if existing:
        return {"id": existing.id, "duplicate": True}
    fav = Favorite(
        user_id=user.id,
        name=f.name,
        brand=f.brand,
        serving_size_g=f.serving_size_g,
        default_qty_g=f.default_qty_g or (f.serving_size_g or 100),
        calories=f.calories,
        protein=f.protein,
        carbs=f.carbs,
        fat=f.fat,
        source=f.source,
        source_id=f.source_id,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return {"id": fav.id}


@router.delete("/favorites/{fav_id}")
def delete_favorite(
    fav_id: int, user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    fav = db.get(Favorite, fav_id)
    if not fav or fav.user_id != user.id:
        raise HTTPException(404, detail="Favorite not found.")
    db.delete(fav)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- energy / TDEE


def _upsert_energy(db: Session, user_id: int, payload: EnergyUpdate) -> EnergyRecord:
    record = db.scalar(
        select(EnergyRecord).where(
            EnergyRecord.user_id == user_id,
            EnergyRecord.record_date == payload.record_date,
        )
    )
    if record is None:
        record = EnergyRecord(user_id=user_id, record_date=payload.record_date)
        db.add(record)
    record.active_kcal = payload.active_kcal
    record.resting_kcal = payload.resting_kcal
    record.source = payload.source
    db.commit()
    db.refresh(record)
    return record


@router.post("/energy")
def update_energy(
    payload: EnergyUpdate, user: User = Depends(require_api_user), db: Session = Depends(get_db)
):
    record = _upsert_energy(db, user.id, payload)
    return {"date": record.record_date.isoformat(), "tdee": record.tdee}


@router.post("/health/energy")
def ingest_apple_health(
    payload: EnergyUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Ingest endpoint for an Apple Shortcuts automation that pushes daily Active +
    Resting energy. Authenticated by the user's personal ingest token (Bearer)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="Missing bearer token.")
    token = authorization.removeprefix("Bearer ").strip()
    user = db.scalar(select(User).where(User.ingest_token == token))
    if not user:
        raise HTTPException(401, detail="Invalid ingest token.")
    payload.source = "apple_health"
    record = _upsert_energy(db, user.id, payload)
    return {
        "date": record.record_date.isoformat(),
        "active_kcal": record.active_kcal,
        "resting_kcal": record.resting_kcal,
        "tdee": record.tdee,
    }
