"""
config.py — Yapılandırma yükleme ve kaydetme
"""

import json
import os

import os.
import logging
import dotenv


logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "google_sheets": {
        "spreadsheet_id": os.getenv("GOOGLE_SHEET_ID"),
        "credentials_file": "credentials.json",
        "token_file": "token.json"
    },
    "sheet_names": {
        "senders": "Kişi Bilgileri",
        "recipients": "Alıcı Listesi"
    },
    "sender_columns": {
        "name":      "İsim",
        "title":     "Ünvan",
        "email":     "Gmail",
        "password":  "App Password",
        "signature": "İmza Linki"
    },
    "recipient_columns": {
        "name":         "Kişi Adı",
        "company":      "Şirket",
        "position":     "Pozisyon",
        "email":        "E-posta",
        "last_date":    "Son Mail Tarihi",
        "mail_count":   "Mail Sayısı",
        "message_id":   "Message-ID",
        "entered_by":   "Datayı Giren",
        "response":     "Dönüş Durumu",
        "template_no":  "Şablon No"
    },
    "email": {
        "subject": "Konu Başlığı",
        "cc": [],
        "bcc": [],
        "attachments": [],
        "templates": {
            "template_1": "<p>Merhaba [Kişi Adı],</p>\n\n<p>[Şirket Adı] için yazıyorum...</p>\n\n<p>Saygılarımla,</p>",
            "template_2": "<p>Merhaba [Kişi Adı],</p>\n\n<p>[Şirket Adı] hakkında...</p>\n\n<p>Saygılarımla,</p>",
            "template_3": "<p>Merhaba [Kişi Adı],</p>\n\n<p>[Şirket Adı] ile iş birliği...</p>\n\n<p>Saygılarımla,</p>",
            "template_4": "<p>Merhaba [Kişi Adı],</p>\n\n<p>[Şirket Adı] için bir fırsat...</p>\n\n<p>Saygılarımla,</p>",
            "reminder":   "<p>Merhaba [Kişi Adı],</p>\n\n<p>Daha önce [Şirket Adı]'na gönderdiğim maili hatırlatmak istedim.</p>\n\n<p>Saygılarımla,</p>"
        }
    },
    "settings": {
        "wait_seconds_between_senders": 180,
        "reminder_after_days": 3,
        "max_mails_per_run": 50
    }
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Eksik anahtarları varsayılanlarla doldur (derin birleştirme)
            return deep_merge(DEFAULT_CONFIG, loaded)
        except Exception as e:
            logger.error(f"Config okuma hatası: {e}")
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Config kaydedildi.")
    except Exception as e:
        logger.error(f"Config kaydetme hatası: {e}")


def deep_merge(base: dict, override: dict) -> dict:
    """Override'daki değerleri base üzerine derin birleştirir."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
