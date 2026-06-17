"""Food lookups against Open Food Facts (primary) and USDA FoodData Central
(fallback / search enrichment).

Both sources are normalized to a per-100 g `Product`.
"""

import httpx

from ..config import settings
from ..schemas import Product

OFF_BASE = "https://world.openfoodfacts.org"
FDC_BASE = "https://api.nal.usda.gov/fdc/v1"
USER_AGENT = "Calibrate/0.1 (calorie tracker)"
TIMEOUT = httpx.Timeout(8.0)


# ---------------------------------------------------------------- Open Food Facts


def _off_to_product(barcode: str, product: dict) -> Product | None:
    n = product.get("nutriments", {})
    calories = n.get("energy-kcal_100g")
    if calories is None and n.get("energy_100g") is not None:
        # OFF sometimes only stores kJ; convert.
        calories = n["energy_100g"] / 4.184
    name = product.get("product_name") or product.get("generic_name")
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
    url = f"{OFF_BASE}/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
        "fields": "code,product_name,generic_name,brands,serving_quantity,serving_size,nutriments",
    }
    r = await client.get(url, params=params)
    if r.status_code != 200:
        return []
    out: list[Product] = []
    for p in r.json().get("products", []):
        prod = _off_to_product(p.get("code", ""), p)
        if prod and prod.calories:
            out.append(prod)
    return out


# ---------------------------------------------------------------- USDA FoodData Central

# FDC nutrient numbers (stable across datasets)
_FDC_NUTRIENTS = {"208": "calories", "203": "protein", "204": "fat", "205": "carbs"}


def _fdc_to_product(food: dict) -> Product | None:
    macros = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for fn in food.get("foodNutrients", []):
        number = str(fn.get("nutrientNumber") or fn.get("number") or "")
        key = _FDC_NUTRIENTS.get(number)
        if key:
            macros[key] = _to_float(fn.get("value") or fn.get("amount"))
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
            "pageSize": limit,
            "dataType": "Branded,Foundation,SR Legacy",
        },
    )
    if r.status_code != 200:
        return []
    out: list[Product] = []
    for food in r.json().get("foods", []):
        prod = _fdc_to_product(food)
        if prod and prod.calories:
            out.append(prod)
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
    """Combined search across both sources, de-duplicated by (name, brand)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        off = await off_search(client, query, limit)
        usda = await usda_search(client, query, limit)

    seen: set[tuple[str, str]] = set()
    results: list[Product] = []
    for prod in [*off, *usda]:
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
