"""
Service layer for mindfulness sessions and techniques.

Sessions track a user's actual practice (technique, duration, pre/post mood);
techniques are the library the app guides them through. Provides session
recording, recommendation, and streak/effectiveness analysis.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from database import SessionLocal
from journal_models import MindfulnessSession, MindfulnessTechnique


@dataclass
class SessionSummary:
    total_sessions: int
    total_minutes: float
    average_duration: float
    completion_rate: float
    favorite_technique: Optional[str]
    average_calm: Optional[float]
    average_mood_delta: Optional[float]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def record_session(
    user_id: int,
    technique: str,
    duration_seconds: int,
    pre_mood: Optional[float] = None,
    post_mood: Optional[float] = None,
    perceived_calm: Optional[float] = None,
    notes: Optional[str] = None,
    interrupted: bool = False,
    background_sound: Optional[str] = None,
    completed: bool = True,
) -> Dict[str, object]:
    """Record a completed (or interrupted) mindfulness session."""
    if not technique:
        raise ValueError("Technique is required.")
    if duration_seconds < 0:
        raise ValueError("Duration must be non-negative.")

    db = SessionLocal()
    try:
        started = datetime.now(timezone.utc) - timedelta(seconds=duration_seconds)
        session = MindfulnessSession(
            user_id=user_id,
            technique=technique,
            duration_seconds=int(duration_seconds),
            completed=bool(completed) and not interrupted,
            pre_mood=pre_mood,
            post_mood=post_mood,
            perceived_calm=perceived_calm,
            notes=(notes or "")[:2000] or None,
            interrupted=bool(interrupted),
            background_sound=background_sound,
            started_at=started,
            ended_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return _serialize_session(session)
    finally:
        db.close()


def list_sessions(
    user_id: int,
    limit: int = 50,
    days: Optional[int] = None,
    technique: Optional[str] = None,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(MindfulnessSession).filter(MindfulnessSession.user_id == user_id)
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            q = q.filter(MindfulnessSession.started_at >= cutoff)
        if technique:
            q = q.filter(MindfulnessSession.technique == technique)
        rows = q.order_by(MindfulnessSession.started_at.desc()).limit(limit).all()
        return [_serialize_session(r) for r in rows]
    finally:
        db.close()


def get_session(user_id: int, session_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.id == session_id,
                MindfulnessSession.user_id == user_id,
            )
            .first()
        )
        return _serialize_session(row) if row else None
    finally:
        db.close()


def delete_session(user_id: int, session_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.id == session_id,
                MindfulnessSession.user_id == user_id,
            )
            .first()
        )
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def update_session_feedback(
    user_id: int,
    session_id: int,
    post_mood: Optional[float] = None,
    perceived_calm: Optional[float] = None,
    notes: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.id == session_id,
                MindfulnessSession.user_id == user_id,
            )
            .first()
        )
        if not row:
            return None
        if post_mood is not None:
            row.post_mood = post_mood
        if perceived_calm is not None:
            row.perceived_calm = perceived_calm
        if notes is not None:
            row.notes = notes[:2000] or None
        db.commit()
        db.refresh(row)
        return _serialize_session(row)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Technique library
# ---------------------------------------------------------------------------

def list_techniques(category: Optional[str] = None) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(MindfulnessTechnique)
        if category:
            q = q.filter(MindfulnessTechnique.category == category)
        return [_serialize_technique(t) for t in q.all()]
    finally:
        db.close()


def get_technique(key: str) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = db.query(MindfulnessTechnique).filter(MindfulnessTechnique.key == key).first()
        return _serialize_technique(row) if row else None
    finally:
        db.close()


def recommend_technique(
    user_id: int,
    mood_score: Optional[float] = None,
    available_minutes: int = 10,
    avoid_recent: bool = True,
) -> Optional[Dict[str, object]]:
    """Pick a technique based on current mood and the user's recent history."""
    db = SessionLocal()
    try:
        techniques = db.query(MindfulnessTechnique).all()
        if not techniques:
            return None

        preferred_categories = _category_for_mood(mood_score)

        # Filter by available time first.
        candidates = [t for t in techniques if (t.typical_duration or 0) <= available_minutes + 2]
        if not candidates:
            candidates = techniques

        if preferred_categories:
            preferred = [t for t in candidates if t.category in preferred_categories]
            if preferred:
                candidates = preferred

        if avoid_recent:
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=2)
            recent = (
                db.query(MindfulnessSession)
                .filter(
                    MindfulnessSession.user_id == user_id,
                    MindfulnessSession.started_at >= recent_cutoff,
                )
                .all()
            )
            recent_techniques = {s.technique for s in recent}
            fresh = [t for t in candidates if t.key not in recent_techniques]
            if fresh:
                candidates = fresh

        if not candidates:
            return None
        candidates.sort(key=lambda t: t.typical_duration or 0)
        return _serialize_technique(candidates[0])
    finally:
        db.close()


def _category_for_mood(mood_score: Optional[float]) -> List[str]:
    if mood_score is None:
        return ["breathing", "awareness", "grounding"]
    if mood_score < 3.5:
        return ["compassion", "grounding"]
    if mood_score < 5.5:
        return ["breathing", "grounding", "compassion"]
    if mood_score < 7.5:
        return ["awareness", "breathing", "joy"]
    return ["joy", "awareness", "movement"]


# ---------------------------------------------------------------------------
# Aggregates / streaks
# ---------------------------------------------------------------------------

def practice_summary(user_id: int, days: int = 30) -> SessionSummary:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.user_id == user_id,
                MindfulnessSession.started_at >= cutoff,
            )
            .all()
        )
        if not rows:
            return SessionSummary(0, 0.0, 0.0, 0.0, None, None, None)

        total_seconds = sum(r.duration_seconds or 0 for r in rows)
        completed = [r for r in rows if r.completed and not r.interrupted]
        completion_rate = round(len(completed) / len(rows), 3)
        average_duration = round((total_seconds / len(rows)) / 60.0, 2)

        technique_counts: Counter = Counter(r.technique for r in rows)
        favorite = technique_counts.most_common(1)[0][0] if technique_counts else None

        calm_scores = [r.perceived_calm for r in rows if r.perceived_calm is not None]
        avg_calm = round(sum(calm_scores) / len(calm_scores), 2) if calm_scores else None

        mood_deltas = [
            (r.post_mood - r.pre_mood)
            for r in rows
            if r.pre_mood is not None and r.post_mood is not None
        ]
        avg_delta = round(sum(mood_deltas) / len(mood_deltas), 2) if mood_deltas else None

        return SessionSummary(
            total_sessions=len(rows),
            total_minutes=round(total_seconds / 60.0, 1),
            average_duration=average_duration,
            completion_rate=completion_rate,
            favorite_technique=favorite,
            average_calm=avg_calm,
            average_mood_delta=avg_delta,
        )
    finally:
        db.close()


def session_streak(user_id: int) -> Dict[str, int]:
    """Current and longest consecutive-day streaks of practice."""
    db = SessionLocal()
    try:
        rows = (
            db.query(MindfulnessSession)
            .filter(MindfulnessSession.user_id == user_id)
            .order_by(MindfulnessSession.started_at.asc())
            .all()
        )
        if not rows:
            return {"current_streak": 0, "longest_streak": 0, "total_days": 0}

        days = sorted({r.started_at.date() for r in rows})
        longest = current = 1
        for prev, curr in zip(days, days[1:]):
            if (curr - prev).days == 1:
                current += 1
                longest = max(longest, current)
            elif (curr - prev).days == 0:
                continue
            else:
                current = 1

        today = datetime.now(timezone.utc).date()
        if (today - days[-1]).days > 1:
            current_streak = 0
        else:
            # Walk backward from the last day to compute current streak
            current_streak = 1
            for prev, curr in zip(days[::-1][1:], days[::-1]):
                if (curr - prev).days == 1:
                    current_streak += 1
                else:
                    break

        return {
            "current_streak": current_streak,
            "longest_streak": longest,
            "total_days": len(days),
        }
    finally:
        db.close()


def technique_effectiveness(user_id: int, min_samples: int = 2) -> List[Dict[str, object]]:
    """Average post-pre mood delta per technique, with sample count."""
    db = SessionLocal()
    try:
        rows = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.user_id == user_id,
                MindfulnessSession.pre_mood.isnot(None),
                MindfulnessSession.post_mood.isnot(None),
            )
            .all()
        )
        grouped: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            grouped[r.technique].append((r.post_mood or 0) - (r.pre_mood or 0))

        out: List[Dict[str, object]] = []
        for technique, deltas in grouped.items():
            if len(deltas) < min_samples:
                continue
            out.append(
                {
                    "technique": technique,
                    "samples": len(deltas),
                    "avg_mood_delta": round(sum(deltas) / len(deltas), 2),
                    "best_single": round(max(deltas), 2),
                }
            )
        out.sort(key=lambda r: r["avg_mood_delta"], reverse=True)
        return out
    finally:
        db.close()


def best_time_of_day(user_id: int) -> Optional[str]:
    """Which time bucket does the user practice in most often?"""
    db = SessionLocal()
    try:
        rows = (
            db.query(MindfulnessSession)
            .filter(MindfulnessSession.user_id == user_id)
            .all()
        )
        if not rows:
            return None
        buckets = Counter()
        for r in rows:
            hour = r.started_at.hour
            if hour < 6:
                buckets["late_night"] += 1
            elif hour < 12:
                buckets["morning"] += 1
            elif hour < 17:
                buckets["afternoon"] += 1
            elif hour < 22:
                buckets["evening"] += 1
            else:
                buckets["late_night"] += 1
        return buckets.most_common(1)[0][0]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_session(row: MindfulnessSession) -> Dict[str, object]:
    return {
        "id": row.id,
        "technique": row.technique,
        "duration_seconds": row.duration_seconds,
        "duration_minutes": round((row.duration_seconds or 0) / 60.0, 2),
        "completed": row.completed,
        "interrupted": row.interrupted,
        "pre_mood": row.pre_mood,
        "post_mood": row.post_mood,
        "perceived_calm": row.perceived_calm,
        "notes": row.notes,
        "background_sound": row.background_sound,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
    }


def _serialize_technique(row: Optional[MindfulnessTechnique]) -> Optional[Dict[str, object]]:
    if not row:
        return None
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "guided_script": row.guided_script,
        "typical_duration": row.typical_duration,
        "category": row.category,
        "difficulty": row.difficulty,
        "benefits": row.benefits,
    }
