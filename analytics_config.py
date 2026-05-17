"""
Configuration for the analytics and therapy exercises system.
Defines thresholds, defaults, and behavioral parameters.
"""

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class MoodThresholds:
    """Define mood score ranges and interpretations."""
    CRITICAL_LOW = 2.0
    LOW = 4.0
    NEUTRAL = 5.0
    GOOD = 7.0
    EXCELLENT = 9.0

    LABELS = {
        (0, 2): "Crisis Level",
        (2, 4): "Needs Support",
        (4, 6): "Neutral",
        (6, 8): "Good",
        (8, 10): "Excellent",
    }

    @staticmethod
    def get_label(score: float) -> str:
        for range_tuple, label in MoodThresholds.LABELS.items():
            if range_tuple[0] <= score < range_tuple[1]:
                return label
        return "Excellent"

    @staticmethod
    def get_emoji(score: float) -> str:
        if score <= 2:
            return "🚨"
        elif score <= 4:
            return "😢"
        elif score <= 6:
            return "😐"
        elif score <= 8:
            return "😊"
        else:
            return "🤩"


@dataclass
class AnalyticsDefaults:
    """Default parameters for analytics calculations."""
    DEFAULT_DAYS = 30
    MAX_DAYS = 90
    MIN_ENTRIES_FOR_ANALYSIS = 5
    RECENT_ENTRIES_COUNT = 10
    TOP_TRIGGERS_COUNT = 5
    TOP_RECOMMENDATIONS = 3
    INSIGHT_CONFIDENCE_MIN = 0.7


@dataclass
class ExerciseConfig:
    """Configuration for therapy exercises."""
    DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]
    CATEGORIES = ["anxiety", "depression", "stress", "shame", "trauma", "general"]
    MAX_EFFECTIVENESS = 5.0
    MIN_DURATION = 1
    MAX_DURATION = 120

    ESTIMATED_DURATIONS = {
        "breathing": 5,
        "grounding": 10,
        "body_scan": 15,
        "gratitude": 10,
        "journaling": 20,
        "cognitive_reframing": 15,
        "physical_activity": 10,
        "self_compassion": 5,
    }


@dataclass
class VolatilityThresholds:
    """Define mood volatility ranges."""
    STABLE = 0.5
    MODERATE = 1.5
    VARIABLE = 2.5
    HIGHLY_VARIABLE = 3.5

    @staticmethod
    def get_stability_label(volatility: float) -> str:
        if volatility <= VolatilityThresholds.STABLE:
            return "Very Stable"
        elif volatility <= VolatilityThresholds.MODERATE:
            return "Stable"
        elif volatility <= VolatilityThresholds.VARIABLE:
            return "Variable"
        elif volatility <= VolatilityThresholds.HIGHLY_VARIABLE:
            return "Highly Variable"
        else:
            return "Extremely Volatile"

    @staticmethod
    def needs_stability_support(volatility: float) -> bool:
        return volatility > VolatilityThresholds.VARIABLE


EMOTION_TO_EXERCISE_MAPPING: Dict[str, List[str]] = {
    "anxiety": ["breathing", "grounding", "body_scan"],
    "stress": ["body_scan", "journaling", "physical_activity"],
    "depression": ["gratitude", "cognitive_reframing", "physical_activity"],
    "sad": ["gratitude", "physical_activity", "self_compassion"],
    "angry": ["breathing", "physical_activity", "journaling"],
    "overwhelmed": ["grounding", "breathing", "body_scan"],
    "calm": [],
    "happy": [],
    "peaceful": [],
    "hopeful": [],
}

INSIGHT_WEIGHTS = {
    "mood_alert": 1.0,
    "positive_trend": 0.8,
    "emotion_pattern": 0.7,
    "trigger_awareness": 0.9,
    "volatility_alert": 0.85,
}

WEEKLY_REPORT_TEMPLATE = {
    "week_start": "",
    "week_end": "",
    "avg_mood_score": None,
    "best_day": None,
    "worst_day": None,
    "mood_volatility": None,
    "dominant_emotions": [],
    "exercises_completed": 0,
    "avg_exercise_effectiveness": None,
    "total_entries": 0,
    "key_improvements": [],
    "recommendations": [],
}

CRISIS_INDICATORS = {
    "hopeless": 1.0,
    "suicide": 1.0,
    "harm": 1.0,
    "worthless": 0.9,
    "crisis": 1.0,
    "death": 0.8,
    "emergency": 1.0,
}

POSITIVE_INDICATORS = {
    "better": 0.6,
    "improving": 0.7,
    "grateful": 0.8,
    "connected": 0.7,
    "supported": 0.7,
    "hopeful": 0.8,
}


class AnalyticsMessages:
    """Standard messages for analytics insights."""

    VOLATILITY_HIGH = "Your mood fluctuates significantly. Try mindfulness exercises or meditation."
    VOLATILITY_STABLE = "Your mood is stable. Continue current self-care practices."

    MOOD_IMPROVING = "Your mood trend is improving! Keep up these positive practices."
    MOOD_DECLINING = "Your mood trend suggests you might benefit from additional support."

    TRIGGER_IDENTIFIED = "We've identified a key trigger. Consider developing specific coping strategies."
    NO_CLEAR_TRIGGERS = "Keep tracking to identify patterns and triggers."

    EXERCISE_RECOMMENDED = "Based on your emotions, this exercise may help."
    EXERCISE_PROGRESS = "Great progress! Continue practicing these exercises."

    CRISIS_ALERT = "You seem to be in distress. Please reach out to a mental health professional or crisis line."
    SUPPORT_AVAILABLE = "Remember: support is available. You're not alone in this."


class CrisisResources:
    """Crisis support resources and hotlines."""

    HOTLINES = {
        "US": {
            "988 Suicide & Crisis Lifeline": "988 or 1-800-273-8255",
            "Crisis Text Line": "Text HOME to 741741",
            "NAMI": "1-800-950-NAMI (6264)",
        },
        "UK": {
            "Samaritans": "116 123",
            "Crisis Text Line": "Text HELLO to 50808",
        },
        "Canada": {
            "1-800-Suicide": "1-800-784-2433",
            "Distress Centre": "1-888-311-4357",
        },
    }

    MESSAGE = """
    If you're having thoughts of self-harm or suicide, please reach out:
    - Call emergency services (911 in US)
    - Contact a crisis hotline
    - Go to your nearest emergency room
    - Tell someone you trust immediately

    You matter. Help is available.
    """
