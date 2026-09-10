import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mail_web.db")
# Railway (and some other providers) hand out "postgres://", which SQLAlchemy 2.x rejects.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _seed_defaults()


def _seed_defaults():
    from app.models import Setting
    db = SessionLocal()
    defaults = {
        "spreadsheet_id": os.getenv("GOOGLE_SHEET_ID", ""),
        "credentials_file": "credentials.json",
        "token_file": "token.json",
        "sheet_senders": "Kişi Bilgileri",
        "sheet_recipients": "Alıcı Listesi",
        "col_recipient_name": "Kişi Adı",
        "col_recipient_company": "Şirket",
        "col_recipient_position": "Pozisyon",
        "col_recipient_email": "E-posta",
        "col_recipient_last_date": "Son Mail Tarihi",
        "col_recipient_mail_count": "Mail Sayısı",
        "col_recipient_message_id": "Message-ID",
        "col_recipient_entered_by": "Datayı Giren",
        "col_recipient_response": "Dönüş Durumu",
        "col_recipient_segment": "Segment",
        "col_sender_name": "İsim",
        "col_sender_title": "Ünvan",
        "col_sender_email": "Gmail",
        "col_sender_password": "App Password",
        "col_sender_signature": "İmza Linki",
        "email_cc": "",
        "email_bcc": "",
        "header_image": "",
        "min_wait_seconds": "12",
        "max_wait_seconds": "24",
        "reminder_after_days": "3",
        "max_mails_per_run": "50",
        "max_mails_per_sender_per_day": "450",
        "schedule_interval_hours": "6",
        "schedule_enabled": "false",
    }
    for k, v in defaults.items():
        if not db.query(Setting).filter_by(key=k).first():
            db.add(Setting(key=k, value=v))
    db.commit()
    db.close()
