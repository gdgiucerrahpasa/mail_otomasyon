"""
gmail_sender.py — SMTP ile mail gönderimi
  - CID ile imza resmi embed
  - In-Reply-To / References header ile gerçek reply
  - Ek dosya desteği
"""

import logging
import smtplib
import urllib.request
import re
from email import utils as email_utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def _download_image(drive_link: str) -> Optional[bytes]:
    """
    Drive doğrudan indirme linkinden resim byte'larını indirir.
    Link formatı: https://drive.usercontent.google.com/download?id=FILE_ID
    ya da sadece FILE_ID olabilir.
    """
    try:
        # Eğer sadece ID geldiyse linke çevir
        if not drive_link.startswith("http"):
            url = f"https://drive.usercontent.google.com/download?id={drive_link.strip()}&export=download"
        else:
            url = drive_link.strip()

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        logger.info(f"İmza resmi indirildi ({len(data)} byte).")
        return data
    except Exception as e:
        logger.error(f"İmza resmi indirilemedi: {e}")
        return None


def _fill_template(template: str, placeholders: dict) -> str:
    """
    [Anahtar] formatındaki yer tutucuları doldurur.
    placeholders: {"Kişi Adı": "Ahmet", "Şirket Adı": "XYZ A.Ş.", ...}
    """
    result = template
    for key, value in placeholders.items():
        result = result.replace(f"[{key}]", str(value) if value else "")
    return result


def build_html_body(
    template: str,
    placeholders: dict,
    signature_data: Optional[bytes],
    cid: str = "signature_img"
) -> tuple[str, Optional[bytes]]:
    """
    HTML body'yi oluşturur.
    Eğer imza resmi varsa:
      - Şablondaki [İmza] ya da <img src="..."> tag'ini CID referansıyla değiştirir
      - (signature_data, cid) çiftini embed için döner
    Döner: (html_string, signature_bytes_or_None)
    """
    filled = _fill_template(template, placeholders)

    if signature_data:
        # Eğer template'de src="...drive..." gibi bir link varsa CID ile değiştir
        filled = re.sub(
            r'src="https://drive[^"]*"',
            f'src="cid:{cid}"',
            filled
        )
        # Eğer [İmza] kaldıysa (kullanıcı farklı yazdıysa)
        filled = filled.replace("[İmza]", f'<img src="cid:{cid}" style="width:420px;height:210px;">')

    return filled, signature_data


def send_mail(
    sender_email: str,
    sender_password: str,
    to_email: str,
    subject: str,
    html_body: str,
    signature_data: Optional[bytes] = None,
    cc: list = None,
    bcc: list = None,
    attachments: list = None,
    reply_to_message_id: Optional[str] = None,  # In-Reply-To header
    custom_message_id: Optional[str] = None
) -> tuple[bool, str]:
    """
    Maili gönderir.
    Döner: (başarı_bool, message_id_str)
    """
    try:
        msg = MIMEMultipart("related")
        msg["From"] = sender_email
        msg["To"] = to_email

        new_message_id = custom_message_id or email_utils.make_msgid(domain="gmail.com")
        msg["Message-ID"] = new_message_id

        is_reply = bool(reply_to_message_id)
        if is_reply:
            display_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id
        else:
            display_subject = subject

        msg["Subject"] = display_subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        # HTML alternatif
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alternative)

        # CID imza embed
        if signature_data:
            img = MIMEImage(signature_data)
            img.add_header("Content-ID", "<signature_img>")
            img.add_header("Content-Disposition", "inline", filename="signature.png")
            msg.attach(img)

        # Ek dosyalar (sadece ilk mailde)
        if attachments and not is_reply:
            import os
            for path in attachments:
                if path and os.path.exists(path):
                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename=\"{os.path.basename(path)}\""
                    )
                    msg.attach(part)
                else:
                    logger.warning(f"Ek dosya bulunamadı: {path}")

        # Alıcı listesi
        recipients = [to_email]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        logger.info(f"Mail gönderildi → {to_email} | Reply: {is_reply} | ID: {new_message_id}")
        return True, new_message_id

    except Exception as e:
        logger.error(f"Mail gönderilemedi ({to_email}): {e}")
        return False, ""
