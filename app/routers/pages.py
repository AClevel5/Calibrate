from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MEALS
from ..services.days import get_day_summary, get_week_summaries, week_bounds
from ..templating import templates

router = APIRouter()


@router.get("/")
def home():
    return RedirectResponse(url=f"/day/{date.today().isoformat()}")


@router.get("/day/{day}")
def day_view(day: date, request: Request, db: Session = Depends(get_db)):
    summary = get_day_summary(db, day)
    # group entries by meal for display
    by_meal = {m: [] for m in MEALS}
    for e in summary.entries:
        by_meal.get(e.meal, by_meal["snack"]).append(e)
    return templates.TemplateResponse(
        request,
        "day.html",
        {
            "summary": summary,
            "by_meal": by_meal,
            "meals": MEALS,
            "today": date.today(),
            "prev_day": day - timedelta(days=1),
            "next_day": day + timedelta(days=1),
        },
    )


@router.get("/week/{day}")
def week_view(day: date, request: Request, db: Session = Depends(get_db)):
    summaries = get_week_summaries(db, day)
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
            "summaries": summaries,
            "totals": totals,
            "monday": monday,
            "sunday": sunday,
            "today": date.today(),
            "prev_week": monday - timedelta(days=7),
            "next_week": monday + timedelta(days=7),
        },
    )
