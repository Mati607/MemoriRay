"""
Analytics service for mood tracking, pattern detection, and insight generation.
Provides utilities for analyzing mood trends, identifying triggers, and generating personalized insights.
"""

import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
from collections import defaultdict, Counter

from database import (
    SessionLocal, MoodEntry, TherapyExercise, MoodInsight,
    add_mood_insight, save_weekly_report, get_mood_history
)


class MoodAnalytics:
    """Analyzes mood data and generates insights."""

    @staticmethod
    def get_mood_statistics(user_id: int, days: int = 30) -> Dict:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            entries = (
                db.query(MoodEntry)
                .filter(MoodEntry.user_id == user_id, MoodEntry.timestamp >= cutoff)
                .all()
            )

            if not entries:
                return {
                    "avg_mood": None,
                    "min_mood": None,
                    "max_mood": None,
                    "volatility": None,
                    "total_entries": 0,
                }

            scores = [e.mood_score for e in entries if e.mood_score is not None]
            if not scores:
                return {
                    "avg_mood": None,
                    "min_mood": None,
                    "max_mood": None,
                    "volatility": None,
                    "total_entries": len(entries),
                }

            return {
                "avg_mood": round(statistics.mean(scores), 2),
                "min_mood": min(scores),
                "max_mood": max(scores),
                "volatility": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
                "total_entries": len(entries),
            }
        finally:
            db.close()

    @staticmethod
    def identify_mood_patterns(user_id: int, days: int = 30) -> Dict:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            entries = (
                db.query(MoodEntry)
                .filter(MoodEntry.user_id == user_id, MoodEntry.timestamp >= cutoff)
                .order_by(MoodEntry.timestamp.asc())
                .all()
            )

            if not entries:
                return {"patterns": [], "best_day": None, "worst_day": None}

            daily_moods = defaultdict(list)
            emotions = []

            for entry in entries:
                day_name = entry.timestamp.strftime("%A")
                if entry.mood_score is not None:
                    daily_moods[day_name].append(entry.mood_score)
                if entry.emotion_category:
                    emotions.append(entry.emotion_category)

            daily_avg = {
                day: round(statistics.mean(scores), 2)
                for day, scores in daily_moods.items()
                if scores
            }

            best_day = max(daily_avg.items(), key=lambda x: x[1])[0] if daily_avg else None
            worst_day = min(daily_avg.items(), key=lambda x: x[1])[0] if daily_avg else None

            emotion_freq = Counter(emotions) if emotions else {}
            dominant_emotions = [emotion for emotion, _ in emotion_freq.most_common(3)]

            return {
                "daily_averages": daily_avg,
                "best_day": best_day,
                "worst_day": worst_day,
                "dominant_emotions": dominant_emotions,
                "emotion_distribution": dict(emotion_freq),
            }
        finally:
            db.close()

    @staticmethod
    def detect_mood_triggers(user_id: int, days: int = 30) -> List[Dict]:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            entries = (
                db.query(MoodEntry)
                .filter(MoodEntry.user_id == user_id, MoodEntry.timestamp >= cutoff)
                .order_by(MoodEntry.timestamp.desc())
                .all()
            )

            triggers_found = []
            low_mood_entries = [e for e in entries if e.mood_score and e.mood_score < 4]

            for entry in low_mood_entries[:10]:
                if entry.triggers:
                    triggers_found.append({
                        "trigger": entry.triggers,
                        "mood_score": entry.mood_score,
                        "emotion": entry.emotion_category,
                        "date": entry.timestamp.isoformat(),
                    })

            trigger_frequency = Counter()
            for trigger_data in triggers_found:
                trigger_frequency[trigger_data["trigger"]] += 1

            return [
                {
                    "trigger": trigger,
                    "frequency": count,
                    "impact": "high" if count >= 3 else "medium" if count >= 2 else "low",
                }
                for trigger, count in trigger_frequency.most_common(5)
            ]
        finally:
            db.close()

    @staticmethod
    def generate_weekly_summary(user_id: int) -> Dict:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=now.weekday())
            week_end = week_start + timedelta(days=7)

            entries = (
                db.query(MoodEntry)
                .filter(
                    MoodEntry.user_id == user_id,
                    MoodEntry.timestamp >= week_start,
                    MoodEntry.timestamp < week_end,
                )
                .all()
            )

            exercises = (
                db.query(TherapyExercise)
                .filter(
                    TherapyExercise.user_id == user_id,
                    TherapyExercise.completed_at >= week_start,
                    TherapyExercise.completed_at < week_end,
                )
                .all()
            )

            stats = MoodAnalytics.get_mood_statistics(user_id, days=7)
            patterns = MoodAnalytics.identify_mood_patterns(user_id, days=7)

            effectiveness_ratings = [
                e.effectiveness_rating for e in exercises if e.effectiveness_rating is not None
            ]
            avg_effectiveness = round(statistics.mean(effectiveness_ratings), 2) if effectiveness_ratings else None

            return {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "avg_mood_score": stats.get("avg_mood"),
                "volatility": stats.get("volatility"),
                "best_day": patterns.get("best_day"),
                "worst_day": patterns.get("worst_day"),
                "dominant_emotions": patterns.get("dominant_emotions"),
                "exercises_completed": len(exercises),
                "avg_exercise_effectiveness": avg_effectiveness,
                "total_entries": stats.get("total_entries"),
            }
        finally:
            db.close()

    @staticmethod
    def generate_improvement_suggestions(user_id: int) -> List[str]:
        stats = MoodAnalytics.get_mood_statistics(user_id, days=30)
        patterns = MoodAnalytics.identify_mood_patterns(user_id, days=30)
        triggers = MoodAnalytics.detect_mood_triggers(user_id, days=30)

        suggestions = []

        if stats.get("volatility") and stats["volatility"] > 2.5:
            suggestions.append(
                "Your mood fluctuates significantly. Consider mindfulness exercises to stabilize emotions."
            )

        if stats.get("avg_mood") and stats["avg_mood"] < 4:
            suggestions.append(
                "Your average mood is below 4. Speaking with a therapist could provide valuable support."
            )

        worst_day = patterns.get("worst_day")
        if worst_day:
            suggestions.append(
                f"{worst_day}s are challenging for you. Try scheduling positive activities on these days."
            )

        if triggers:
            top_trigger = triggers[0]
            suggestions.append(
                f"'{top_trigger['trigger']}' appears to be a significant trigger. Consider developing coping strategies."
            )

        dominant_emotion = patterns.get("dominant_emotions", [None])[0]
        if dominant_emotion:
            suggestions.append(
                f"You frequently experience {dominant_emotion}. Exercises targeting this emotion may help."
            )

        return suggestions[:5]


class TherapyRecommender:
    """Recommends therapy exercises based on mood and patterns."""

    EXERCISE_DATABASE = {
        "breathing": {
            "name": "Box Breathing",
            "description": "Calming breathing technique to reduce anxiety",
            "best_for": ["anxiety", "stress", "panic"],
        },
        "grounding": {
            "name": "5-4-3-2-1 Grounding",
            "description": "Sensory grounding technique to stay present",
            "best_for": ["anxiety", "dissociation", "panic"],
        },
        "body_scan": {
            "name": "Progressive Body Scan",
            "description": "Mindfulness technique for body awareness",
            "best_for": ["stress", "tension", "anxiety"],
        },
        "gratitude": {
            "name": "Gratitude Reflection",
            "description": "Write down 3 things you're grateful for",
            "best_for": ["depression", "low_mood", "sadness"],
        },
        "journaling": {
            "name": "Emotion Journal",
            "description": "Write about your feelings and experiences",
            "best_for": ["stress", "anxiety", "confusion"],
        },
        "cognitive_reframing": {
            "name": "Thought Challenge",
            "description": "Identify and reframe negative thought patterns",
            "best_for": ["depression", "anxiety", "low_mood"],
        },
        "physical_activity": {
            "name": "Movement Break",
            "description": "5-10 minute physical activity or stretch",
            "best_for": ["depression", "stress", "low_energy"],
        },
        "self_compassion": {
            "name": "Self-Compassion Practice",
            "description": "Speak to yourself with kindness and understanding",
            "best_for": ["shame", "self_criticism", "low_self_esteem"],
        },
    }

    @staticmethod
    def recommend_exercises(user_id: int, top_n: int = 3) -> List[Dict]:
        patterns = MoodAnalytics.identify_mood_patterns(user_id, days=30)
        dominant_emotions = patterns.get("dominant_emotions", [])

        if not dominant_emotions:
            return []

        recommended = []
        seen_types = set()

        for emotion in dominant_emotions:
            for exercise_type, exercise_data in TherapyRecommender.EXERCISE_DATABASE.items():
                if exercise_type not in seen_types and emotion in exercise_data["best_for"]:
                    recommended.append({
                        "exercise_type": exercise_type,
                        "name": exercise_data["name"],
                        "description": exercise_data["description"],
                        "reason": f"Helpful for managing {emotion}",
                    })
                    seen_types.add(exercise_type)
                    if len(recommended) >= top_n:
                        break
            if len(recommended) >= top_n:
                break

        return recommended[:top_n]


class InsightGenerator:
    """Generates actionable insights from mood data."""

    @staticmethod
    def generate_all_insights(user_id: int) -> List[Dict]:
        insights = []

        stats = MoodAnalytics.get_mood_statistics(user_id, days=30)
        if stats.get("avg_mood"):
            if stats["avg_mood"] < 3:
                insights.append({
                    "type": "mood_alert",
                    "title": "Low Average Mood",
                    "description": f"Your average mood over the past month is {stats['avg_mood']}/10. Consider reaching out for support.",
                    "confidence": 0.95,
                })
            elif stats["avg_mood"] >= 7:
                insights.append({
                    "type": "positive_trend",
                    "title": "Strong Mental Well-being",
                    "description": "Your average mood indicates positive mental health. Keep up your current practices!",
                    "confidence": 0.90,
                })

        patterns = MoodAnalytics.identify_mood_patterns(user_id, days=30)
        if len(patterns.get("emotion_distribution", {})) > 0:
            top_emotion = max(patterns["emotion_distribution"].items(), key=lambda x: x[1])
            insights.append({
                "type": "emotion_pattern",
                "title": f"Frequent {top_emotion[0].title()} Experience",
                "description": f"You frequently experience {top_emotion[0]}. This pattern may indicate areas for growth.",
                "confidence": 0.85,
            })

        triggers = MoodAnalytics.detect_mood_triggers(user_id, days=30)
        if triggers:
            top_trigger = triggers[0]
            insights.append({
                "type": "trigger_awareness",
                "title": "Key Trigger Identified",
                "description": f"'{top_trigger['trigger']}' appears {top_trigger['frequency']} times as a mood trigger.",
                "confidence": 0.88,
            })

        if stats.get("volatility"):
            if stats["volatility"] > 2:
                insights.append({
                    "type": "volatility_alert",
                    "title": "High Mood Variability",
                    "description": "Your mood varies significantly day-to-day. Stability exercises might help.",
                    "confidence": 0.82,
                })

        return insights
