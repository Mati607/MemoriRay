"""
SQLAlchemy database setup and User model for MemoriRay authentication.
Uses SQLite for zero-config local development.
"""

import hashlib
import os
from datetime import datetime, timezone
from typing import List as TypingList

from sqlalchemy import Column, Integer, String, DateTime, Float, create_engine
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


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment_text = Column(String(1000), nullable=True)
    mood_score = Column(Float, nullable=True)
    message_snippet = Column(String(300), nullable=True)
    emotion_category = Column(String(50), nullable=True)
    intensity = Column(Float, nullable=True)
    triggers = Column(String(1000), nullable=True)


class TherapyExercise(Base):
    __tablename__ = "therapy_exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    exercise_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    category = Column(String(100), nullable=False)
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    duration_minutes = Column(Integer, nullable=True)
    effectiveness_rating = Column(Float, nullable=True)
    notes = Column(String(1000), nullable=True)


class ExerciseTemplate(Base):
    __tablename__ = "exercise_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exercise_type = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    instructions = Column(String(5000), nullable=False)
    category = Column(String(100), nullable=False)
    estimated_duration = Column(Integer, nullable=False)
    difficulty_level = Column(String(50), nullable=False)


class MoodInsight(Base):
    __tablename__ = "mood_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    insight_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    confidence_score = Column(Float, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    data_points = Column(String(2000), nullable=True)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    avg_mood_score = Column(Float, nullable=True)
    best_day = Column(String(100), nullable=True)
    worst_day = Column(String(100), nullable=True)
    mood_volatility = Column(Float, nullable=True)
    dominant_emotions = Column(String(500), nullable=True)
    exercises_completed = Column(Integer, default=0)
    key_improvements = Column(String(2000), nullable=True)
    recommendations = Column(String(2000), nullable=True)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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


def save_mood_entry(user_id: int, sentiment_text: str, mood_score: float, message_snippet: str) -> None:
    db = SessionLocal()
    try:
        entry = MoodEntry(
            user_id=user_id,
            sentiment_text=sentiment_text,
            mood_score=mood_score,
            message_snippet=(message_snippet or "")[:300],
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()


def get_mood_history(user_id: int, limit: int = 90) -> TypingList[dict]:
    db = SessionLocal()
    try:
        entries = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user_id)
            .order_by(MoodEntry.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "mood_score": e.mood_score,
                "sentiment_text": e.sentiment_text,
                "message_snippet": e.message_snippet,
            }
            for e in entries
        ]
    finally:
        db.close()


def create_exercise_template(exercise_type: str, name: str, description: str, instructions: str,
                            category: str, estimated_duration: int, difficulty_level: str) -> None:
    db = SessionLocal()
    try:
        template = ExerciseTemplate(
            exercise_type=exercise_type,
            name=name,
            description=description,
            instructions=instructions,
            category=category,
            estimated_duration=estimated_duration,
            difficulty_level=difficulty_level,
        )
        db.add(template)
        db.commit()
    finally:
        db.close()


def get_exercise_templates(category: str = None) -> TypingList[dict]:
    db = SessionLocal()
    try:
        query = db.query(ExerciseTemplate)
        if category:
            query = query.filter(ExerciseTemplate.category == category)
        templates = query.all()
        return [
            {
                "id": t.id,
                "exercise_type": t.exercise_type,
                "name": t.name,
                "description": t.description,
                "instructions": t.instructions,
                "category": t.category,
                "estimated_duration": t.estimated_duration,
                "difficulty_level": t.difficulty_level,
            }
            for t in templates
        ]
    finally:
        db.close()


def add_therapy_exercise(user_id: int, exercise_type: str, name: str, description: str,
                        category: str, duration_minutes: int = None, effectiveness_rating: float = None,
                        notes: str = None) -> None:
    db = SessionLocal()
    try:
        exercise = TherapyExercise(
            user_id=user_id,
            exercise_type=exercise_type,
            name=name,
            description=description,
            category=category,
            duration_minutes=duration_minutes,
            effectiveness_rating=effectiveness_rating,
            notes=notes,
        )
        db.add(exercise)
        db.commit()
    finally:
        db.close()


def get_user_exercises(user_id: int, limit: int = 50) -> TypingList[dict]:
    db = SessionLocal()
    try:
        exercises = (
            db.query(TherapyExercise)
            .filter(TherapyExercise.user_id == user_id)
            .order_by(TherapyExercise.completed_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "exercise_type": e.exercise_type,
                "name": e.name,
                "description": e.description,
                "category": e.category,
                "completed_at": e.completed_at.isoformat(),
                "duration_minutes": e.duration_minutes,
                "effectiveness_rating": e.effectiveness_rating,
                "notes": e.notes,
            }
            for e in exercises
        ]
    finally:
        db.close()


def add_mood_insight(user_id: int, insight_type: str, title: str, description: str,
                    confidence_score: float, data_points: str = None) -> None:
    db = SessionLocal()
    try:
        insight = MoodInsight(
            user_id=user_id,
            insight_type=insight_type,
            title=title,
            description=description,
            confidence_score=confidence_score,
            data_points=data_points,
        )
        db.add(insight)
        db.commit()
    finally:
        db.close()


def get_user_insights(user_id: int, limit: int = 20) -> TypingList[dict]:
    db = SessionLocal()
    try:
        insights = (
            db.query(MoodInsight)
            .filter(MoodInsight.user_id == user_id)
            .order_by(MoodInsight.generated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": i.id,
                "insight_type": i.insight_type,
                "title": i.title,
                "description": i.description,
                "confidence_score": i.confidence_score,
                "generated_at": i.generated_at.isoformat(),
            }
            for i in insights
        ]
    finally:
        db.close()


def save_weekly_report(user_id: int, week_start: datetime, week_end: datetime, avg_mood_score: float,
                      best_day: str, worst_day: str, mood_volatility: float, dominant_emotions: str,
                      exercises_completed: int, key_improvements: str, recommendations: str) -> None:
    db = SessionLocal()
    try:
        report = WeeklyReport(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            avg_mood_score=avg_mood_score,
            best_day=best_day,
            worst_day=worst_day,
            mood_volatility=mood_volatility,
            dominant_emotions=dominant_emotions,
            exercises_completed=exercises_completed,
            key_improvements=key_improvements,
            recommendations=recommendations,
        )
        db.add(report)
        db.commit()
    finally:
        db.close()


def get_latest_weekly_report(user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        report = (
            db.query(WeeklyReport)
            .filter(WeeklyReport.user_id == user_id)
            .order_by(WeeklyReport.generated_at.desc())
            .first()
        )
        if not report:
            return None
        return {
            "id": report.id,
            "week_start": report.week_start.isoformat(),
            "week_end": report.week_end.isoformat(),
            "avg_mood_score": report.avg_mood_score,
            "best_day": report.best_day,
            "worst_day": report.worst_day,
            "mood_volatility": report.mood_volatility,
            "dominant_emotions": report.dominant_emotions,
            "exercises_completed": report.exercises_completed,
            "key_improvements": report.key_improvements,
            "recommendations": report.recommendations,
            "generated_at": report.generated_at.isoformat(),
        }
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
