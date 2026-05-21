"""
Analytics across the journal, gratitude, and mindfulness data.

Lower-level summaries live in each service module; this file provides
cross-cutting views: combined wellbeing scores, calendar heatmaps,
correlation between practice and mood, and exportable digest payloads.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple

from database import SessionLocal
from journal_models import (
    JournalEntry,
    GratitudeEntry,
    MindfulnessSession,
)


@dataclass
class WellbeingScore:
    score: float           # 0-100
    components: Dict[str, float]
    label: str
    window_days: int


# ---------------------------------------------------------------------------
# Wellbeing score
# ---------------------------------------------------------------------------

def compute_wellbeing(user_id: int, days: int = 14) -> WellbeingScore:
    """A 0-100 composite of journaling consistency, gratitude practice,
    mindfulness time, and average mood. Coarse on purpose — meant to be
    motivating, not diagnostic.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        entries = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= cutoff,
                JournalEntry.is_archived.is_(False),
            )
            .all()
        )
        gratitudes = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.user_id == user_id, GratitudeEntry.created_at >= cutoff)
            .all()
        )
        sessions = (
            db.query(MindfulnessSession)
            .filter(MindfulnessSession.user_id == user_id, MindfulnessSession.started_at >= cutoff)
            .all()
        )

        journal_days = len({e.created_at.date() for e in entries})
        gratitude_days = len({g.created_at.date() for g in gratitudes})
        practice_minutes = sum((s.duration_seconds or 0) for s in sessions) / 60.0
        mood_scores = [e.mood_score for e in entries if e.mood_score is not None]
        avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else None

        target_days = max(days, 1)
        journal_component = min(journal_days / (target_days * 0.5), 1.0) * 30
        gratitude_component = min(gratitude_days / (target_days * 0.5), 1.0) * 25
        practice_component = min(practice_minutes / (target_days * 5.0), 1.0) * 25
        if avg_mood is None:
            mood_component = 10.0  # neutral if no signal
        else:
            mood_component = max(0.0, min(20.0, (avg_mood / 10.0) * 20))

        total = journal_component + gratitude_component + practice_component + mood_component
        total = max(0.0, min(100.0, total))

        if total >= 80:
            label = "thriving"
        elif total >= 60:
            label = "steady"
        elif total >= 40:
            label = "uneven"
        elif total >= 20:
            label = "running_low"
        else:
            label = "depleted"

        return WellbeingScore(
            score=round(total, 1),
            components={
                "journaling": round(journal_component, 1),
                "gratitude": round(gratitude_component, 1),
                "mindfulness": round(practice_component, 1),
                "mood": round(mood_component, 1),
            },
            label=label,
            window_days=days,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

def activity_heatmap(user_id: int, days: int = 60) -> Dict[str, Dict[str, int]]:
    """Return per-day counts for each activity type, suitable for a heatmap."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        per_day_journal: Dict[str, int] = defaultdict(int)
        for e in db.query(JournalEntry).filter(
            JournalEntry.user_id == user_id,
            JournalEntry.created_at >= cutoff,
        ).all():
            per_day_journal[e.created_at.date().isoformat()] += 1

        per_day_gratitude: Dict[str, int] = defaultdict(int)
        for g in db.query(GratitudeEntry).filter(
            GratitudeEntry.user_id == user_id,
            GratitudeEntry.created_at >= cutoff,
        ).all():
            per_day_gratitude[g.created_at.date().isoformat()] += 1

        per_day_sessions: Dict[str, int] = defaultdict(int)
        for s in db.query(MindfulnessSession).filter(
            MindfulnessSession.user_id == user_id,
            MindfulnessSession.started_at >= cutoff,
        ).all():
            per_day_sessions[s.started_at.date().isoformat()] += 1

        return {
            "journal": dict(per_day_journal),
            "gratitude": dict(per_day_gratitude),
            "mindfulness": dict(per_day_sessions),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------

def mood_practice_correlation(user_id: int, days: int = 60) -> Dict[str, object]:
    """Does practicing mindfulness on a given day correlate with mood
    on that day's journal entries? Simple Pearson on aggregated daily values.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        entries = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= cutoff,
                JournalEntry.mood_score.isnot(None),
            )
            .all()
        )
        sessions = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.user_id == user_id,
                MindfulnessSession.started_at >= cutoff,
            )
            .all()
        )

        mood_by_day: Dict[str, List[float]] = defaultdict(list)
        for e in entries:
            mood_by_day[e.created_at.date().isoformat()].append(float(e.mood_score))

        minutes_by_day: Dict[str, float] = defaultdict(float)
        for s in sessions:
            minutes_by_day[s.started_at.date().isoformat()] += (s.duration_seconds or 0) / 60.0

        # Align days
        days_set = set(mood_by_day.keys()) | set(minutes_by_day.keys())
        if len(days_set) < 3:
            return {
                "samples": len(days_set),
                "pearson_r": None,
                "interpretation": "Not enough data points yet.",
            }

        xs = []
        ys = []
        for d in sorted(days_set):
            xs.append(minutes_by_day.get(d, 0.0))
            avg_mood = (
                sum(mood_by_day[d]) / len(mood_by_day[d])
                if d in mood_by_day else None
            )
            if avg_mood is None:
                continue
            ys.append(avg_mood)
            xs[-1] = minutes_by_day.get(d, 0.0)

        if len(xs) != len(ys) or len(xs) < 3:
            return {
                "samples": len(xs),
                "pearson_r": None,
                "interpretation": "Not enough mood-rated days to correlate.",
            }

        r = _pearson(xs, ys)
        interp = _interpret_correlation(r)
        return {
            "samples": len(xs),
            "pearson_r": round(r, 3),
            "interpretation": interp,
        }
    finally:
        db.close()


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    denom_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return num / (denom_x * denom_y)


def _interpret_correlation(r: float) -> str:
    abs_r = abs(r)
    if abs_r < 0.1:
        return "Practice doesn't yet show a clear connection to mood — that's okay; it can take weeks."
    if r > 0.4:
        return "On days you practice more, mood tends to be higher. Worth doubling down."
    if r > 0.1:
        return "There's a small positive nudge from practice to mood."
    if r < -0.4:
        return "Curious — more practice on hard days suggests you turn to it for support, not as a cause of low mood."
    if r < -0.1:
        return "A slight inverse pattern — likely because you reach for practice when you most need it."
    return "Mixed pattern; keep observing."


# ---------------------------------------------------------------------------
# Calendar digest
# ---------------------------------------------------------------------------

def daily_digest(user_id: int, target_date: Optional[date] = None) -> Dict[str, object]:
    """Combined view for a single day: entries, gratitudes, sessions, mood."""
    if target_date is None:
        target_date = date.today()
    start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    db = SessionLocal()
    try:
        entries = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= start,
                JournalEntry.created_at < end,
            )
            .order_by(JournalEntry.created_at.asc())
            .all()
        )
        gratitudes = (
            db.query(GratitudeEntry)
            .filter(
                GratitudeEntry.user_id == user_id,
                GratitudeEntry.created_at >= start,
                GratitudeEntry.created_at < end,
            )
            .order_by(GratitudeEntry.created_at.asc())
            .all()
        )
        sessions = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.user_id == user_id,
                MindfulnessSession.started_at >= start,
                MindfulnessSession.started_at < end,
            )
            .order_by(MindfulnessSession.started_at.asc())
            .all()
        )

        return {
            "date": target_date.isoformat(),
            "entries": [
                {
                    "id": e.id,
                    "title": e.title,
                    "excerpt": (e.body or "")[:160],
                    "mood_score": e.mood_score,
                }
                for e in entries
            ],
            "gratitudes": [
                {"id": g.id, "content": g.content, "category": g.category}
                for g in gratitudes
            ],
            "sessions": [
                {
                    "id": s.id,
                    "technique": s.technique,
                    "duration_minutes": round((s.duration_seconds or 0) / 60.0, 1),
                }
                for s in sessions
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Weekly digest (for export, email, etc.)
# ---------------------------------------------------------------------------

def weekly_digest(user_id: int) -> Dict[str, object]:
    db = SessionLocal()
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)

        entry_count = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= start,
                JournalEntry.is_archived.is_(False),
            )
            .count()
        )
        gratitude_count = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.user_id == user_id, GratitudeEntry.created_at >= start)
            .count()
        )
        sessions = (
            db.query(MindfulnessSession)
            .filter(MindfulnessSession.user_id == user_id, MindfulnessSession.started_at >= start)
            .all()
        )
        practice_minutes = sum((s.duration_seconds or 0) for s in sessions) / 60.0

        wellbeing = compute_wellbeing(user_id, days=7)
        heatmap = activity_heatmap(user_id, days=7)
        correlation = mood_practice_correlation(user_id, days=21)

        return {
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "entry_count": entry_count,
            "gratitude_count": gratitude_count,
            "session_count": len(sessions),
            "practice_minutes": round(practice_minutes, 1),
            "wellbeing": asdict(wellbeing),
            "heatmap": heatmap,
            "correlation": correlation,
        }
    finally:
        db.close()


def writing_consistency(user_id: int, days: int = 30) -> Dict[str, object]:
    """How consistent is the user's writing cadence?"""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= cutoff,
                JournalEntry.is_archived.is_(False),
            )
            .all()
        )
        if not rows:
            return {
                "days": days,
                "active_days": 0,
                "consistency_ratio": 0.0,
                "average_gap_days": None,
            }
        date_set = sorted({r.created_at.date() for r in rows})
        gaps: List[int] = []
        for prev, curr in zip(date_set, date_set[1:]):
            gaps.append((curr - prev).days)
        average_gap = round(sum(gaps) / len(gaps), 2) if gaps else 0.0
        return {
            "days": days,
            "active_days": len(date_set),
            "consistency_ratio": round(len(date_set) / max(days, 1), 3),
            "average_gap_days": average_gap,
        }
    finally:
        db.close()
