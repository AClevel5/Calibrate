"""Food lookups against Open Food Facts (primary) and USDA FoodData Central
(fallback / search enrichment).

Both sources are normalized to a per-100 g `Product`.
"""

import re

import httpx

from ..config import settings
from ..schemas import Product

# Matches any non-ASCII letter — accents (café, Müsli) or non-Latin scripts
# (Cyrillic, Arabic, CJK). Used to weed out non-English names.
_NON_ASCII = re.compile(r"[^\x00-\x7f]")

OFF_BASE = "https://world.openfoodfacts.org"
# Search the US database so results are English-market products. Barcode lookups
# still use the global DB (a scanned product should resolve regardless of market).
OFF_SEARCH_BASE = "https://us.openfoodfacts.org"
FDC_BASE = "https://api.nal.usda.gov/fdc/v1"
USER_AGENT = "Calibrate/0.1 (calorie tracker)"
TIMEOUT = httpx.Timeout(8.0)


# ---------------------------------------------------------------- Open Food Facts


def _looks_english(name: str) -> bool:
    """Heuristic English-name check used to filter search results.

    OFF's language metadata is unreliable (foreign products get tagged `en`, and
    native names get copied into the `product_name_en` field), so we judge by the
    name itself: reject any non-ASCII letters, which removes accented foreign
    names (Kéfir, Pâte) and non-Latin scripts (Arabic, Cyrillic, CJK).
    """
    return bool(name) and not _NON_ASCII.search(name)


def _off_to_product(barcode: str, product: dict) -> Product | None:
    n = product.get("nutriments", {})
    calories = n.get("energy-kcal_100g")
    if calories is None and n.get("energy_100g") is not None:
        # OFF sometimes only stores kJ; convert.
        calories = n["energy_100g"] / 4.184
    # Prefer the explicit English name when present.
    name = (
        product.get("product_name_en")
        or product.get("product_name")
        or product.get("generic_name")
    )
    if not name:
        return None
    return Product(
        source="off",
        source_id=barcode,
        name=name.strip(),
        brand=(product.get("brands") or None),
        serving_size_g=_to_float(product.get("serving_quantity")),
        serving_label=product.get("serving_size"),
        calories=_to_float(calories),
        protein=_to_float(n.get("proteins_100g")),
        carbs=_to_float(n.get("carbohydrates_100g")),
        fat=_to_float(n.get("fat_100g")),
    )


async def off_by_barcode(client: httpx.AsyncClient, barcode: str) -> Product | None:
    url = f"{OFF_BASE}/api/v2/product/{barcode}.json"
    r = await client.get(url, params={"fields": "product_name,generic_name,brands,"
                                               "serving_quantity,serving_size,nutriments"})
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("status") != 1:
        return None
    return _off_to_product(barcode, data.get("product", {}))


async def off_search(client: httpx.AsyncClient, query: str, limit: int = 12) -> list[Product]:
    url = f"{OFF_SEARCH_BASE}/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "lc": "en",  # prefer English fields
        # Over-fetch so we still have enough after the English-name filter.
        "page_size": max(limit * 3, 30),
        "fields": "code,product_name,product_name_en,generic_name,brands,"
        "serving_quantity,serving_size,nutriments",
    }
    r = await client.get(url, params=params)
    if r.status_code != 200:
        return []
    out: list[Product] = []
    for p in r.json().get("products", []):
        prod = _off_to_product(p.get("code", ""), p)
        if prod and prod.calories and _looks_english(prod.name):
            out.append(prod)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- USDA FoodData Central

# FDC macro nutrient numbers (stable across datasets)
_FDC_MACROS = {"203": "protein", "204": "fat", "205": "carbs"}
# Energy can appear under several numbers; branded foods use 208 (kcal), while
# Foundation/SR foods often only carry Atwater energy (957/958) or kJ (268).
_FDC_ENERGY_KCAL = ("208", "957", "958")  # priority order, all kcal

# Surface generic whole foods ("Bananas, raw") above branded packaged products,
# which is usually what you want to log. Lower sorts first.
_FDC_TYPE_RANK = {"Foundation": 0, "SR Legacy": 1, "Survey (FNDDS)": 2, "Branded": 3}


def _fdc_to_product(food: dict) -> Product | None:
    macros = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
    kcal_by_num: dict[str, float] = {}
    kj_value = 0.0
    for fn in food.get("foodNutrients", []):
        number = str(fn.get("nutrientNumber") or fn.get("number") or "")
        unit = (fn.get("unitName") or "").upper()
        val = _to_float(fn.get("value") or fn.get("amount"))
        if number in _FDC_MACROS:
            macros[_FDC_MACROS[number]] = val
        elif number in _FDC_ENERGY_KCAL and unit in ("KCAL", ""):
            kcal_by_num[number] = val
        elif number == "268" and unit in ("KJ", "KILOJOULE"):  # Energy in kJ
            kj_value = kj_value or val
    calories = next((kcal_by_num[n] for n in _FDC_ENERGY_KCAL if kcal_by_num.get(n)), 0.0)
    if not calories and kj_value:
        calories = kj_value / 4.184

    name = food.get("description")
    if not name:
        return None
    return Product(
        source="usda",
        source_id=str(food.get("fdcId")) if food.get("fdcId") else None,
        name=name.strip().title(),
        brand=(food.get("brandOwner") or food.get("brandName") or None),
        serving_size_g=_to_float(food.get("servingSize"))
        if (food.get("servingSizeUnit") or "").lower() in ("g", "gram", "grams")
        else None,
        serving_label=food.get("householdServingFullText"),
        calories=calories,
        **macros,
    )


async def usda_search(client: httpx.AsyncClient, query: str, limit: int = 12) -> list[Product]:
    if not settings.fdc_api_key:
        return []
    r = await client.get(
        f"{FDC_BASE}/foods/search",
        params={
            "api_key": settings.fdc_api_key,
            "query": query,
            # Over-fetch: some rows get dropped for missing energy data.
            "pageSize": max(limit * 2, 25),
            "dataType": "Branded,Foundation,SR Legacy",
        },
    )
    if r.status_code != 200:
        return []
    # Stable sort keeps USDA's relevance order within each data type while
    # floating generic whole foods above branded products.
    foods = sorted(
        r.json().get("foods", []),
        key=lambda f: _FDC_TYPE_RANK.get(f.get("dataType"), 9),
    )
    out: list[Product] = []
    for food in foods:
        prod = _fdc_to_product(food)
        if prod and prod.calories:
            out.append(prod)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- public API


async def lookup_barcode(barcode: str) -> Product | None:
    """Open Food Facts first; fall back to a USDA UPC search."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        product = await off_by_barcode(client, barcode)
        if product and product.calories:
            return product
        usda = await usda_search(client, barcode, limit=1)
        if usda:
            return usda[0]
        return product  # may be None, or an OFF hit with no calories


async def search_foods(query: str, limit: int = 12) -> list[Product]:
    """USDA-primary food search (clean, all-English, includes generic whole
    foods). Open Food Facts only tops up the list when USDA comes up short — and
    is skipped entirely when no FDC key is set, OFF becomes the sole source."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        usda = await usda_search(client, query, limit)
        remaining = limit - len(usda)
        off = await off_search(client, query, remaining) if remaining > 0 else []

    seen: set[tuple[str, str]] = set()
    results: list[Product] = []
    for prod in [*usda, *off]:  # USDA first
        key = (prod.name.lower(), (prod.brand or "").lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(prod)
    return results[:limit]


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
