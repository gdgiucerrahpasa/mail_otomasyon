from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    is_reminder = Column(Boolean, default=False, nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False, default="")
    cc = Column(String(500), default="")
    bcc = Column(String(500), default="")
    attachments = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")
    sent = Column(Integer, default=0)
    reminded = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    responded = Column(Integer, default=0)
    log_entries = relationship("LogEntry", back_populates="run", cascade="all, delete-orphan")


class LogEntry(Base):
    __tablename__ = "log_entries"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(10), default="INFO")
    message = Column(Text)
    run = relationship("Run", back_populates="log_entries")
