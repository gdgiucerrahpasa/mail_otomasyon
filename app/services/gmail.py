"""SMTP mail sending — ported unchanged from gmail_sender.py."""

import logging
import smtplib
import time
import urllib.request
import re
from email import utils as email_utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

logger = logging.getLogger(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def download_image(drive_link: str) -> Optional[bytes]:
    try:
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
    result = template
    for key, value in placeholders.items():
        result = result.replace(f"[{key}]", str(value) if value else "")
    return result


def build_html_body(
    template: str,
    placeholders: dict,
    signature_data: Optional[bytes],
    header_image_data: Optional[bytes] = None,
    cid: str = "signature_img",
    header_cid: str = "header_img",
) -> tuple[str, Optional[bytes]]:
    filled = _fill_template(template, placeholders)
    if signature_data:
        filled = re.sub(r'src="https://drive[^"]*"', f'src="cid:{cid}"', filled)
        filled = filled.replace("[İmza]", f'<img src="cid:{cid}" style="width:420px;height:210px;">')
        if f"cid:{cid}" not in filled:
            filled += f'<br><img src="cid:{cid}" style="width:420px;height:210px;">'
    if header_image_data:
        filled = f'<img src="cid:{header_cid}" style="max-width:600px;width:100%;"><br>' + filled
    return filled, signature_data


def send_mail(
    sender_email: str,
    sender_password: str,
    to_email: str,
    subject: str,
    html_body: str,
    signature_data: Optional[bytes] = None,
    header_image_data: Optional[bytes] = None,
    cc: list = None,
    bcc: list = None,
    attachments: list = None,
    reply_to_message_id: Optional[str] = None,
    custom_message_id: Optional[str] = None,
) -> tuple[bool, str]:
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

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alternative)

        if signature_data:
            img = MIMEImage(signature_data)
            img.add_header("Content-ID", "<signature_img>")
            img.add_header("Content-Disposition", "inline")
            msg.attach(img)

        if header_image_data:
            himg = MIMEImage(header_image_data)
            himg.add_header("Content-ID", "<header_img>")
            himg.add_header("Content-Disposition", "inline")
            msg.attach(himg)

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
                        f'attachment; filename="{os.path.basename(path)}"',
                    )
                    msg.attach(part)
                else:
                    logger.warning(f"Ek dosya bulunamadı: {path}")

        recipients = [to_email]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        logger.info(f"Mail gönderildi → {to_email} | Reply: {is_reply}")
        return True, new_message_id

    except Exception as e:
        logger.error(f"Mail gönderilemedi ({to_email}): {e}")
        return False, ""


def fetch_actual_sent_message_id(
    sender_email: str,
    sender_password: str,
    to_email: str,
    delay_secs: int = 2,
) -> str:
    """Fetch the real Message-ID Gmail assigned to the sent email via IMAP.

    Gmail SMTP replaces the custom Message-ID header with its own. Without the
    real ID, In-Reply-To headers in reminders point to a non-existent message
    and threading breaks. This reads the actual ID from [Gmail]/Sent Mail.
    """
    import imaplib
    import email as email_lib
    time.sleep(delay_secs)  # give Gmail time to add the message to Sent Mail
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(sender_email, sender_password)
            imap.select('"[Gmail]/Sent Mail"')
            _, data = imap.search(None, f'TO "{to_email}"')
            if data and data[0]:
                nums = data[0].split()
                _, msg_data = imap.fetch(nums[-1], "(BODY[HEADER.FIELDS (MESSAGE-ID)])")
                raw = msg_data[0][1]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                parsed = email_lib.message_from_string(raw)
                msg_id = parsed.get("Message-ID", "").strip()
                if msg_id:
                    logger.info(f"Gerçek Message-ID alındı ({to_email}): {msg_id}")
                    return msg_id
    except Exception as e:
        logger.warning(f"IMAP Message-ID alınamadı ({to_email}): {e}")
    return ""
