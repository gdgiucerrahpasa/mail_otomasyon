import os
from functools import wraps

from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH", "")


def verify_password(plain: str) -> bool:
    if not APP_PASSWORD_HASH:
        return False
    return _pwd_ctx.verify(plain, APP_PASSWORD_HASH)


def get_current_user(request: Request) -> str | None:
    return request.session.get("user")


def require_admin(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_current_user(request)
        is_htmx = request.headers.get("HX-Request")
        if not user:
            if is_htmx:
                return HTMLResponse(
                    '<p class="text-red text-xs">⚠️ Oturum süresi doldu. Sayfayı yenileyin.</p>',
                    status_code=200,
                )
            return RedirectResponse("/login", status_code=302)
        return await func(request, *args, **kwargs)
    return wrapper
