import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _fmt(value: float, digits: int = 0) -> str:
    if digits == 0:
        return f"{round(value):,}"
    return f"{round(value, digits):,}"


def _asset_version() -> str:
    """A content hash of the app's JS/CSS, computed at startup. Used as a cache-
    busting query string on asset URLs so a deploy is always picked up fresh —
    the URL changes whenever the files change, defeating any HTTP/SW cache."""
    h = hashlib.md5()
    for name in ("app.js", "styles.css"):
        path = STATIC_DIR / name
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:8]


templates.env.filters["num"] = _fmt
templates.env.globals["asset_v"] = _asset_version()
