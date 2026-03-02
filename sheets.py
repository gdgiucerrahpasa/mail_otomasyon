"""
sheets.py — Google Sheets API işlemleri
"""

import logging
import time
from typing import Optional
import pandas as pd
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# --- Yetki ---

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def authenticate(credentials_file: str, token_file: str):
    """OAuth2 ile Sheets servisi döner."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import os

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    service = build("sheets", "v4", credentials=creds)
    logger.info("Google Sheets kimlik doğrulaması başarılı.")
    return service


# --- Exponential Backoff ---

def _call(func, *args, **kwargs):
    """API çağrısını exponential backoff ile gerçekleştirir."""
    max_retries = 5
    delay = 1
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs).execute()
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503, 504):
                wait = delay * (2 ** attempt)
                logger.warning(f"API hatası {e.resp.status}. {wait}s bekleniyor... ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Maksimum deneme sayısı aşıldı.")


# --- Okuma ---

def read_sheet(service, spreadsheet_id: str, sheet_name: str) -> Optional[pd.DataFrame]:
    """Belirtilen sayfayı DataFrame olarak döner."""
    try:
        result = _call(
            service.spreadsheets().values().get,
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:Z"
        )
        values = result.get("values", [])
        if not values or len(values) < 2:
            logger.warning(f"'{sheet_name}' sayfasında veri yok veya sadece başlık var.")
            return None

        headers = values[0]
        rows = []
        for row in values[1:]:
            # Kısa satırları başlık uzunluğuna tamamla
            padded = row + [""] * (len(headers) - len(row))
            rows.append(padded[:len(headers)])

        df = pd.DataFrame(rows, columns=headers)
        logger.info(f"'{sheet_name}' sayfasından {len(df)} satır okundu.")
        return df
    except Exception as e:
        logger.error(f"Sheet okuma hatası ({sheet_name}): {e}")
        return None


def get_sheet_names(service, spreadsheet_id: str) -> list[str]:
    """Spreadsheet'teki tüm sayfa isimlerini döner."""
    try:
        result = _call(
            service.spreadsheets().get,
            spreadsheetId=spreadsheet_id
        )
        return [s["properties"]["title"] for s in result.get("sheets", [])]
    except Exception as e:
        logger.error(f"Sayfa isimleri alınamadı: {e}")
        return []


# --- Yazma ---

def update_recipient_row(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row_index: int,          # 0-tabanlı veri satırı (başlık hariç)
    col_mapping: dict,       # recipient_columns config'den
    headers: list[str],
    mail_count: int,
    last_date: str,
    message_id: str
) -> bool:
    """
    Alıcı tablosunun ilgili satırında:
      - Mail Sayısı
      - Son Mail Tarihi
      - Message-ID
    sütunlarını günceller.
    """
    try:
        actual_row = row_index + 2  # +1 başlık, +1 1-tabanlı indeks

        def col_letter(col_name: str) -> Optional[str]:
            norm = lambda s: s.strip().lower()
            col_name_n = norm(col_name)
            for i, h in enumerate(headers):
                if norm(h) == col_name_n:
                    # Excel tarzı harf hesaplama (A-Z sonra AA, AB...)
                    return _index_to_col_letter(i)
            logger.error(f"'{col_name}' sütunu bulunamadı.")
            return None

        count_col = col_letter(col_mapping["mail_count"])
        date_col  = col_letter(col_mapping["last_date"])
        msgid_col = col_letter(col_mapping["message_id"])

        if not all([count_col, date_col, msgid_col]):
            return False

        data = [
            {"range": f"'{sheet_name}'!{count_col}{actual_row}", "values": [[str(mail_count)]]},
            {"range": f"'{sheet_name}'!{date_col}{actual_row}",  "values": [[last_date]]},
            {"range": f"'{sheet_name}'!{msgid_col}{actual_row}", "values": [[message_id]]},
        ]

        _call(
            service.spreadsheets().values().batchUpdate,
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data}
        )
        logger.info(f"Satır {actual_row} güncellendi (mail_count={mail_count}).")
        return True

    except Exception as e:
        logger.error(f"Satır güncelleme hatası: {e}")
        return False


def _index_to_col_letter(index: int) -> str:
    """0-tabanlı sütun indeksini Excel harf notasyonuna çevirir (0→A, 25→Z, 26→AA...)."""
    result = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
