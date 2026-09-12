"""
Bulk send engine — adapted from original engine.py.
Key changes:
  - template_no (int 1-4) → segment (str) matched against Draft.slug in DB
  - subject/cc/bcc/attachments come from the matched Draft record
  - logging writes to LogEntry table + Python logger
  - stop_event checked each iteration for graceful stop
"""

import colorsys
import logging
import random
import threading
import time
from datetime import datetime, date
from typing import Optional

import pandas as pd

from app.services import sheets as sheets_svc
from app.services import gmail as gmail_svc

logger = logging.getLogger(__name__)

# Rows filled with any shade of red, yellow, or cyan are treated as "do not
# mail" markers — checked by hue so light/dark variants all match, not just
# one exact RGB value.
_SKIP_HUE_RANGES = [
    (0, 15), (345, 360),   # red
    (45, 75),              # yellow
    (165, 195),            # cyan / camgöbeği
]


def _is_skip_color(rgb: Optional[tuple]) -> bool:
    if not rgb:
        return False
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    if s < 0.15 or v < 0.15:
        return False  # near white/gray/black — not an intentional marker
    hue_deg = h * 360
    return any(lo <= hue_deg <= hi for lo, hi in _SKIP_HUE_RANGES)


class SendResult:
    def __init__(self):
        self.sent = 0
        self.reminded = 0
        self.skipped = 0
        self.failed = 0
        self.responded = 0

    def summary(self) -> str:
        return (
            f"Gönderilen: {self.sent} | Hatırlatma: {self.reminded} | "
            f"Atlanan: {self.skipped} | Başarısız: {self.failed} | "
            f"Dönüş alınmış: {self.responded}"
        )


def _db_log(db, run_id: int, level: str, message: str):
    from app.models import LogEntry
    entry = LogEntry(run_id=run_id, level=level, message=message, timestamp=datetime.utcnow())
    db.add(entry)
    db.commit()
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(message)


def _parse_date(val) -> Optional[date]:
    if not val or str(val).strip() in ("", "nan"):
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _days_since(last_date: date) -> int:
    return (date.today() - last_date).days


def _get_sender_info(sender_name: str, senders_df: pd.DataFrame, col: dict) -> Optional[dict]:
    for _, row in senders_df.iterrows():
        name_in_sheet = str(row.get(col["name"], "")).strip()
        if name_in_sheet.lower() == sender_name.lower():
            return {
                "name":      name_in_sheet,
                "email":     str(row.get(col["email"], "")).strip(),
                "password":  str(row.get(col["password"], "")).strip(),
                "title":     str(row.get(col["title"], "")).strip(),
                "signature": str(row.get(col["signature"], "")).strip(),
            }
    return None


def _get_sender_usage_today(db, sender_email: str) -> int:
    from app.models import SenderUsage
    today_str = date.today().isoformat()
    row = db.query(SenderUsage).filter_by(sender_email=sender_email, date=today_str).first()
    return row.count if row else 0


def _increment_sender_usage(db, sender_email: str):
    from app.models import SenderUsage
    today_str = date.today().isoformat()
    row = db.query(SenderUsage).filter_by(sender_email=sender_email, date=today_str).first()
    if row:
        row.count += 1
    else:
        row = SenderUsage(sender_email=sender_email, date=today_str, count=1)
        db.add(row)
    db.commit()


def _choose_draft(segment: str, is_reminder: bool, db):
    from app.models import Draft
    slug = segment.strip().lower()
    return (
        db.query(Draft)
        .filter(Draft.slug.ilike(slug), Draft.is_reminder == is_reminder)
        .first()
    )


def build_settings_dict(db) -> dict:
    """Build the engine settings dict from DB settings."""
    from app.models import Setting
    s = {r.key: r.value for r in db.query(Setting).all()}
    return {
        "spreadsheet_id":   s.get("spreadsheet_id", ""),
        "credentials_file": s.get("credentials_file", "credentials.json"),
        "token_file":       s.get("token_file", "token.json"),
        "sheet_names": {
            "senders":    s.get("sheet_senders", "Kişi Bilgileri"),
            "recipients": s.get("sheet_recipients", "Alıcı Listesi"),
        },
        "sender_columns": {
            "name":      s.get("col_sender_name", "İsim"),
            "title":     s.get("col_sender_title", "Ünvan"),
            "email":     s.get("col_sender_email", "Gmail"),
            "password":  s.get("col_sender_password", "App Password"),
            "signature": s.get("col_sender_signature", "İmza Linki"),
        },
        "recipient_columns": {
            "name":       s.get("col_recipient_name", "Kişi Adı"),
            "company":    s.get("col_recipient_company", "Şirket"),
            "position":   s.get("col_recipient_position", "Pozisyon"),
            "email":      s.get("col_recipient_email", "E-posta"),
            "last_date":  s.get("col_recipient_last_date", "Son Mail Tarihi"),
            "mail_count": s.get("col_recipient_mail_count", "Mail Sayısı"),
            "message_id": s.get("col_recipient_message_id", "Message-ID"),
            "entered_by": s.get("col_recipient_entered_by", "Datayı Giren"),
            "response":   s.get("col_recipient_response", "Dönüş Durumu"),
            "segment":    s.get("col_recipient_segment", "Segment"),
        },
        "global_cc":  [e.strip() for e in s.get("email_cc", "").split(",") if e.strip()],
        "global_bcc": [e.strip() for e in s.get("email_bcc", "").split(",") if e.strip()],
        "header_image": s.get("header_image", ""),
        "min_wait_seconds":              int(s.get("min_wait_seconds", "12")),
        "max_wait_seconds":              int(s.get("max_wait_seconds", "24")),
        "reminder_after_days":           int(s.get("reminder_after_days", "2")),
        "max_mails_per_run":             int(s.get("max_mails_per_run", "50")),
        "max_mails_per_sender_per_day":  int(s.get("max_mails_per_sender_per_day", "450")),
    }


def run_bulk_send(
    settings: dict,
    service,
    db,
    run_id: int,
    stop_event: threading.Event = None,
) -> SendResult:
    result = SendResult()

    def log(level: str, msg: str):
        _db_log(db, run_id, level, msg)

    recipient_cols = settings["recipient_columns"]
    sender_cols    = settings["sender_columns"]
    sheet_names    = settings["sheet_names"]
    spreadsheet_id = settings["spreadsheet_id"]
    min_wait       = settings["min_wait_seconds"]
    max_wait       = max(settings["max_wait_seconds"], min_wait)
    reminder_days  = settings["reminder_after_days"]
    max_per_run    = settings["max_mails_per_run"]
    max_per_sender_day = settings["max_mails_per_sender_per_day"]
    global_cc      = settings["global_cc"]
    global_bcc     = settings["global_bcc"]
    header_image_link = settings.get("header_image", "")

    header_image_data = None
    if header_image_link:
        header_image_data = gmail_svc.download_image(header_image_link)
        if not header_image_data:
            log("WARNING", "⚠️ Başlık fotoğrafı indirilemedi, mailler fotoğrafsız gönderilecek.")

    log("INFO", "📋 Sheets okunuyor...")
    recipients_df = sheets_svc.read_sheet(service, spreadsheet_id, sheet_names["recipients"])
    senders_df    = sheets_svc.read_sheet(service, spreadsheet_id, sheet_names["senders"])

    if recipients_df is None or senders_df is None:
        log("ERROR", "❌ Sheet verisi okunamadı, iptal edildi.")
        return result

    headers = list(recipients_df.columns)
    row_colors = sheets_svc.get_row_colors(service, spreadsheet_id, sheet_names["recipients"], len(recipients_df))
    total_sent_this_run = 0
    attempts_this_run = 0

    for idx, row in recipients_df.iterrows():
        if stop_event and stop_event.is_set():
            log("WARNING", "⛔ Gönderim durduruldu.")
            break

        if total_sent_this_run >= max_per_run:
            log("WARNING", f"⚠️ Maksimum limit ({max_per_run}) doldu.")
            break

        label_early = f"[Satır {idx+2}]"
        if _is_skip_color(row_colors[idx] if idx < len(row_colors) else None):
            log("INFO", f"{label_early}: 🎨 Satır renkle işaretlenmiş (kırmızı/sarı/camgöbeği), atlandı.")
            result.skipped += 1
            continue

        recipient_name    = str(row.get(recipient_cols["name"],    "")).strip()
        company           = str(row.get(recipient_cols["company"], "")).strip()
        position          = str(row.get(recipient_cols["position"],"")).strip()
        to_email          = str(row.get(recipient_cols["email"],   "")).strip()
        entered_by        = str(row.get(recipient_cols["entered_by"], "")).strip()
        response_raw      = str(row.get(recipient_cols["response"], "")).strip()
        segment_raw       = str(row.get(recipient_cols["segment"], "")).strip()
        message_id_stored = str(row.get(recipient_cols["message_id"], "")).strip()

        try:
            mail_count = int(row.get(recipient_cols["mail_count"], 0))
        except (ValueError, TypeError):
            mail_count = 0

        last_date = _parse_date(row.get(recipient_cols["last_date"], ""))
        label = f"[Satır {idx+2}] {recipient_name or to_email}"

        if not to_email or to_email == "nan":
            log("WARNING", f"{label}: ⚠️ E-posta adresi boş, atlandı.")
            result.failed += 1
            continue

        if response_raw == "1" or response_raw.strip().lower() == "dönüş var":
            log("INFO", f"{label}: ✅ Dönüş alınmış, atlandı.")
            result.responded += 1
            continue

        sender_info = _get_sender_info(entered_by, senders_df, sender_cols)
        if not sender_info:
            log("WARNING", f"{label}: ⚠️ '{entered_by}' bulunamadı, atlandı.")
            result.failed += 1
            continue

        if not sender_info["email"] or not sender_info["password"]:
            log("WARNING", f"{label}: ⚠️ Gönderici bilgisi eksik, atlandı.")
            result.failed += 1
            continue

        sender_usage_today = _get_sender_usage_today(db, sender_info["email"])
        if sender_usage_today >= max_per_sender_day:
            log("WARNING", f"{label}: 🚫 '{sender_info['email']}' bugünkü gönderim limitine ({max_per_sender_day}) ulaştı, atlandı.")
            result.skipped += 1
            continue

        # Decide: first email or reminder
        is_reminder = False
        if mail_count == 0:
            pass  # send first
        elif 1 <= mail_count <= 3:
            if last_date and _days_since(last_date) >= reminder_days:
                is_reminder = True
            else:
                days_left = reminder_days - (_days_since(last_date) if last_date else 0)
                log("INFO", f"{label}: ⏳ Hatırlatma için {days_left} gün daha var, atlandı.")
                result.skipped += 1
                continue
        else:
            log("INFO", f"{label}: 🔒 Mail limiti dolmuş (mail_count={mail_count}), atlandı.")
            result.skipped += 1
            continue

        if not segment_raw:
            log("WARNING", f"{label}: ⚠️ Segment sütunu boş, atlandı.")
            result.skipped += 1
            continue

        draft = _choose_draft(segment_raw, is_reminder, db)
        if not draft:
            kind = "hatırlatma" if is_reminder else "ilk mail"
            log("WARNING", f"{label}: ⚠️ '{segment_raw}' için {kind} taslağı bulunamadı, atlandı.")
            result.skipped += 1
            continue

        placeholders = {
            "Kişi Adı":     recipient_name,
            "Şirket Adı":   company,
            "Pozisyon":     position,
            "Datayı Giren": sender_info["name"],
            "Ünvan":        sender_info["title"],
        }

        sig_data = None
        if sender_info["signature"]:
            sig_data = gmail_svc.download_image(sender_info["signature"])

        html_body, sig_bytes = gmail_svc.build_html_body(draft.body_html, placeholders, sig_data, header_image_data)

        if attempts_this_run > 0:
            delay = random.randint(min_wait, max_wait)
            log("INFO", f"⏳ Spam koruması: {delay} sn bekleniyor...")
            time.sleep(delay)
        attempts_this_run += 1

        draft_cc = [e.strip() for e in draft.cc.split(",") if e.strip()]
        draft_bcc = [e.strip() for e in draft.bcc.split(",") if e.strip()]
        all_cc = list(set(global_cc + draft_cc))
        all_bcc = list(set(global_bcc + draft_bcc))
        attachment_paths = [p.strip() for p in draft.attachments.split(",") if p.strip()]

        reply_to = message_id_stored if (is_reminder and message_id_stored) else None

        success, new_message_id = gmail_svc.send_mail(
            sender_email        = sender_info["email"],
            sender_password     = sender_info["password"],
            to_email            = to_email,
            subject             = draft.subject,
            html_body           = html_body,
            signature_data      = sig_bytes,
            header_image_data   = header_image_data,
            cc                  = all_cc,
            bcc                 = all_bcc,
            attachments         = attachment_paths,
            reply_to_message_id = reply_to,
        )

        if success:
            _increment_sender_usage(db, sender_info["email"])
            new_count = mail_count + 1
            today_str = datetime.today().strftime("%Y-%m-%d")

            if is_reminder:
                # Keep original ID so all reminders chain to the first email's thread.
                # Fall back to the reply's ID only if original was never stored.
                stored_id = message_id_stored if message_id_stored else new_message_id
            else:
                # Gmail SMTP replaces our custom Message-ID with its own. Fetch the
                # real one via IMAP so In-Reply-To headers in reminders actually work.
                real_id = gmail_svc.fetch_actual_sent_message_id(
                    sender_info["email"], sender_info["password"], to_email
                )
                stored_id = real_id if real_id else new_message_id
                log("INFO", f"{label}: 📌 Message-ID: {stored_id[:50]}")

            updated = sheets_svc.update_recipient_row(
                service        = service,
                spreadsheet_id = spreadsheet_id,
                sheet_name     = sheet_names["recipients"],
                row_index      = idx,
                col_mapping    = recipient_cols,
                headers        = headers,
                mail_count     = new_count,
                last_date      = today_str,
                message_id     = stored_id,
            )
            action = "🔔 Hatırlatma" if is_reminder else "📧 İlk mail"
            log("INFO", f"{label}: {action} gönderildi. Sheets güncellendi: {updated}")
            if is_reminder:
                result.reminded += 1
            else:
                result.sent += 1
            total_sent_this_run += 1
        else:
            log("ERROR", f"{label}: ❌ Gönderilemedi.")
            result.failed += 1

    log("INFO", f"\n🏁 Gönderim tamamlandı. {result.summary()}")
    return result
