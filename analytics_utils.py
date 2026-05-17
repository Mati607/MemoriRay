"""
Utility functions for analytics visualization and data processing.
Provides helpers for formatting, aggregation, and transformations.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
import statistics
from analytics_config import MoodThresholds, VolatilityThresholds, AnalyticsDefaults


def format_mood_score(score: float) -> str:
    """Format mood score with emoji and label."""
    emoji = MoodThresholds.get_emoji(score)
    label = MoodThresholds.get_label(score)
    return f"{emoji} {score:.1f}/10 ({label})"


def format_volatility(volatility: float) -> str:
    """Format volatility with label and assessment."""
    label = VolatilityThresholds.get_stability_label(volatility)
    needs_support = VolatilityThresholds.needs_stability_support(volatility)
    support_msg = " - Consider stability exercises" if needs_support else " - Stable pattern"
    return f"σ = {volatility:.2f} ({label}){support_msg}"


def get_mood_trend(scores: List[float]) -> str:
    """Determine if mood is trending up, down, or stable."""
    if len(scores) < 2:
        return "insufficient_data"

    first_half_avg = statistics.mean(scores[:len(scores)//2])
    second_half_avg = statistics.mean(scores[len(scores)//2:])
    diff = second_half_avg - first_half_avg

    if diff > 1.0:
        return "improving"
    elif diff < -1.0:
        return "declining"
    else:
        return "stable"


def get_mood_trend_emoji(trend: str) -> str:
    """Get emoji for mood trend."""
    trends = {
        "improving": "📈",
        "declining": "📉",
        "stable": "➡️",
        "insufficient_data": "❓"
    }
    return trends.get(trend, "❓")


def calculate_recovery_time(mood_scores: List[float]) -> int:
    """Estimate how many days it takes to recover from low mood."""
    if not mood_scores or len(mood_scores) < 2:
        return 0

    recovery_times = []
    in_low_mood = False

    for i, score in enumerate(mood_scores):
        if score < 4.0 and not in_low_mood:
            in_low_mood = True
            start_idx = i
        elif score >= 5.0 and in_low_mood:
            in_low_mood = False
            recovery_time = i - start_idx
            recovery_times.append(recovery_time)

    return int(statistics.mean(recovery_times)) if recovery_times else 0


def get_best_time_of_day(timestamps: List[datetime], scores: List[float]) -> str:
    """Determine which time of day mood is typically best."""
    if not timestamps or not scores:
        return "unknown"

    time_periods = {
        "morning": (6, 12),
        "afternoon": (12, 17),
        "evening": (17, 21),
        "night": (21, 24),
    }

    period_scores = {period: [] for period in time_periods}

    for timestamp, score in zip(timestamps, scores):
        hour = timestamp.hour
        for period, (start, end) in time_periods.items():
            if start <= hour < end:
                period_scores[period].append(score)
                break

    valid_periods = {p: statistics.mean(s) for p, s in period_scores.items() if s}

    if not valid_periods:
        return "unknown"

    best_period = max(valid_periods.items(), key=lambda x: x[1])[0]
    return best_period


def get_worst_time_of_day(timestamps: List[datetime], scores: List[float]) -> str:
    """Determine which time of day mood is typically worst."""
    if not timestamps or not scores:
        return "unknown"

    time_periods = {
        "morning": (6, 12),
        "afternoon": (12, 17),
        "evening": (17, 21),
        "night": (21, 24),
    }

    period_scores = {period: [] for period in time_periods}

    for timestamp, score in zip(timestamps, scores):
        hour = timestamp.hour
        for period, (start, end) in time_periods.items():
            if start <= hour < end:
                period_scores[period].append(score)
                break

    valid_periods = {p: statistics.mean(s) for p, s in period_scores.items() if s}

    if not valid_periods:
        return "unknown"

    worst_period = min(valid_periods.items(), key=lambda x: x[1])[0]
    return worst_period


def categorize_mood_score(score: float) -> str:
    """Categorize mood score into bins."""
    if score < 2:
        return "crisis"
    elif score < 4:
        return "poor"
    elif score < 6:
        return "neutral"
    elif score < 8:
        return "good"
    else:
        return "excellent"


def get_category_emoji(category: str) -> str:
    """Get emoji for mood category."""
    emojis = {
        "crisis": "🚨",
        "poor": "😢",
        "neutral": "😐",
        "good": "😊",
        "excellent": "🤩",
    }
    return emojis.get(category, "❓")


def smooth_mood_data(scores: List[float], window: int = 3) -> List[float]:
    """Smooth mood data using moving average."""
    if len(scores) < window:
        return scores

    smoothed = []
    for i in range(len(scores)):
        start = max(0, i - window // 2)
        end = min(len(scores), i + window // 2 + 1)
        smoothed.append(statistics.mean(scores[start:end]))

    return smoothed


def find_mood_peaks(scores: List[float], threshold: float = 7.0) -> List[Tuple[int, float]]:
    """Find peaks (high mood values) in mood data."""
    peaks = []
    for i, score in enumerate(scores):
        if score >= threshold:
            peaks.append((i, score))
    return peaks


def find_mood_valleys(scores: List[float], threshold: float = 3.0) -> List[Tuple[int, float]]:
    """Find valleys (low mood values) in mood data."""
    valleys = []
    for i, score in enumerate(scores):
        if score <= threshold:
            valleys.append((i, score))
    return valleys


def get_consecutive_low_mood_days(scores: List[float], threshold: float = 4.0) -> int:
    """Get longest streak of consecutive low mood days."""
    max_streak = 0
    current_streak = 0

    for score in scores:
        if score < threshold:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return max_streak


def estimate_mood_trajectory(scores: List[float], days_ahead: int = 7) -> List[float]:
    """Simple linear regression to estimate future mood."""
    if len(scores) < 2:
        return []

    n = len(scores)
    x = list(range(n))
    y = scores

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return [mean_y] * days_ahead

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    trajectory = []
    for i in range(n, n + days_ahead):
        predicted = slope * i + intercept
        predicted = max(0, min(10, predicted))
        trajectory.append(predicted)

    return trajectory


def get_emotion_intensity_distribution(intensities: List[float]) -> Dict[str, int]:
    """Categorize emotion intensities."""
    if not intensities:
        return {"none": 0, "mild": 0, "moderate": 0, "intense": 0, "overwhelming": 0}

    distribution = {"none": 0, "mild": 0, "moderate": 0, "intense": 0, "overwhelming": 0}

    for intensity in intensities:
        if intensity == 0:
            distribution["none"] += 1
        elif intensity <= 2:
            distribution["mild"] += 1
        elif intensity <= 5:
            distribution["moderate"] += 1
        elif intensity <= 8:
            distribution["intense"] += 1
        else:
            distribution["overwhelming"] += 1

    return distribution


def generate_summary_statement(stats: Dict, patterns: Dict) -> str:
    """Generate human-readable summary statement from analytics."""
    statements = []

    avg_mood = stats.get("avg_mood")
    if avg_mood:
        if avg_mood >= 7:
            statements.append(f"Your overall mood is positive ({avg_mood:.1f}/10).")
        elif avg_mood >= 5:
            statements.append(f"Your mood is neutral ({avg_mood:.1f}/10).")
        else:
            statements.append(f"Your mood needs support ({avg_mood:.1f}/10).")

    best_day = patterns.get("best_day")
    if best_day:
        statements.append(f"{best_day}s are typically your best days.")

    worst_day = patterns.get("worst_day")
    if worst_day:
        statements.append(f"You tend to struggle on {worst_day}s.")

    dominant_emotions = patterns.get("dominant_emotions", [])
    if dominant_emotions:
        emotion_str = ", ".join(dominant_emotions[:2])
        statements.append(f"Your dominant emotions are {emotion_str}.")

    return " ".join(statements)


def format_date_range(start: datetime, end: datetime) -> str:
    """Format a date range nicely."""
    start_str = start.strftime("%b %d")
    end_str = end.strftime("%b %d, %Y")
    return f"{start_str} - {end_str}"


def get_week_number(date: datetime) -> int:
    """Get week number of the year."""
    return date.isocalendar()[1]


def get_session_duration(start_time: datetime, end_time: datetime) -> str:
    """Format duration between two times."""
    delta = end_time - start_time
    minutes = int(delta.total_seconds() / 60)
    hours = minutes // 60
    minutes = minutes % 60

    if hours == 0:
        return f"{minutes} min"
    elif minutes == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {minutes}m"
