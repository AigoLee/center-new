"""
SQLite 数据库模型
"""
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, Integer, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DB_PATH

Base = declarative_base()
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


class Question(Base):
    __tablename__ = "questions"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), index=True)
    original = Column(Text)
    refined = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)
    intent = Column(String(128), nullable=True)
    urgency = Column(String(16), default="普通")
    department = Column(String(64), nullable=True)
    keywords = Column(JSON, default=list)
    status = Column(String(32), default="收集中")  # 收集中/已回答/已解决/未解决/待审核/已入库/已驳回
    followup_round = Column(Integer, default=0)
    followup_history = Column(JSON, default=list)
    answer = Column(Text, nullable=True)
    answer_source = Column(String(32), nullable=True)
    references = Column(JSON, default=list)
    resolved = Column(Boolean, nullable=True)
    satisfaction = Column(Integer, nullable=True)
    review_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class Review(Base):
    __tablename__ = "reviews"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id = Column(String(64), index=True)
    original_question = Column(Text)
    answer = Column(Text)
    summary = Column(Text)
    edited_summary = Column(Text, nullable=True)
    source = Column(String(32))
    satisfaction = Column(Integer, nullable=True)
    status = Column(String(16), default="pending")
    admin_notes = Column(Text, nullable=True)
    kb_entry_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = Session()
    try:
        return db
    except Exception:
        db.close()
        raise
