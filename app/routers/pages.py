from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_page_user
from ..models import MEALS, CustomFood, User
from ..services.days import get_day_summary, get_week_summaries, week_bounds
from ..templating import templates

router = APIRouter()


@router.get("/")
def home(user: User = Depends(require_page_user)):
    return RedirectResponse(url=f"/day/{date.today().isoformat()}")


@router.get("/day/{day}")
def day_view(
    day: date,
    request: Request,
    user: User = Depends(require_page_user),
    db: Session = Depends(get_db),
):
    summary = get_day_summary(db, user.id, day)
    by_meal = {m: [] for m in MEALS}
    for e in summary.entries:
        by_meal.get(e.meal, by_meal["snack"]).append(e)
    return templates.TemplateResponse(
        request,
        "day.html",
        {
            "user": user,
            "summary": summary,
            "by_meal": by_meal,
            "meals": MEALS,
            "today": date.today(),
            "prev_day": day - timedelta(days=1),
            "next_day": day + timedelta(days=1),
        },
    )


@router.get("/week/{day}")
def week_view(
    day: date,
    request: Request,
    user: User = Depends(require_page_user),
    db: Session = Depends(get_db),
):
    summaries = get_week_summaries(db, user.id, day)
    monday, sunday = week_bounds(day)
    totals = {
        "consumed": sum(s.consumed.calories for s in summaries),
        "tdee": sum(s.tdee for s in summaries),
        "protein": sum(s.consumed.protein for s in summaries),
        "carbs": sum(s.consumed.carbs for s in summaries),
        "fat": sum(s.consumed.fat for s in summaries),
    }
    totals["net"] = totals["consumed"] - totals["tdee"]
    return templates.TemplateResponse(
        request,
        "week.html",
        {
            "user": user,
            "summaries": summaries,
            "totals": totals,
            "monday": monday,
            "sunday": sunday,
            "today": date.today(),
            "prev_week": monday - timedelta(days=7),
            "next_week": monday + timedelta(days=7),
        },
    )


@router.get("/settings")
def settings_page(
    request: Request,
    user: User = Depends(require_page_user),
    db: Session = Depends(get_db),
    saved: bool = False,
):
    ingest_url = str(request.base_url).rstrip("/") + "/api/health/energy"
    custom_foods = db.scalars(
        select(CustomFood).where(CustomFood.user_id == user.id).order_by(CustomFood.name)
    ).all()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "today": date.today(),
            "ingest_url": ingest_url,
            "saved": saved,
            "custom_foods": custom_foods,
        },
    )


@router.post("/settings")
def save_settings(
    request: Request,
    user: User = Depends(require_page_user),
    db: Session = Depends(get_db),
    goal_calories: float = Form(0),
    goal_protein: float = Form(0),
    goal_carbs: float = Form(0),
    goal_fat: float = Form(0),
):
    user.goal_calories = max(0, goal_calories)
    user.goal_protein = max(0, goal_protein)
    user.goal_carbs = max(0, goal_carbs)
    user.goal_fat = max(0, goal_fat)
    db.commit()
    return RedirectResponse("/settings?saved=true", status_code=303)
