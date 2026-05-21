"""
Database models for the Habit Loop & Behavior Tracker.

Adds habits with configurable cadence (daily/weekly/N-times-per-week),
per-day check-ins, habit stacks (chained habits), routines with ordered
steps, and a generic behavior-event log (sleep, exercise, meals,
hydration, screen time, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean, Text,
)

from database import Base, SessionLocal


# ---------------------------------------------------------------------------
# Habits
# ---------------------------------------------------------------------------

class Habit(Base):
    """A repeatable habit a user wants to build."""
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    category = Column(String(80), nullable=False, default="general")
    icon = Column(String(20), nullable=True)
    color = Column(String(20), nullable=True)

    # Cadence: "daily", "weekdays", "weekends", "weekly_n" with frequency_per_week,
    # or "every_n_days" with interval_days.
    cadence = Column(String(40), nullable=False, default="daily")
    frequency_per_week = Column(Integer, nullable=True)
    interval_days = Column(Integer, nullable=True)

    target_streak = Column(Integer, nullable=True)
    target_minutes = Column(Integer, nullable=True)
    target_count = Column(Integer, nullable=True)
    unit = Column(String(40), nullable=True)

    reminder_time = Column(String(10), nullable=True)  # "HH:MM"
    reminder_enabled = Column(Boolean, default=False)

    cue = Column(String(500), nullable=True)        # the cue / context
    reward = Column(String(500), nullable=True)     # the reward / payoff
    motivation = Column(Text, nullable=True)

    is_archived = Column(Boolean, default=False, index=True)
    is_keystone = Column(Boolean, default=False)
    difficulty = Column(String(40), default="easy")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HabitCheckIn(Base):
    """A single completion (or skip) of a habit on a given date."""
    __tablename__ = "habit_check_ins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    habit_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    occurred_on = Column(DateTime, nullable=False, index=True)  # day-resolution
    status = Column(String(20), nullable=False, default="done")  # done/partial/skipped
    quantity = Column(Float, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    quality = Column(Float, nullable=True)  # 1-5
    notes = Column(String(1000), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HabitStreak(Base):
    """Materialized streak metrics per habit, updated incrementally."""
    __tablename__ = "habit_streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    habit_id = Column(Integer, nullable=False, unique=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    total_check_ins = Column(Integer, default=0)
    total_skips = Column(Integer, default=0)
    last_check_in = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HabitStack(Base):
    """A habit stack — anchor habit triggers a chain of follow-on habits."""
    __tablename__ = "habit_stacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    anchor_habit_id = Column(Integer, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HabitStackStep(Base):
    """A step in a habit stack (an additional habit linked to the anchor)."""
    __tablename__ = "habit_stack_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stack_id = Column(Integer, nullable=False, index=True)
    habit_id = Column(Integer, nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

class Routine(Base):
    """A named routine the user runs (morning / evening / pre-meeting, etc.)."""
    __tablename__ = "routines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    when_to_run = Column(String(200), nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RoutineStep(Base):
    """An ordered step inside a routine."""
    __tablename__ = "routine_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    routine_id = Column(Integer, nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    text = Column(String(1000), nullable=False)
    expected_minutes = Column(Integer, nullable=True)
    habit_id = Column(Integer, nullable=True)  # optionally link to a habit


class RoutineRun(Base):
    """A logged execution of a routine."""
    __tablename__ = "routine_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    routine_id = Column(Integer, nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    completed_steps = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    notes = Column(String(1000), nullable=True)


# ---------------------------------------------------------------------------
# Behavior events
# ---------------------------------------------------------------------------

class BehaviorEvent(Base):
    """Generic logged event: sleep, meal, exercise, hydration, screen time, etc.

    `event_type` is the discriminator; payload fields (value, value_unit,
    quality, etc.) carry the type-specific data.
    """
    __tablename__ = "behavior_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    event_type = Column(String(40), nullable=False, index=True)
    occurred_at = Column(DateTime, nullable=False, index=True)

    value = Column(Float, nullable=True)
    value_unit = Column(String(40), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    quality = Column(Float, nullable=True)
    intensity = Column(Float, nullable=True)

    notes = Column(String(1000), nullable=True)
    tags = Column(String(500), nullable=True)  # comma-separated

    # Sleep-specific
    bedtime = Column(DateTime, nullable=True)
    wake_time = Column(DateTime, nullable=True)
    awakenings = Column(Integer, nullable=True)
    dream_summary = Column(String(2000), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HabitCoachNote(Base):
    """A piece of coaching content delivered to the user (AI or rule)."""
    __tablename__ = "habit_coach_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    note_type = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    related_habit_id = Column(Integer, nullable=True, index=True)
    confidence = Column(Float, nullable=True)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Catalog defaults
# ---------------------------------------------------------------------------

HABIT_CATEGORIES: List[str] = [
    "movement",
    "mind",
    "sleep",
    "nutrition",
    "hydration",
    "social",
    "creative",
    "work",
    "learning",
    "finance",
    "home",
    "digital",
    "spiritual",
    "general",
]


BEHAVIOR_EVENT_TYPES: Dict[str, Dict[str, object]] = {
    "sleep":      {"unit": "hours",     "good_min": 7.0,  "good_max": 9.0},
    "exercise":   {"unit": "minutes",   "good_min": 20.0, "good_max": 90.0},
    "hydration":  {"unit": "glasses",   "good_min": 6.0,  "good_max": 12.0},
    "meal":       {"unit": "count",     "good_min": 2.0,  "good_max": 5.0},
    "screen":     {"unit": "minutes",   "good_min": 0.0,  "good_max": 120.0},
    "caffeine":   {"unit": "mg",        "good_min": 0.0,  "good_max": 400.0},
    "alcohol":    {"unit": "drinks",    "good_min": 0.0,  "good_max": 1.0},
    "outdoor":    {"unit": "minutes",   "good_min": 15.0, "good_max": 240.0},
    "social":     {"unit": "minutes",   "good_min": 15.0, "good_max": 240.0},
    "reading":    {"unit": "minutes",   "good_min": 10.0, "good_max": 120.0},
    "creative":   {"unit": "minutes",   "good_min": 15.0, "good_max": 180.0},
    "stretching": {"unit": "minutes",   "good_min": 5.0,  "good_max": 60.0},
    "steps":      {"unit": "count",     "good_min": 5000, "good_max": 15000},
    "mood":       {"unit": "score",     "good_min": 5.0,  "good_max": 10.0},
}


DEFAULT_HABIT_TEMPLATES: List[Dict[str, object]] = [
    {
        "name": "10-minute morning walk",
        "category": "movement",
        "cadence": "daily",
        "target_minutes": 10,
        "difficulty": "easy",
        "cue": "Right after brushing teeth",
        "reward": "Notice your mood in the first hour",
    },
    {
        "name": "Drink water on waking",
        "category": "hydration",
        "cadence": "daily",
        "target_count": 1,
        "unit": "glasses",
        "difficulty": "easy",
        "cue": "Glass next to your bed",
    },
    {
        "name": "Two-minute tidy",
        "category": "home",
        "cadence": "daily",
        "target_minutes": 2,
        "difficulty": "easy",
    },
    {
        "name": "Phone-free first hour",
        "category": "digital",
        "cadence": "daily",
        "difficulty": "medium",
        "cue": "Phone stays in another room overnight",
    },
    {
        "name": "5-4-3-2-1 grounding",
        "category": "mind",
        "cadence": "daily",
        "target_minutes": 5,
        "difficulty": "easy",
    },
    {
        "name": "Connect with one person",
        "category": "social",
        "cadence": "weekly_n",
        "frequency_per_week": 3,
        "difficulty": "medium",
    },
    {
        "name": "Read 10 minutes",
        "category": "learning",
        "cadence": "daily",
        "target_minutes": 10,
        "difficulty": "easy",
    },
    {
        "name": "Strength training",
        "category": "movement",
        "cadence": "weekly_n",
        "frequency_per_week": 3,
        "target_minutes": 30,
        "difficulty": "medium",
    },
    {
        "name": "Lights off by 22:30",
        "category": "sleep",
        "cadence": "daily",
        "difficulty": "medium",
        "cue": "Phone alarm at 22:15",
    },
    {
        "name": "Three slow breaths before meals",
        "category": "mind",
        "cadence": "daily",
        "difficulty": "easy",
    },
    {
        "name": "10-minute creative play",
        "category": "creative",
        "cadence": "weekly_n",
        "frequency_per_week": 4,
        "target_minutes": 10,
        "difficulty": "easy",
    },
    {
        "name": "Outdoor sunlight",
        "category": "movement",
        "cadence": "daily",
        "target_minutes": 15,
        "difficulty": "easy",
    },
]


DEFAULT_ROUTINE_TEMPLATES: List[Dict[str, object]] = [
    {
        "name": "Morning anchor",
        "when_to_run": "within 30 minutes of waking",
        "estimated_minutes": 20,
        "steps": [
            "Drink a glass of water",
            "5 minutes of light movement",
            "Open the curtains, get sunlight",
            "Write one intention for the day",
            "3 slow breaths before opening your phone",
        ],
    },
    {
        "name": "Evening wind-down",
        "when_to_run": "60-90 minutes before bed",
        "estimated_minutes": 30,
        "steps": [
            "Dim the lights",
            "Phone away in another room",
            "5 minutes of stretching",
            "Write 3 gratitudes",
            "Read for 10 minutes",
            "Plan tomorrow's first task",
        ],
    },
    {
        "name": "Hard-day reset",
        "when_to_run": "when overwhelmed",
        "estimated_minutes": 12,
        "steps": [
            "Step outside for 3 minutes",
            "4-7-8 breathing x 4 cycles",
            "Name one thing in your control",
            "Drink water",
            "Send one supportive message to someone you trust",
        ],
    },
    {
        "name": "Pre-meeting reset",
        "when_to_run": "5 minutes before a meeting",
        "estimated_minutes": 5,
        "steps": [
            "Close other tabs",
            "Sit upright, feet planted",
            "3 box breaths",
            "Note the one outcome you want from this meeting",
        ],
    },
    {
        "name": "Sunday review",
        "when_to_run": "Sunday afternoon",
        "estimated_minutes": 25,
        "steps": [
            "Open journal — what did you learn this week?",
            "List 3 wins, however small",
            "Identify one drain to reduce next week",
            "Schedule one rest block",
            "Pick one habit to focus on",
        ],
    },
]


def seed_default_habits(user_id: int) -> int:
    """Seed default habits for a user. Returns inserted count."""
    db = SessionLocal()
    inserted = 0
    try:
        existing_names = {
            h.name
            for h in db.query(Habit).filter(Habit.user_id == user_id).all()
        }
        for tpl in DEFAULT_HABIT_TEMPLATES:
            if tpl["name"] in existing_names:
                continue
            db.add(Habit(user_id=user_id, **tpl))
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def seed_default_routines(user_id: int) -> int:
    """Seed default routines + their steps for a user."""
    db = SessionLocal()
    inserted = 0
    try:
        existing_names = {
            r.name
            for r in db.query(Routine).filter(Routine.user_id == user_id).all()
        }
        for tpl in DEFAULT_ROUTINE_TEMPLATES:
            if tpl["name"] in existing_names:
                continue
            routine = Routine(
                user_id=user_id,
                name=tpl["name"],
                when_to_run=tpl["when_to_run"],
                estimated_minutes=tpl["estimated_minutes"],
            )
            db.add(routine)
            db.flush()
            for idx, step_text in enumerate(tpl["steps"]):
                db.add(
                    RoutineStep(
                        routine_id=routine.id,
                        order_index=idx,
                        text=step_text,
                    )
                )
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def init_habit_models() -> Dict[str, object]:
    """Create habit tables. Safe to call repeatedly."""
    from database import engine
    Base.metadata.create_all(bind=engine)
    return {"ok": True, "tables": [
        "habits", "habit_check_ins", "habit_streaks",
        "habit_stacks", "habit_stack_steps",
        "routines", "routine_steps", "routine_runs",
        "behavior_events", "habit_coach_notes",
    ]}
