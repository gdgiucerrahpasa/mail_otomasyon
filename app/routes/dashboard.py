from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_admin, get_current_user
from app.database import get_db
from app import state
from app.scheduler import start_run_in_background
from app.models import Run, LogEntry

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
@require_admin
async def dashboard(request: Request, db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.started_at.desc()).limit(10).all()
    current_run_id = state.get_current_run_id()
    return templates.TemplateResponse(request, "dashboard.html", {
        "user":           get_current_user(request),
        "runs":           runs,
        "is_running":     state.is_running(),
        "current_run_id": current_run_id,
    })


@router.post("/run/start")
@require_admin
async def run_start(request: Request):
    started = start_run_in_background()
    if not started:
        return HTMLResponse('<p class="text-yellow">⚠️ Gönderim zaten çalışıyor.</p>', status_code=200)
    return RedirectResponse("/", status_code=302)


@router.post("/run/stop")
@require_admin
async def run_stop(request: Request):
    state.request_stop()
    return RedirectResponse("/", status_code=302)


@router.get("/run/status", response_class=HTMLResponse)
@require_admin
async def run_status(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: status badge + new log lines."""
    current_run_id = state.get_current_run_id()
    after_id = int(request.query_params.get("after_id", 0))

    new_entries = []
    if current_run_id:
        new_entries = (
            db.query(LogEntry)
            .filter(LogEntry.run_id == current_run_id, LogEntry.id > after_id)
            .order_by(LogEntry.id.asc())
            .all()
        )

    return templates.TemplateResponse(request, "partials/run_status.html", {
        "is_running":     state.is_running(),
        "current_run_id": current_run_id,
        "new_entries":    new_entries,
        "last_id":        new_entries[-1].id if new_entries else after_id,
    })
