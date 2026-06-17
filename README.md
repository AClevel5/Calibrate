# ⚖︎ Calibrate

A calorie & macro tracking **PWA** built with FastAPI. It shows your daily **net
calories** (consumed vs. TDEE), tracks macros automatically from logged foods,
supports **barcode scanning**, and gives a **week-at-a-glance** view. Designed to
deploy on [Railway](https://railway.app).

## Features

- **Daily view** — calories consumed vs. TDEE (Active + Resting energy) → net kcal,
  shown as a deficit/surplus, with protein/carbs/fat totals.
- **Food logging** — search [Open Food Facts](https://world.openfoodfacts.org) and
  [USDA FoodData Central](https://fdc.nal.usda.gov/), or scan a barcode with your
  phone camera. Nutrition is pulled per 100 g and scaled to the quantity you log.
- **Automatic macros** — every entry contributes to the day's macro totals.
- **History** — each day is stored; navigate back/forward by day or week.
- **Week at a glance** — net calories and macros for each day of the week, plus
  weekly totals and a daily average.
- **Installable PWA** — add to your home screen; works offline for viewing.

## Tech stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2** — SQLite locally, Postgres in production (auto-detected from
  `DATABASE_URL`)
- **Jinja2** server-rendered templates + vanilla JS (no build step)
- Barcode scanning via [`html5-qrcode`](https://github.com/mebjas/html5-qrcode)
- Python **3.14**

## Local development

```bash
cd Calibrate
python -m venv .venv && source .venv/bin/activate   # already created
pip install -r requirements.txt
cp .env.example .env                                 # then edit as needed
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — it redirects to today's view. The SQLite database
(`calibrate.db`) is created automatically on first run.

> **Barcode scanning needs HTTPS or `localhost`.** Browsers only grant camera
> access on a secure origin. `localhost` counts; a LAN IP like `192.168.x.x` does
> not — use the deployed HTTPS URL on your phone, or a tunnel (e.g. `cloudflared`).

### Optional: USDA FoodData Central

Open Food Facts works with no key. For the USDA fallback/enrichment, grab a free
key at <https://fdc.nal.usda.gov/api-key-signup.html> and set `FDC_API_KEY` in
`.env`.

## Apple Health → TDEE

**Apple Health (HealthKit) has no public web API**, so a PWA can't read it
directly. The supported path is an **Apple Shortcuts automation** that pushes your
daily energy to Calibrate:

1. In the **Shortcuts** app, create a Personal Automation → **Time of Day**
   (e.g. 11:45 PM daily).
2. Add **Find Health Samples**: *Active Energy*, Today → sum → store as variable.
   Repeat for **Resting Energy** (Basal Energy Burned).
3. Add **Get Contents of URL**:
   - URL: `https://<your-app>.up.railway.app/api/health/energy`
   - Method: `POST`, Request Body: `JSON`
   - Fields:
     - `record_date` → today's date as `YYYY-MM-DD`
     - `active_kcal` → the Active Energy total
     - `resting_kcal` → the Resting Energy total
   - If you set `HEALTH_INGEST_TOKEN`, add header
     `Authorization: Bearer <token>`.
4. Turn off "Ask Before Running" so it runs unattended.

You can also enter Active/Resting energy **manually** from the daily view (tap the
⚡ energy row).

### Ingest endpoint

```
POST /api/health/energy
{ "record_date": "2026-06-17", "active_kcal": 620, "resting_kcal": 1700 }
```

`record_date` is unique — re-posting the same day updates it (idempotent).

## Deploying to Railway

1. Push this folder to a Git repo and create a Railway project from it.
2. Add the **PostgreSQL** plugin — Railway injects `DATABASE_URL` automatically
   (the app rewrites the legacy `postgres://` prefix for psycopg3).
3. Set variables as needed: `FDC_API_KEY`, `HEALTH_INGEST_TOKEN`.
4. Railway uses Nixpacks; `railway.json` / `Procfile` define the start command
   (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`). Health check: `/health`.

## Project layout

```
app/
  main.py            FastAPI app, lifespan (creates tables), PWA root files
  config.py          env-driven settings
  database.py        engine/session, postgres:// → postgresql+psycopg:// rewrite
  models.py          FoodItem, FoodEntry, EnergyRecord
  schemas.py         Pydantic request/response models
  services/
    foodfacts.py     Open Food Facts + USDA lookups (normalized to per-100 g)
    nutrition.py     macro math (scaling, day rollups)
    days.py          daily & weekly summaries
  routers/
    pages.py         HTML views (/day/{date}, /week/{date})
    api.py           JSON API (foods, entries, energy, health ingest)
  templates/         base / day / week
  static/            styles.css, app.js, sw.js, manifest, icons
```

## API quick reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/day/{date}` | Daily view |
| GET | `/week/{date}` | Week-at-a-glance |
| GET | `/api/foods/barcode/{code}` | Look up a product by barcode |
| GET | `/api/foods/search?q=` | Search foods |
| POST | `/api/entries` | Log a food (per-100 g nutrition, scaled by `quantity_g`) |
| DELETE | `/api/entries/{id}` | Remove a logged food |
| POST | `/api/energy` | Set Active/Resting energy for a date (manual) |
| POST | `/api/health/energy` | Apple Health ingest (token-guarded) |

## Roadmap ideas

- Calorie/macro **goals** and progress rings
- **Recent & favorite foods** for one-tap logging
- Editable serving sizes (servings vs. grams)
- User accounts / auth (currently single-user)
- Charts/trends over weeks and months
