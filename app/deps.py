"""Auth dependencies: resolve the current user from the signed session cookie.

- `optional_user` — returns the User or None.
- `require_page_user` — raises NotAuthenticated (→ redirect to /login) for HTML pages.
- `require_api_user` — raises 401 for JSON API routes.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


class NotAuthenticated(Exception):
    """Raised by page routes when no user is logged in; handled by a redirect."""


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_page_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise NotAuthenticated()
    return user


def require_api_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user
