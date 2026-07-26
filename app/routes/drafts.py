from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_admin, get_current_user
from app.database import get_db
from app.models import Draft

router = APIRouter(prefix="/drafts")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
@require_admin
async def drafts_list(request: Request, db: Session = Depends(get_db)):
    drafts = db.query(Draft).order_by(Draft.slug, Draft.is_reminder).all()
    return templates.TemplateResponse(request, "drafts/list.html", {
        "user":    get_current_user(request),
        "drafts":  drafts,
    })


@router.get("/new")
@require_admin
async def draft_new(request: Request):
    return templates.TemplateResponse(request, "drafts/form.html", {
        "user":    get_current_user(request),
        "draft":   None,
        "action":  "/drafts/new",
        "title":   "Yeni Taslak",
    })


@router.post("/new")
@require_admin
async def draft_create(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    slug: str = Form(...),
    is_reminder: str = Form(""),
    subject: str = Form(...),
    body_html: str = Form(...),
    cc: str = Form(""),
    bcc: str = Form(""),
    attachments: str = Form(""),
):
    slug_clean = slug.strip().lower()
    draft = Draft(
        name        = name.strip(),
        slug        = slug_clean,
        is_reminder = bool(is_reminder),
        subject     = subject.strip(),
        body_html   = body_html,
        cc          = cc.strip(),
        bcc         = bcc.strip(),
        attachments = attachments.strip(),
    )
    db.add(draft)
    db.commit()
    return RedirectResponse("/drafts", status_code=302)


@router.get("/{draft_id}/edit")
@require_admin
async def draft_edit(request: Request, draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter_by(id=draft_id).first()
    if not draft:
        return RedirectResponse("/drafts", status_code=302)
    return templates.TemplateResponse(request, "drafts/form.html", {
        "user":    get_current_user(request),
        "draft":   draft,
        "action":  f"/drafts/{draft_id}/edit",
        "title":   "Taslağı Düzenle",
    })


@router.post("/{draft_id}/edit")
@require_admin
async def draft_update(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    slug: str = Form(...),
    is_reminder: str = Form(""),
    subject: str = Form(...),
    body_html: str = Form(...),
    cc: str = Form(""),
    bcc: str = Form(""),
    attachments: str = Form(""),
):
    draft = db.query(Draft).filter_by(id=draft_id).first()
    if not draft:
        return RedirectResponse("/drafts", status_code=302)
    draft.name        = name.strip()
    draft.slug        = slug.strip().lower()
    draft.is_reminder = bool(is_reminder)
    draft.subject     = subject.strip()
    draft.body_html   = body_html
    draft.cc          = cc.strip()
    draft.bcc         = bcc.strip()
    draft.attachments = attachments.strip()
    draft.updated_at  = datetime.utcnow()
    db.commit()
    return RedirectResponse("/drafts", status_code=302)


@router.post("/{draft_id}/delete")
@require_admin
async def draft_delete(request: Request, draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter_by(id=draft_id).first()
    if draft:
        db.delete(draft)
        db.commit()
    return RedirectResponse("/drafts", status_code=302)
