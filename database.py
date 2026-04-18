"""
SQLAlchemy database setup and User model for MemoriRay authentication.
Uses SQLite for zero-config local development.
"""

import hashlib
import os
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("MEMORIRAY_DATABASE_URL", "sqlite:///memoriray.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000,
    ).hex()


def create_user(username: str, password: str) -> User:
    salt = os.urandom(32).hex()
    pw_hash = hash_password(password, salt)
    db = SessionLocal()
    try:
        user = User(username=username, password_hash=pw_hash, salt=salt)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> User | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            return None
        if hash_password(password, user.salt) != user.password_hash:
            return None
        return user
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
