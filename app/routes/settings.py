from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_admin, get_current_user
from app.database import get_db
from app.models import Setting

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="app/templates")

SETTING_KEYS = [
    "spreadsheet_id", "credentials_file", "token_file",
    "sheet_senders", "sheet_recipients",
    "col_recipient_name", "col_recipient_company", "col_recipient_position",
    "col_recipient_email", "col_recipient_last_date", "col_recipient_mail_count",
    "col_recipient_message_id", "col_recipient_entered_by", "col_recipient_response",
    "col_recipient_segment",
    "col_sender_name", "col_sender_title", "col_sender_email",
    "col_sender_password", "col_sender_signature",
    "email_cc", "email_bcc",
    "wait_seconds_between_senders", "reminder_after_days", "max_mails_per_run",
    "schedule_enabled", "schedule_interval_hours",
]


def _get_all(db: Session) -> dict:
    return {s.key: s.value for s in db.query(Setting).all()}


@router.get("")
@require_admin
async def settings_page(request: Request, db: Session = Depends(get_db), saved: str = ""):
    cfg = _get_all(db)
    return templates.TemplateResponse(request, "settings.html", {
        "user":    get_current_user(request),
        "cfg":     cfg,
        "saved":   saved == "1",
    })


@router.post("")
@require_admin
async def settings_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    for key in SETTING_KEYS:
        val = str(form.get(key, "")).strip()
        # checkbox: present = true, absent = false
        if key == "schedule_enabled":
            val = "true" if form.get("schedule_enabled") else "false"
        row = db.query(Setting).filter_by(key=key).first()
        if row:
            row.value = val
        else:
            db.add(Setting(key=key, value=val))
    db.commit()

    from app.scheduler import apply_schedule_from_db
    apply_schedule_from_db()

    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/test-connection", response_class=HTMLResponse)
@require_admin
async def test_connection(request: Request, db: Session = Depends(get_db)):
    cfg = _get_all(db)
    try:
        from app.services.sheets import authenticate, get_sheet_names
        service = authenticate(cfg.get("credentials_file", "credentials.json"),
                               cfg.get("token_file", "token.json"))
        names = get_sheet_names(service, cfg.get("spreadsheet_id", ""))
        return HTMLResponse(
            f'<span class="text-green">✅ Bağlantı başarılı. Sayfalar: {", ".join(names)}</span>'
        )
    except Exception as e:
        return HTMLResponse(f'<span class="text-red">❌ Bağlantı hatası: {e}</span>')
