import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import state
from app.auth import verify_password, APP_USERNAME

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host if request.client else "unknown"

    if state.is_login_blocked(ip):
        logger.warning(f"Giriş engellendi (çok fazla hatalı deneme): {ip}")
        return templates.TemplateResponse(
            request, "login.html", {"error": "too_many_attempts"}, status_code=429
        )

    if username == APP_USERNAME and verify_password(password):
        state.clear_login_failures(ip)
        request.session["user"] = username
        return RedirectResponse("/", status_code=302)

    state.register_login_failure(ip)
    logger.warning(f"Hatalı giriş denemesi: {ip}")
    return templates.TemplateResponse(
        request, "login.html", {"error": "wrong_credentials"}, status_code=401
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
