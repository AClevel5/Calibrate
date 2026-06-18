from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import hash_password, new_ingest_token, verify_password
from ..templating import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request, error: str | None = None):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password."}, status_code=401
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/register")
def register_form(request: Request, error: str | None = None):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {"error": error})


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if len(password) < 8:
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "Password must be at least 8 characters."}, status_code=400,
        )
    if db.scalar(select(User).where(User.email == email)):
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "An account with that email already exists."}, status_code=400,
        )
    user = User(
        email=email,
        password_hash=hash_password(password),
        ingest_token=new_ingest_token(),
    )
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
