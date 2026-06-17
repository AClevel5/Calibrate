from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _fmt(value: float, digits: int = 0) -> str:
    if digits == 0:
        return f"{round(value):,}"
    return f"{round(value, digits):,}"


templates.env.filters["num"] = _fmt
