from datetime import timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_admin, get_current_user
from app.database import get_db
from app.models import Run, LogEntry

router = APIRouter(prefix="/logs")
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["tr_dt"] = lambda dt: dt + timedelta(hours=3)

PAGE_SIZE = 200


@router.get("")
@require_admin
async def logs_page(
    request: Request,
    db: Session = Depends(get_db),
    run_id: int = 0,
    level: str = "",
    page: int = 1,
):
    runs = db.query(Run).order_by(Run.started_at.desc()).limit(50).all()

    q = db.query(LogEntry)
    if run_id:
        q = q.filter(LogEntry.run_id == run_id)
    if level:
        q = q.filter(LogEntry.level == level.upper())

    total = q.count()
    entries = q.order_by(LogEntry.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(request, "logs.html", {
        "user":        get_current_user(request),
        "runs":        runs,
        "entries":     entries,
        "filter_run":  run_id,
        "filter_level": level,
        "page":        page,
        "total_pages": total_pages,
        "total":       total,
    })
