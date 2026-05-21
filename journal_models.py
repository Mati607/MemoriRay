"""
Database models for the Mindful Journal & Reflection System.

Adds journal entries, gratitude logs, mindfulness sessions, journal prompts,
reflection snapshots, and entry tags. Models are SQLAlchemy declarative on
the shared `Base` from database.py so they participate in the same metadata
and are created by init_db().
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey,
)

from database import Base, SessionLocal


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class JournalEntry(Base):
    """A single free-form journal entry written by a user."""
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    title = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)

    mood_score = Column(Float, nullable=True)
    energy_level = Column(Float, nullable=True)
    stress_level = Column(Float, nullable=True)

    prompt_id = Column(Integer, nullable=True, index=True)
    entry_type = Column(String(50), default="free_form")
    visibility = Column(String(20), default="private")

    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)

    location = Column(String(255), nullable=True)
    weather = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class JournalTag(Base):
    """User-defined tags that can be attached to journal entries."""
    __tablename__ = "journal_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(80), nullable=False, index=True)
    color = Column(String(20), nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class JournalEntryTag(Base):
    """Many-to-many link table between journal entries and tags."""
    __tablename__ = "journal_entry_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class JournalPrompt(Base):
    """A prompt or guiding question to help users start writing."""
    __tablename__ = "journal_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(500), nullable=False)
    category = Column(String(80), nullable=False, index=True)
    difficulty = Column(String(40), nullable=False, default="easy")
    target_mood = Column(String(80), nullable=True)
    is_active = Column(Boolean, default=True)
    estimated_minutes = Column(Integer, default=5)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class JournalAttachment(Base):
    """Lightweight attachments (image references, links) for an entry."""
    __tablename__ = "journal_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    kind = Column(String(40), nullable=False)
    reference = Column(String(1000), nullable=False)
    caption = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Gratitude
# ---------------------------------------------------------------------------

class GratitudeEntry(Base):
    """A single gratitude item ('today I'm thankful for X')."""
    __tablename__ = "gratitude_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    content = Column(String(1000), nullable=False)
    category = Column(String(80), nullable=True, index=True)
    intensity = Column(Float, default=3.0)

    related_person = Column(String(255), nullable=True)
    related_event = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class GratitudeStreak(Base):
    """Tracks a user's longest and current gratitude practice streak."""
    __tablename__ = "gratitude_streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_entry_date = Column(DateTime, nullable=True)
    total_entries = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Mindfulness
# ---------------------------------------------------------------------------

class MindfulnessSession(Base):
    """A completed mindfulness/meditation session."""
    __tablename__ = "mindfulness_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    technique = Column(String(100), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, default=True)

    pre_mood = Column(Float, nullable=True)
    post_mood = Column(Float, nullable=True)
    perceived_calm = Column(Float, nullable=True)

    notes = Column(String(2000), nullable=True)
    interrupted = Column(Boolean, default=False)
    background_sound = Column(String(100), nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ended_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MindfulnessTechnique(Base):
    """A library of mindfulness techniques the app can guide users through."""
    __tablename__ = "mindfulness_techniques"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    guided_script = Column(Text, nullable=True)
    typical_duration = Column(Integer, default=10)
    category = Column(String(80), nullable=False)
    difficulty = Column(String(40), default="beginner")
    benefits = Column(String(1000), nullable=True)


# ---------------------------------------------------------------------------
# Reflections
# ---------------------------------------------------------------------------

class ReflectionSnapshot(Base):
    """An AI- or rule-generated reflection summarizing a window of entries."""
    __tablename__ = "reflection_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    window_kind = Column(String(40), nullable=False)  # daily/weekly/monthly

    summary = Column(Text, nullable=False)
    dominant_themes = Column(String(1000), nullable=True)
    mood_trend = Column(String(40), nullable=True)
    growth_signals = Column(Text, nullable=True)
    suggested_focus = Column(Text, nullable=True)

    entries_analyzed = Column(Integer, default=0)
    gratitudes_analyzed = Column(Integer, default=0)
    sessions_analyzed = Column(Integer, default=0)

    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReflectionFeedback(Base):
    """User feedback on a reflection: was it accurate, helpful?"""
    __tablename__ = "reflection_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    accuracy_rating = Column(Float, nullable=True)
    helpfulness_rating = Column(Float, nullable=True)
    comment = Column(String(2000), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Catalog defaults
# ---------------------------------------------------------------------------

DEFAULT_PROMPTS: List[Dict[str, object]] = [
    {
        "text": "What is one thing you're proud of from today, no matter how small?",
        "category": "reflection",
        "difficulty": "easy",
        "target_mood": "low",
        "estimated_minutes": 5,
    },
    {
        "text": "Describe a moment today when you felt fully present. What were you doing?",
        "category": "mindfulness",
        "difficulty": "easy",
        "target_mood": "neutral",
        "estimated_minutes": 7,
    },
    {
        "text": "If your current feelings were a weather pattern, what would they look like?",
        "category": "emotion",
        "difficulty": "easy",
        "target_mood": "any",
        "estimated_minutes": 5,
    },
    {
        "text": "Write a letter to yourself from one year ago. What would you tell them?",
        "category": "self_compassion",
        "difficulty": "medium",
        "target_mood": "low",
        "estimated_minutes": 12,
    },
    {
        "text": "What boundary do you want to honor this week, and why does it matter?",
        "category": "growth",
        "difficulty": "medium",
        "target_mood": "any",
        "estimated_minutes": 10,
    },
    {
        "text": "List five sensory details you noticed today (one sight, one sound, one smell, one taste, one texture).",
        "category": "mindfulness",
        "difficulty": "easy",
        "target_mood": "anxious",
        "estimated_minutes": 5,
    },
    {
        "text": "What's been weighing on you lately? Try writing about it without judging yourself.",
        "category": "emotion",
        "difficulty": "medium",
        "target_mood": "stressed",
        "estimated_minutes": 12,
    },
    {
        "text": "Describe a recent interaction that drained you, and one that energized you. What was different?",
        "category": "relationships",
        "difficulty": "medium",
        "target_mood": "any",
        "estimated_minutes": 10,
    },
    {
        "text": "What's a belief about yourself you'd like to gently challenge?",
        "category": "growth",
        "difficulty": "hard",
        "target_mood": "any",
        "estimated_minutes": 15,
    },
    {
        "text": "Imagine your most rested, supported self. What is one thing they would do today?",
        "category": "self_compassion",
        "difficulty": "easy",
        "target_mood": "low",
        "estimated_minutes": 6,
    },
    {
        "text": "What did your body try to tell you today? Did you listen?",
        "category": "mindfulness",
        "difficulty": "easy",
        "target_mood": "any",
        "estimated_minutes": 5,
    },
    {
        "text": "Write about a small win from the past week that you didn't celebrate.",
        "category": "reflection",
        "difficulty": "easy",
        "target_mood": "low",
        "estimated_minutes": 5,
    },
    {
        "text": "If you could remove one source of friction from your life this month, what would it be?",
        "category": "growth",
        "difficulty": "medium",
        "target_mood": "stressed",
        "estimated_minutes": 8,
    },
    {
        "text": "Describe a place where you feel safe. What is it about that place that calms you?",
        "category": "mindfulness",
        "difficulty": "easy",
        "target_mood": "anxious",
        "estimated_minutes": 6,
    },
    {
        "text": "What is something you've been avoiding? Write down one tiny step you could take.",
        "category": "growth",
        "difficulty": "medium",
        "target_mood": "any",
        "estimated_minutes": 8,
    },
    {
        "text": "When did you last laugh? What made it funny?",
        "category": "joy",
        "difficulty": "easy",
        "target_mood": "low",
        "estimated_minutes": 4,
    },
    {
        "text": "What would change if you treated yourself with the same kindness you give to a close friend?",
        "category": "self_compassion",
        "difficulty": "medium",
        "target_mood": "any",
        "estimated_minutes": 10,
    },
    {
        "text": "Where did you set down something heavy today, even briefly?",
        "category": "reflection",
        "difficulty": "easy",
        "target_mood": "stressed",
        "estimated_minutes": 5,
    },
    {
        "text": "What is one assumption you made today that turned out not to be true?",
        "category": "growth",
        "difficulty": "medium",
        "target_mood": "any",
        "estimated_minutes": 7,
    },
    {
        "text": "Describe your inner critic. What would change if you stopped believing every word?",
        "category": "self_compassion",
        "difficulty": "hard",
        "target_mood": "low",
        "estimated_minutes": 15,
    },
]


DEFAULT_TECHNIQUES: List[Dict[str, object]] = [
    {
        "key": "box_breathing_4_4_4_4",
        "name": "Box Breathing (4-4-4-4)",
        "description": "Inhale, hold, exhale, hold — each for four counts. Anchors attention through equal rhythm.",
        "guided_script": (
            "Sit with your back supported and close your eyes if comfortable.\n"
            "Inhale through your nose for four counts.\n"
            "Hold for four counts.\n"
            "Exhale through your mouth for four counts.\n"
            "Hold the empty breath for four counts.\n"
            "Repeat for the duration of the session."
        ),
        "typical_duration": 5,
        "category": "breathing",
        "difficulty": "beginner",
        "benefits": "Calms acute stress; improves focus; useful before meetings or sleep.",
    },
    {
        "key": "478_breathing",
        "name": "4-7-8 Breathing",
        "description": "Lengthened exhale that activates the parasympathetic nervous system.",
        "guided_script": (
            "Inhale through your nose for 4 counts.\n"
            "Hold the breath for 7 counts.\n"
            "Exhale slowly through your mouth for 8 counts.\n"
            "Repeat four cycles."
        ),
        "typical_duration": 4,
        "category": "breathing",
        "difficulty": "beginner",
        "benefits": "Promotes relaxation; supports sleep onset.",
    },
    {
        "key": "body_scan_progressive",
        "name": "Progressive Body Scan",
        "description": "Move attention slowly from feet to head, noticing sensation without changing it.",
        "guided_script": (
            "Lie or sit comfortably.\n"
            "Bring attention to your feet — notice temperature, weight, contact.\n"
            "Move slowly upward: calves, knees, thighs, hips, belly, chest, hands, arms, shoulders, neck, jaw, eyes, scalp.\n"
            "If your mind wanders, gently return to the body part you were on."
        ),
        "typical_duration": 15,
        "category": "awareness",
        "difficulty": "beginner",
        "benefits": "Releases held tension; supports interoception.",
    },
    {
        "key": "five_senses_grounding",
        "name": "5-4-3-2-1 Grounding",
        "description": "Notice five things you see, four you can touch, three you hear, two you smell, one you taste.",
        "guided_script": (
            "Notice 5 things you can see right now.\n"
            "Notice 4 things you can physically feel.\n"
            "Notice 3 sounds.\n"
            "Notice 2 things you can smell.\n"
            "Notice 1 thing you can taste, or one thing you're grateful for."
        ),
        "typical_duration": 5,
        "category": "grounding",
        "difficulty": "beginner",
        "benefits": "Interrupts spirals; anchors you in the present.",
    },
    {
        "key": "loving_kindness",
        "name": "Loving-Kindness Meditation",
        "description": "Direct warm wishes toward yourself, a loved one, a neutral person, and a difficult person.",
        "guided_script": (
            "Begin by sending the wish to yourself: 'May I be safe, may I be well, may I be at ease.'\n"
            "Then to someone you love.\n"
            "Then to someone neutral — a stranger, a barista.\n"
            "Then to someone difficult.\n"
            "Finally, all beings everywhere."
        ),
        "typical_duration": 12,
        "category": "compassion",
        "difficulty": "intermediate",
        "benefits": "Builds warmth; reduces rumination about conflict.",
    },
    {
        "key": "open_awareness",
        "name": "Open Awareness",
        "description": "Rather than focusing on one thing, allow whatever arises — sounds, thoughts, sensations — to come and go.",
        "guided_script": (
            "Sit upright.\n"
            "Let your attention be wide — like a sky in which everything moves through.\n"
            "Whatever arises (sound, thought, feeling), notice it and let it pass."
        ),
        "typical_duration": 10,
        "category": "awareness",
        "difficulty": "intermediate",
        "benefits": "Increases equanimity; reduces reactivity.",
    },
    {
        "key": "walking_meditation",
        "name": "Walking Meditation",
        "description": "Slow, deliberate walking with attention to each step and the breath.",
        "guided_script": (
            "Walk slower than usual.\n"
            "Notice the lift, swing, and placement of each foot.\n"
            "Sync the breath to a comfortable cadence.\n"
            "When the mind wanders, return to the soles of the feet."
        ),
        "typical_duration": 10,
        "category": "movement",
        "difficulty": "beginner",
        "benefits": "Combines movement with mindfulness; good for restlessness.",
    },
    {
        "key": "noting_practice",
        "name": "Noting Practice",
        "description": "Label experience softly as it arises — 'thinking', 'hearing', 'feeling'.",
        "guided_script": (
            "Sit comfortably and follow the breath.\n"
            "When a thought, sound, or sensation arises, label it softly in your mind ('thinking', 'sound', 'tension').\n"
            "Then return to the breath."
        ),
        "typical_duration": 10,
        "category": "awareness",
        "difficulty": "intermediate",
        "benefits": "Reduces fusion with thoughts; supports CBT-style decentering.",
    },
    {
        "key": "self_compassion_break",
        "name": "Self-Compassion Break",
        "description": "Three short phrases acknowledging suffering, common humanity, and kindness toward yourself.",
        "guided_script": (
            "Place a hand on your heart or another soothing spot.\n"
            "Say silently: 'This is a moment of difficulty.'\n"
            "Then: 'Difficulty is part of being human.'\n"
            "Then: 'May I be kind to myself right now.'"
        ),
        "typical_duration": 3,
        "category": "compassion",
        "difficulty": "beginner",
        "benefits": "Soothes acute distress; reframes shame.",
    },
    {
        "key": "savoring",
        "name": "Savoring Practice",
        "description": "Pick one pleasant experience from today and linger on its details for several minutes.",
        "guided_script": (
            "Recall something you enjoyed today, however small (sunlight, a meal, a message).\n"
            "Spend a few minutes recreating it in detail — the sights, sounds, and sensations.\n"
            "Let the warmth settle into your body."
        ),
        "typical_duration": 6,
        "category": "joy",
        "difficulty": "beginner",
        "benefits": "Strengthens positive memory consolidation; counteracts negativity bias.",
    },
]


def seed_default_prompts() -> int:
    """Insert the bundled prompt catalog if missing. Returns number inserted."""
    db = SessionLocal()
    inserted = 0
    try:
        existing = {row.text for row in db.query(JournalPrompt).all()}
        for prompt in DEFAULT_PROMPTS:
            if prompt["text"] in existing:
                continue
            db.add(JournalPrompt(**prompt))
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def seed_default_techniques() -> int:
    """Insert the bundled mindfulness technique library if missing."""
    db = SessionLocal()
    inserted = 0
    try:
        existing = {row.key for row in db.query(MindfulnessTechnique).all()}
        for technique in DEFAULT_TECHNIQUES:
            if technique["key"] in existing:
                continue
            db.add(MindfulnessTechnique(**technique))
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def init_journal_models() -> Dict[str, int]:
    """Create tables and seed defaults. Safe to call repeatedly."""
    from database import engine
    Base.metadata.create_all(bind=engine)
    return {
        "prompts_seeded": seed_default_prompts(),
        "techniques_seeded": seed_default_techniques(),
    }
