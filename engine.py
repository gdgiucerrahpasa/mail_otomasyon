"""
engine.py — Toplu mail gönderim motoru
  - Her alıcı için uygun template ve gönderici seçimi
  - 3 gün hatırlatma kontrolü
  - Gönderim sonrası Sheets güncelleme
  - Her gönderici değiştiğinde 3 dk bekleme
"""

import logging
import time
from datetime import datetime, date
from typing import Optional
import pandas as pd

import sheets
import gmail_sender

logger = logging.getLogger(__name__)


class SendResult:
    def __init__(self):
        self.sent = 0
        self.reminded = 0
        self.skipped = 0
        self.failed = 0
        self.responded = 0
        self.log_lines: list[str] = []

    def add_log(self, msg: str):
        self.log_lines.append(msg)
        logger.info(msg)

    def summary(self) -> str:
        return (
            f"Gönderilen: {self.sent} | Hatırlatma: {self.reminded} | "
            f"Atlanan: {self.skipped} | Başarısız: {self.failed} | "
            f"Dönüş alınmış: {self.responded}"
        )


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
    """Kişi Bilgileri tablosundan gönderici bilgisini döner."""
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


def _choose_template(template_no: int, is_reminder: bool, templates: dict) -> Optional[str]:
    """
    is_reminder=True  → reminder template
    template_no=1     → template_1
    template_no=2     → template_2
    template_no=3     → template_3
    template_no=4     → template_4
    Geçersiz değer    → None (atlanır)
    """
    if is_reminder:
        return templates.get("reminder")

    tmpl_map = {1: "template_1", 2: "template_2", 3: "template_3", 4: "template_4"}
    key = tmpl_map.get(template_no)
    return templates.get(key) if key else None


def run_bulk_send(config: dict, service, log_callback=None) -> SendResult:
    """
    Ana gönderim döngüsü.
    log_callback: UI'da canlı log göstermek için çağrılır (str → None)
    """
    result = SendResult()

    def log(msg: str):
        result.add_log(msg)
        if log_callback:
            log_callback(msg)

    # --- Sheet config ---
    spreadsheet_id  = config["google_sheets"]["spreadsheet_id"]
    sheet_names     = config["sheet_names"]
    sender_cols     = config["sender_columns"]
    recipient_cols  = config["recipient_columns"]
    email_cfg       = config["email"]
    settings        = config["settings"]

    wait_between    = int(settings.get("wait_seconds_between_senders", 180))
    reminder_days   = int(settings.get("reminder_after_days", 3))
    max_per_run     = int(settings.get("max_mails_per_run", 50))

    # --- Verileri oku ---
    log("📋 Sheets okunuyor...")
    recipients_df = sheets.read_sheet(service, spreadsheet_id, sheet_names["recipients"])
    senders_df    = sheets.read_sheet(service, spreadsheet_id, sheet_names["senders"])

    if recipients_df is None or senders_df is None:
        log("❌ Sheet verisi okunamadı, iptal edildi.")
        return result

    headers = list(recipients_df.columns)

    # Gönderim sayacı: hangi gönderici en son gönderdi (sıralama için)
    last_sender_email: Optional[str] = None
    total_sent_this_run = 0

    for idx, row in recipients_df.iterrows():
        if total_sent_this_run >= max_per_run:
            log(f"⚠️  Maksimum gönderim limitine ulaşıldı ({max_per_run}).")
            break

        # --- Alıcı bilgileri ---
        recipient_name    = str(row.get(recipient_cols["name"],    "")).strip()
        company           = str(row.get(recipient_cols["company"], "")).strip()
        position          = str(row.get(recipient_cols["position"],"")).strip()
        to_email          = str(row.get(recipient_cols["email"],   "")).strip()
        entered_by        = str(row.get(recipient_cols["entered_by"], "")).strip()
        response_raw      = str(row.get(recipient_cols["response"], "")).strip()
        message_id_stored = str(row.get(recipient_cols["message_id"], "")).strip()

        mail_count_raw = row.get(recipient_cols["mail_count"], 0)
        try:
            mail_count = int(mail_count_raw)
        except (ValueError, TypeError):
            mail_count = 0

        template_no_raw = row.get(recipient_cols["template_no"], 1)
        try:
            template_no = int(template_no_raw)
        except (ValueError, TypeError):
            template_no = 1  # Varsayılan şablon 1

        last_date_raw = row.get(recipient_cols["last_date"], "")
        last_date = _parse_date(last_date_raw)

        label = f"[Satır {idx+2}] {recipient_name or to_email}"

        # --- Temel kontroller ---
        if not to_email or to_email == "nan":
            log(f"{label}: ⚠️  E-posta adresi boş, atlandı.")
            result.failed += 1
            continue

        if response_raw == "1" or response_raw.strip().lower() == "dönüş var":
            log(f"{label}: ✅ Dönüş alınmış, atlandı.")
            result.responded += 1
            continue

        # --- Gönderici bilgisi ---
        sender_info = _get_sender_info(entered_by, senders_df, sender_cols)
        if not sender_info:
            log(f"{label}: ⚠️  '{entered_by}' için Kişi Bilgileri'nde kayıt bulunamadı, atlandı.")
            result.failed += 1
            continue

        if not sender_info["email"] or not sender_info["password"]:
            log(f"{label}: ⚠️  Gönderici e-posta veya şifre boş, atlandı.")
            result.failed += 1
            continue

        # --- Mail gönderilecek mi? ---
        is_reminder = False

        if mail_count == 0:
            # İlk mail
            should_send = True
        elif 1 <= mail_count <= 4:
            # Hatırlatma kontrolü: 3+ gün geçmeli, 4. mails olmamalı
            if last_date and _days_since(last_date) >= reminder_days:
                should_send = True
                is_reminder = True
            else:
                days_left = reminder_days - (_days_since(last_date) if last_date else 0)
                log(f"{label}: ⏳ Hatırlatma için {days_left} gün daha var, atlandı.")
                result.skipped += 1
                continue
        else:
            log(f"{label}: 🔒 Mail limiti dolmuş (mail_count={mail_count}), atlandı.")
            result.skipped += 1
            continue

        # --- Template seç ---
        template = _choose_template(template_no, is_reminder, email_cfg["templates"])
        if not template:
            log(f"{label}: ⚠️  Uygun template bulunamadı (template_no={template_no}), atlandı.")
            result.skipped += 1
            continue

        # --- Placeholders ---
        placeholders = {
            "Kişi Adı":     recipient_name,
            "Şirket Adı":   company,
            "Pozisyon":     position,
            "Datayı Giren": sender_info["name"],
            "Ünvan":        sender_info["title"],
        }

        # --- İmza indir ---
        sig_data = None
        if sender_info["signature"]:
            sig_data = gmail_sender._download_image(sender_info["signature"])

        # --- HTML gövde oluştur ---
        html_body, sig_bytes = gmail_sender.build_html_body(
            template, placeholders, sig_data
        )

        # --- Gönderici değişti mi? 3 dk bekle ---
        if last_sender_email is not None and last_sender_email != sender_info["email"]:
            log(f"🔄 Gönderici değişiyor → {sender_info['email']}. {wait_between//60} dk bekleniyor...")
            time.sleep(wait_between)

        last_sender_email = sender_info["email"]

        # --- Maili gönder ---
        reply_to = message_id_stored if (is_reminder and message_id_stored) else None

        success, new_message_id = gmail_sender.send_mail(
            sender_email    = sender_info["email"],
            sender_password = sender_info["password"],
            to_email        = to_email,
            subject         = email_cfg["subject"],
            html_body       = html_body,
            signature_data  = sig_bytes,
            cc              = email_cfg.get("cc", []),
            bcc             = email_cfg.get("bcc", []),
            attachments     = email_cfg.get("attachments", []),
            reply_to_message_id = reply_to
        )

        if success:
            new_count = mail_count + 1
            today_str = datetime.today().strftime("%Y-%m-%d")

            # Hatırlatmada message_id değişmez (aynı zincir korunur)
            stored_id = message_id_stored if is_reminder else new_message_id

            updated = sheets.update_recipient_row(
                service        = service,
                spreadsheet_id = spreadsheet_id,
                sheet_name     = sheet_names["recipients"],
                row_index      = idx,
                col_mapping    = recipient_cols,
                headers        = headers,
                mail_count     = new_count,
                last_date      = today_str,
                message_id     = stored_id
            )

            action = "🔔 Hatırlatma" if is_reminder else "📧 İlk mail"
            log(f"{label}: {action} gönderildi. Sheets güncellendi: {updated}")

            if is_reminder:
                result.reminded += 1
            else:
                result.sent += 1

            total_sent_this_run += 1
        else:
            log(f"{label}: ❌ Gönderilemedi.")
            result.failed += 1

    log(f"\n🏁 Gönderim tamamlandı. {result.summary()}")
    return result
