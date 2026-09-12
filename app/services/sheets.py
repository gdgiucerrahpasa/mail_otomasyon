"""Google Sheets API — ported from original sheets.py with service account support."""

import json
import logging
import os
import time
from typing import Optional

import pandas as pd
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def authenticate(credentials_file: str, token_file: str):
    """Returns authenticated Sheets service. Supports service accounts and OAuth user tokens."""
    from googleapiclient.discovery import build

    # Service account path
    if os.path.exists(credentials_file):
        with open(credentials_file) as f:
            creds_data = json.load(f)
        if creds_data.get("type") == "service_account":
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                credentials_file, scopes=SCOPES
            )
            return build("sheets", "v4", credentials=creds)

    # OAuth user token
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds and creds.valid:
        return build("sheets", "v4", credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        return build("sheets", "v4", credentials=creds)

    raise ValueError(
        "Google Sheets kimlik doğrulaması başarısız. "
        "Geçerli bir credentials.json (servis hesabı) veya token.json sağlayın."
    )


def _call(func, *args, **kwargs):
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


def read_sheet(service, spreadsheet_id: str, sheet_name: str) -> Optional[pd.DataFrame]:
    try:
        result = _call(
            service.spreadsheets().values().get,
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:Z"
        )
        values = result.get("values", [])
        if not values or len(values) < 2:
            logger.warning(f"'{sheet_name}' sayfasında veri yok.")
            return None
        headers = values[0]
        rows = []
        for row in values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            rows.append(padded[:len(headers)])
        df = pd.DataFrame(rows, columns=headers)
        logger.info(f"'{sheet_name}': {len(df)} satır okundu.")
        return df
    except Exception as e:
        logger.error(f"Sheet okuma hatası ({sheet_name}): {e}")
        return None


def get_row_colors(service, spreadsheet_id: str, sheet_name: str, num_data_rows: int) -> list[Optional[tuple]]:
    """Returns column-A background color (r,g,b floats 0-1, or None if unfilled) for each
    data row (sheet rows 2..num_data_rows+1), aligned with read_sheet()'s DataFrame index."""
    try:
        rng = f"'{sheet_name}'!A2:A{num_data_rows + 1}"
        result = _call(
            service.spreadsheets().get,
            spreadsheetId=spreadsheet_id,
            ranges=[rng],
            fields="sheets.data.rowData.values.userEnteredFormat.backgroundColor",
        )
        sheets_data = result.get("sheets", [])
        row_data = sheets_data[0]["data"][0].get("rowData", []) if sheets_data and sheets_data[0].get("data") else []
        colors = []
        for row in row_data:
            values = row.get("values", [])
            bg = values[0].get("userEnteredFormat", {}).get("backgroundColor") if values else None
            colors.append((bg.get("red", 0.0), bg.get("green", 0.0), bg.get("blue", 0.0)) if bg else None)
        colors += [None] * (num_data_rows - len(colors))
        return colors
    except Exception as e:
        logger.error(f"Satır renkleri okunamadı: {e}")
        return [None] * num_data_rows


def get_sheet_names(service, spreadsheet_id: str) -> list[str]:
    try:
        result = _call(service.spreadsheets().get, spreadsheetId=spreadsheet_id)
        return [s["properties"]["title"] for s in result.get("sheets", [])]
    except Exception as e:
        logger.error(f"Sayfa isimleri alınamadı: {e}")
        return []


def update_recipient_row(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row_index: int,
    col_mapping: dict,
    headers: list[str],
    mail_count: int,
    last_date: str,
    message_id: str,
) -> bool:
    try:
        actual_row = row_index + 2

        def col_letter(col_name: str) -> Optional[str]:
            norm = lambda s: s.strip().lower()
            for i, h in enumerate(headers):
                if norm(h) == norm(col_name):
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
    result = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
