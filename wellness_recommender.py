"""
Wellness recommendations engine that provides personalized suggestions
based on mood data, patterns, and therapeutic approaches.
"""

from typing import List, Dict, Optional
from analytics_service import MoodAnalytics
from analytics_config import EMOTION_TO_EXERCISE_MAPPING


class WellnessRecommender:
    """Generate personalized wellness recommendations."""

    RECOMMENDATIONS_DB = {
        "high_volatility": {
            "title": "Your mood fluctuates significantly",
            "description": "Practice stability-focused exercises like meditation and body scans",
            "actions": [
                "Try a daily 10-minute meditation",
                "Practice progressive muscle relaxation",
                "Maintain consistent sleep schedule",
                "Track mood at same times daily",
            ],
            "priority": "high",
            "emoji": "🌪️",
        },
        "low_mood": {
            "title": "Your overall mood is concerning",
            "description": "Increase positive activities and consider professional support",
            "actions": [
                "Schedule pleasant activities daily",
                "Reach out to friends or family",
                "Consider therapy or counseling",
                "Practice gratitude journaling",
            ],
            "priority": "critical",
            "emoji": "😢",
        },
        "anxiety_dominant": {
            "title": "Anxiety appears to be significant",
            "description": "Focus on grounding and breathing techniques",
            "actions": [
                "Practice 5-4-3-2-1 grounding technique",
                "Try box breathing (4-4-4-4)",
                "Limit caffeine intake",
                "Do regular exercise",
            ],
            "priority": "high",
            "emoji": "😰",
        },
        "depression_dominant": {
            "title": "Depression symptoms are present",
            "description": "Engage in behavioral activation and self-care",
            "actions": [
                "Set small, achievable daily goals",
                "Spend time in sunlight",
                "Connect with others",
                "Practice self-compassion",
            ],
            "priority": "high",
            "emoji": "☁️",
        },
        "stress_accumulation": {
            "title": "Stress levels are building",
            "description": "Use stress-relief techniques and create boundaries",
            "actions": [
                "Take regular breaks throughout the day",
                "Practice deep breathing",
                "Set boundaries with work",
                "Engage in hobbies",
            ],
            "priority": "medium",
            "emoji": "😓",
        },
        "low_activity": {
            "title": "You're not completing many exercises",
            "description": "Increase therapeutic activity engagement",
            "actions": [
                "Start with 1 exercise daily",
                "Choose activities you enjoy",
                "Set reminders for exercise time",
                "Track effectiveness ratings",
            ],
            "priority": "medium",
            "emoji": "🏃",
        },
        "positive_trend": {
            "title": "Your mood is improving!",
            "description": "Continue current positive practices and build on success",
            "actions": [
                "Maintain current healthy habits",
                "Celebrate progress with yourself",
                "Set new wellness goals",
                "Help others with similar challenges",
            ],
            "priority": "low",
            "emoji": "📈",
        },
        "sleep_importance": {
            "title": "Sleep is crucial for your mental health",
            "description": "Prioritize consistent sleep schedule and quality",
            "actions": [
                "Aim for 7-9 hours nightly",
                "Go to bed at same time daily",
                "Avoid screens 1 hour before bed",
                "Create a calm bedroom environment",
            ],
            "priority": "medium",
            "emoji": "😴",
        },
        "social_connection": {
            "title": "Social connection matters",
            "description": "Reach out to friends, family, or support groups",
            "actions": [
                "Schedule time with supportive people",
                "Join a support group",
                "Attend community events",
                "Share your feelings with trusted people",
            ],
            "priority": "medium",
            "emoji": "🤝",
        },
        "professional_help": {
            "title": "Professional support may help",
            "description": "Consider therapy or counseling services",
            "actions": [
                "Research local therapists",
                "Check insurance coverage",
                "Try teletherapy options",
                "Discuss with your doctor",
            ],
            "priority": "critical",
            "emoji": "👨‍⚕️",
        },
    }

    @staticmethod
    def generate_recommendations(user_id: int) -> List[Dict]:
        """Generate personalized wellness recommendations."""
        recommendations = []

        stats = MoodAnalytics.get_mood_statistics(user_id, days=30)
        patterns = MoodAnalytics.identify_mood_patterns(user_id, days=30)
        triggers = MoodAnalytics.detect_mood_triggers(user_id, days=30)

        avg_mood = stats.get("avg_mood")
        volatility = stats.get("volatility")
        dominant_emotions = patterns.get("dominant_emotions", [])

        if volatility and volatility > 2.5:
            recommendations.append(
                WellnessRecommender._create_recommendation("high_volatility")
            )

        if avg_mood and avg_mood < 3:
            recommendations.append(
                WellnessRecommender._create_recommendation("low_mood")
            )
            recommendations.append(
                WellnessRecommender._create_recommendation("professional_help")
            )

        elif avg_mood and avg_mood < 5:
            recommendations.append(
                WellnessRecommender._create_recommendation("low_mood")
            )

        if "anxiety" in dominant_emotions or "anxious" in dominant_emotions:
            recommendations.append(
                WellnessRecommender._create_recommendation("anxiety_dominant")
            )

        if "depression" in dominant_emotions or "sad" in dominant_emotions:
            recommendations.append(
                WellnessRecommender._create_recommendation("depression_dominant")
            )

        if volatility and volatility > 2 and triggers and len(triggers) >= 3:
            recommendations.append(
                WellnessRecommender._create_recommendation("stress_accumulation")
            )

        if not stats.get("total_entries", 0) >= 10:
            recommendations.append(
                WellnessRecommender._create_recommendation("low_activity")
            )

        if avg_mood and avg_mood >= 6:
            recommendations.append(
                WellnessRecommender._create_recommendation("positive_trend")
            )

        recommendations.append(
            WellnessRecommender._create_recommendation("sleep_importance")
        )

        recommendations.append(
            WellnessRecommender._create_recommendation("social_connection")
        )

        sorted_recs = sorted(
            recommendations,
            key=lambda x: {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
            }.get(x.get("priority", "low"), 4)
        )

        return sorted_recs

    @staticmethod
    def _create_recommendation(rec_type: str) -> Dict:
        """Create a recommendation object."""
        if rec_type not in WellnessRecommender.RECOMMENDATIONS_DB:
            return {}

        rec_data = WellnessRecommender.RECOMMENDATIONS_DB[rec_type]
        return {
            "type": rec_type,
            "title": rec_data["title"],
            "description": rec_data["description"],
            "actions": rec_data["actions"],
            "priority": rec_data["priority"],
            "emoji": rec_data["emoji"],
        }

    @staticmethod
    def get_action_plan(user_id: int, days: int = 7) -> Dict:
        """Generate a customized action plan for the next N days."""
        recommendations = WellnessRecommender.generate_recommendations(user_id)

        action_plan = {
            "duration_days": days,
            "priority_actions": [],
            "daily_schedule": [],
        }

        for rec in recommendations[:3]:
            action_plan["priority_actions"].extend(
                [
                    {
                        "action": action,
                        "category": rec["type"],
                        "priority": rec["priority"],
                    }
                    for action in rec["actions"][:2]
                ]
            )

        daily_schedule = [
            {
                "day": day,
                "morning": "Complete mood check-in",
                "afternoon": "Practice one recommended exercise",
                "evening": "Journal about your day",
            }
            for day in range(1, days + 1)
        ]

        action_plan["daily_schedule"] = daily_schedule

        return action_plan

    @staticmethod
    def get_crisis_support_info() -> Dict:
        """Get crisis support resources."""
        return {
            "warning_signs": [
                "Persistent thoughts of hopelessness",
                "Withdrawal from friends and family",
                "Increased substance use",
                "Talk of suicide or self-harm",
                "Extreme mood changes",
                "Inability to perform daily tasks",
            ],
            "immediate_help": {
                "us": {
                    "988_suicide_crisis_lifeline": "Call 988",
                    "crisis_text_line": "Text HOME to 741741",
                    "emergency": "Call 911",
                },
                "international": {
                    "befrienders": "1-800-273-8255",
                    "samaritans_uk": "116 123",
                    "lifeline_au": "13 11 14",
                },
            },
            "message": "If you're in crisis, please reach out to a professional immediately. You are not alone.",
        }


class CopingStrategyAdvisor:
    """Provide coping strategies for specific situations and emotions."""

    COPING_STRATEGIES = {
        "anxiety": {
            "immediate": [
                "Box breathing: 4-4-4-4 count",
                "5-4-3-2-1 grounding technique",
                "Cold water on face (dive reflex)",
                "Progressive muscle relaxation",
            ],
            "short_term": [
                "20-minute walk",
                "Call a trusted friend",
                "Journal your worries",
                "Gentle yoga or stretching",
            ],
            "long_term": [
                "Regular exercise routine",
                "Meditation practice",
                "Therapy or counseling",
                "Stress management classes",
            ],
        },
        "depression": {
            "immediate": [
                "Step outside for sunlight",
                "Do one small task",
                "Reach out to someone",
                "Listen to uplifting music",
            ],
            "short_term": [
                "Engage in a hobby",
                "Spend time with others",
                "Practice self-compassion",
                "Do physical activity",
            ],
            "long_term": [
                "Therapy or counseling",
                "Consistent exercise",
                "Social connection",
                "Medication if appropriate",
            ],
        },
        "anger": {
            "immediate": [
                "Take 10 deep breaths",
                "Count to 10 slowly",
                "Physical activity (run, punch pillow)",
                "Write angry letter (don't send)",
            ],
            "short_term": [
                "Cool down period alone",
                "Exercise vigorously",
                "Write in journal",
                "Talk to trusted person",
            ],
            "long_term": [
                "Anger management classes",
                "Therapy to explore triggers",
                "Regular exercise routine",
                "Meditation and mindfulness",
            ],
        },
        "loneliness": {
            "immediate": [
                "Text a friend",
                "Join an online community",
                "Call someone you know",
                "Spend time with pet (if have one)",
            ],
            "short_term": [
                "Schedule time with friends",
                "Join a group or club",
                "Volunteer somewhere",
                "Take a class",
            ],
            "long_term": [
                "Build consistent relationships",
                "Join support group",
                "Community involvement",
                "Develop social skills",
            ],
        },
        "stress": {
            "immediate": [
                "Take 5-minute break",
                "Do breathing exercise",
                "Step outside",
                "Drink water",
            ],
            "short_term": [
                "30-minute relaxation activity",
                "Talk with someone",
                "Organize your space",
                "Do something enjoyable",
            ],
            "long_term": [
                "Identify stressors",
                "Develop time management",
                "Regular exercise and sleep",
                "Consider therapy",
            ],
        },
    }

    @staticmethod
    def get_strategy_for_emotion(emotion: str, urgency: str = "immediate") -> List[str]:
        """Get coping strategies for a specific emotion."""
        emotion_lower = emotion.lower()

        if emotion_lower not in CopingStrategyAdvisor.COPING_STRATEGIES:
            return ["Practice self-compassion", "Reach out for support", "Give yourself time"]

        strategies = CopingStrategyAdvisor.COPING_STRATEGIES[emotion_lower]
        return strategies.get(urgency, strategies.get("immediate", []))

    @staticmethod
    def generate_coping_toolkit(dominant_emotions: List[str]) -> Dict:
        """Generate a personalized coping toolkit."""
        toolkit = {
            "toolkit_name": "Your Personalized Coping Toolkit",
            "emotions_addressed": dominant_emotions,
            "immediate_strategies": [],
            "daily_practices": [],
            "professional_help": [],
        }

        unique_strategies = set()
        for emotion in dominant_emotions[:3]:
            for strategy in CopingStrategyAdvisor.get_strategy_for_emotion(emotion, "immediate"):
                unique_strategies.add(strategy)

        toolkit["immediate_strategies"] = list(unique_strategies)[:5]

        toolkit["daily_practices"] = [
            "Morning: 5-minute mindfulness or breathing",
            "Midday: Short walk or movement break",
            "Afternoon: Check-in with mood and emotions",
            "Evening: Journal or reflection",
            "Before bed: Relaxation technique",
        ]

        toolkit["professional_help"] = [
            "Find a therapist who specializes in your concerns",
            "Join a support group for shared experiences",
            "Consider crisis resources if needed",
        ]

        return toolkit
