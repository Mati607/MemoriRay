"""
Goal tracking system for mental health improvement.
Allows users to set, track, and measure progress on wellness goals.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text
from database import Base, SessionLocal


class WellnessGoal(Base):
    """Model for wellness goals."""
    __tablename__ = "wellness_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    goal_type = Column(String(100), nullable=False)
    target_value = Column(Float, nullable=True)
    current_value = Column(Float, default=0.0)
    unit = Column(String(50), nullable=True)
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    target_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GoalProgress(Base):
    """Track progress updates on goals."""
    __tablename__ = "goal_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    goal_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    value = Column(Float, nullable=False)
    notes = Column(String(500), nullable=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GoalTracker:
    """Manage wellness goals and track progress."""

    GOAL_TYPES = {
        "mood_improvement": {
            "name": "Mood Improvement",
            "description": "Increase average mood score",
            "unit": "points",
            "typical_target": 7.0,
        },
        "exercise_frequency": {
            "name": "Exercise Frequency",
            "description": "Complete exercises regularly",
            "unit": "times per week",
            "typical_target": 3.0,
        },
        "meditation_streak": {
            "name": "Meditation Streak",
            "description": "Consecutive days of meditation",
            "unit": "days",
            "typical_target": 30.0,
        },
        "mood_stability": {
            "name": "Mood Stability",
            "description": "Reduce mood volatility",
            "unit": "volatility score",
            "typical_target": 1.5,
        },
        "sleep_improvement": {
            "name": "Sleep Improvement",
            "description": "Increase average sleep hours",
            "unit": "hours",
            "typical_target": 8.0,
        },
        "stress_reduction": {
            "name": "Stress Reduction",
            "description": "Lower stress levels",
            "unit": "score (1-10)",
            "typical_target": 4.0,
        },
        "social_connection": {
            "name": "Social Connection",
            "description": "Maintain regular social contact",
            "unit": "interactions per week",
            "typical_target": 3.0,
        },
        "therapy_attendance": {
            "name": "Therapy Attendance",
            "description": "Attend therapy sessions",
            "unit": "sessions",
            "typical_target": 4.0,
        },
        "self_care": {
            "name": "Self-Care Activities",
            "description": "Regular self-care practice",
            "unit": "activities per week",
            "typical_target": 5.0,
        },
        "journaling": {
            "name": "Journaling Practice",
            "description": "Regular journal entries",
            "unit": "entries per week",
            "typical_target": 5.0,
        },
    }

    @staticmethod
    def create_goal(
        user_id: int,
        title: str,
        goal_type: str,
        target_value: float,
        target_date: datetime,
        description: str = None,
        unit: str = None,
    ) -> int:
        """Create a new wellness goal."""
        db = SessionLocal()
        try:
            goal = WellnessGoal(
                user_id=user_id,
                title=title,
                goal_type=goal_type,
                target_value=target_value,
                unit=unit or GoalTracker.GOAL_TYPES.get(goal_type, {}).get("unit"),
                target_date=target_date,
                description=description,
            )
            db.add(goal)
            db.commit()
            db.refresh(goal)
            return goal.id
        finally:
            db.close()

    @staticmethod
    def record_progress(
        goal_id: int,
        user_id: int,
        value: float,
        notes: str = None,
    ) -> None:
        """Record progress on a goal."""
        db = SessionLocal()
        try:
            progress = GoalProgress(
                goal_id=goal_id,
                user_id=user_id,
                value=value,
                notes=notes,
            )
            db.add(progress)

            goal = db.query(WellnessGoal).filter(WellnessGoal.id == goal_id).first()
            if goal:
                goal.current_value = value
                goal.updated_at = datetime.now(timezone.utc)

                if value >= goal.target_value:
                    goal.is_completed = True

            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_user_goals(user_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all goals for a user."""
        db = SessionLocal()
        try:
            query = db.query(WellnessGoal).filter(WellnessGoal.user_id == user_id)

            if not include_completed:
                query = query.filter(WellnessGoal.is_completed == False)

            goals = query.order_by(WellnessGoal.created_at.desc()).all()

            return [
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "goal_type": g.goal_type,
                    "target_value": g.target_value,
                    "current_value": g.current_value,
                    "unit": g.unit,
                    "progress_percent": (g.current_value / g.target_value * 100)
                    if g.target_value else 0,
                    "is_completed": g.is_completed,
                    "start_date": g.start_date.isoformat(),
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                    "days_remaining": (
                        (g.target_date - datetime.now(timezone.utc)).days
                        if g.target_date
                        else None
                    ),
                }
                for g in goals
            ]
        finally:
            db.close()

    @staticmethod
    def get_goal_progress(goal_id: int, limit: int = 20) -> List[Dict]:
        """Get progress history for a goal."""
        db = SessionLocal()
        try:
            progress_entries = (
                db.query(GoalProgress)
                .filter(GoalProgress.goal_id == goal_id)
                .order_by(GoalProgress.recorded_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": p.id,
                    "value": p.value,
                    "notes": p.notes,
                    "recorded_at": p.recorded_at.isoformat(),
                }
                for p in progress_entries
            ]
        finally:
            db.close()

    @staticmethod
    def complete_goal(goal_id: int) -> None:
        """Mark a goal as completed."""
        db = SessionLocal()
        try:
            goal = db.query(WellnessGoal).filter(WellnessGoal.id == goal_id).first()
            if goal:
                goal.is_completed = True
                goal.updated_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

    @staticmethod
    def delete_goal(goal_id: int) -> None:
        """Delete a goal."""
        db = SessionLocal()
        try:
            db.query(WellnessGoal).filter(WellnessGoal.id == goal_id).delete()
            db.query(GoalProgress).filter(GoalProgress.goal_id == goal_id).delete()
            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_goal_completion_rate(user_id: int) -> float:
        """Calculate percentage of completed goals."""
        db = SessionLocal()
        try:
            total = db.query(WellnessGoal).filter(WellnessGoal.user_id == user_id).count()
            completed = (
                db.query(WellnessGoal)
                .filter(WellnessGoal.user_id == user_id, WellnessGoal.is_completed == True)
                .count()
            )
            return (completed / total * 100) if total > 0 else 0
        finally:
            db.close()

    @staticmethod
    def get_upcoming_goals(user_id: int, days: int = 30) -> List[Dict]:
        """Get goals with upcoming deadlines."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            future = now + timedelta(days=days)

            goals = (
                db.query(WellnessGoal)
                .filter(
                    WellnessGoal.user_id == user_id,
                    WellnessGoal.is_completed == False,
                    WellnessGoal.target_date >= now,
                    WellnessGoal.target_date <= future,
                )
                .order_by(WellnessGoal.target_date.asc())
                .all()
            )

            return [
                {
                    "id": g.id,
                    "title": g.title,
                    "target_date": g.target_date.isoformat(),
                    "days_remaining": (g.target_date - now).days,
                    "current_value": g.current_value,
                    "target_value": g.target_value,
                    "progress_percent": (g.current_value / g.target_value * 100)
                    if g.target_value else 0,
                }
                for g in goals
            ]
        finally:
            db.close()

    @staticmethod
    def suggest_goals_for_user(user_id: int) -> List[Dict]:
        """Suggest goals based on user's data."""
        from analytics_service import MoodAnalytics

        suggestions = []

        stats = MoodAnalytics.get_mood_statistics(user_id, days=30)
        if stats.get("avg_mood") and stats["avg_mood"] < 6:
            suggestions.append({
                "goal_type": "mood_improvement",
                "title": "Improve Daily Mood",
                "description": "Increase your average mood from 5.2 to 7.0 over 8 weeks",
                "target_value": 7.0,
                "reason": "Your current mood could benefit from targeted improvement",
            })

        if stats.get("volatility") and stats["volatility"] > 2.5:
            suggestions.append({
                "goal_type": "mood_stability",
                "title": "Stabilize Your Mood",
                "description": "Reduce mood volatility through regular exercises",
                "target_value": 1.5,
                "reason": "Mood fluctuations are high; stability exercises can help",
            })

        patterns = MoodAnalytics.identify_mood_patterns(user_id, days=30)
        if len(patterns.get("dominant_emotions", [])) > 0:
            emotion = patterns["dominant_emotions"][0]
            suggestions.append({
                "goal_type": "exercise_frequency",
                "title": f"Regular {emotion.title()} Management",
                "description": f"Practice exercises {emotion.lower()} management 3x per week",
                "target_value": 3.0,
                "reason": f"{emotion.title()} is frequent in your tracking",
            })

        suggestions.append({
            "goal_type": "journaling",
            "title": "Daily Journaling Practice",
            "description": "Write in your mood journal 5 times per week",
            "target_value": 5.0,
            "reason": "Regular journaling improves self-awareness and mood",
        })

        return suggestions[:4]


class MilestoneTracker:
    """Track achievements and milestones."""

    MILESTONES = {
        "first_entry": {
            "name": "First Step",
            "description": "Recorded your first mood entry",
            "icon": "🎯",
        },
        "week_of_entries": {
            "name": "Week Warrior",
            "description": "Tracked mood for a full week",
            "icon": "📅",
        },
        "first_exercise": {
            "name": "Taking Action",
            "description": "Completed your first exercise",
            "icon": "🏃",
        },
        "5_exercises": {
            "name": "Consistent Effort",
            "description": "Completed 5 exercises",
            "icon": "⭐",
        },
        "mood_improvement": {
            "name": "Progress",
            "description": "Improved your mood by 2+ points",
            "icon": "📈",
        },
        "week_stability": {
            "name": "Steady Ground",
            "description": "Maintained stable mood for a week",
            "icon": "🌳",
        },
        "month_consistency": {
            "name": "Dedicated",
            "description": "Tracked consistently for a month",
            "icon": "🏆",
        },
    }

    @staticmethod
    def check_milestones(user_id: int) -> List[Dict]:
        """Check which milestones have been achieved."""
        from analytics_service import MoodAnalytics
        from database import SessionLocal, MoodEntry, TherapyExercise

        db = SessionLocal()
        achieved = []

        try:
            mood_entries = db.query(MoodEntry).filter(MoodEntry.user_id == user_id).all()
            exercises = db.query(TherapyExercise).filter(TherapyExercise.user_id == user_id).all()

            if mood_entries:
                achieved.append("first_entry")

            if len(mood_entries) >= 7:
                achieved.append("week_of_entries")

            if exercises:
                achieved.append("first_exercise")

            if len(exercises) >= 5:
                achieved.append("5_exercises")

            if len(mood_entries) >= 30:
                achieved.append("month_consistency")

            mood_scores = [e.mood_score for e in mood_entries if e.mood_score]
            if len(mood_scores) >= 2:
                first_avg = sum(mood_scores[:len(mood_scores)//2]) / (len(mood_scores)//2)
                last_avg = sum(mood_scores[len(mood_scores)//2:]) / (len(mood_scores) - len(mood_scores)//2)
                if last_avg - first_avg >= 2:
                    achieved.append("mood_improvement")

            return [
                {
                    "id": milestone_id,
                    "name": MilestoneTracker.MILESTONES[milestone_id]["name"],
                    "description": MilestoneTracker.MILESTONES[milestone_id]["description"],
                    "icon": MilestoneTracker.MILESTONES[milestone_id]["icon"],
                }
                for milestone_id in achieved
            ]
        finally:
            db.close()
