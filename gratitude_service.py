"""
Service layer for gratitude tracking.

Manages individual gratitude entries plus per-user streak bookkeeping
(current streak, longest streak, total entries). Gratitude is treated
as a lightweight, frequent practice — separate from full journal entries.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Iterable, List, Dict, Optional

from database import SessionLocal
from journal_models import GratitudeEntry, GratitudeStreak


GRATITUDE_CATEGORIES = [
    "people",
    "experiences",
    "self",
    "body",
    "work",
    "nature",
    "creativity",
    "small_joys",
    "growth",
    "comfort",
    "other",
]


@dataclass
class StreakSummary:
    current_streak: int
    longest_streak: int
    total_entries: int
    last_entry_date: Optional[str]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def add_gratitude(
    user_id: int,
    content: str,
    category: Optional[str] = None,
    intensity: float = 3.0,
    related_person: Optional[str] = None,
    related_event: Optional[str] = None,
) -> Dict[str, object]:
    """Save a gratitude entry and update the user's streak."""
    if not content or not content.strip():
        raise ValueError("Gratitude content cannot be empty.")
    if category and category not in GRATITUDE_CATEGORIES:
        category = "other"
    intensity = max(1.0, min(5.0, float(intensity)))

    db = SessionLocal()
    try:
        entry = GratitudeEntry(
            user_id=user_id,
            content=content.strip()[:1000],
            category=category,
            intensity=intensity,
            related_person=(related_person or None),
            related_event=(related_event or None),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        _update_streak(db, user_id=user_id, entry_date=entry.created_at)
        db.commit()

        return _serialize(entry)
    finally:
        db.close()


def add_gratitude_batch(user_id: int, items: Iterable[str]) -> List[Dict[str, object]]:
    """Quick path: add several short gratitudes at once (one per line)."""
    results: List[Dict[str, object]] = []
    for raw in items:
        text = (raw or "").strip()
        if not text:
            continue
        results.append(add_gratitude(user_id=user_id, content=text))
    return results


def list_gratitude(
    user_id: int,
    limit: int = 50,
    days: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(GratitudeEntry).filter(GratitudeEntry.user_id == user_id)
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            q = q.filter(GratitudeEntry.created_at >= cutoff)
        if category:
            q = q.filter(GratitudeEntry.category == category)
        rows = q.order_by(GratitudeEntry.created_at.desc()).limit(limit).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


def get_gratitude(user_id: int, entry_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.id == entry_id, GratitudeEntry.user_id == user_id)
            .first()
        )
        return _serialize(row) if row else None
    finally:
        db.close()


def delete_gratitude(user_id: int, entry_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.id == entry_id, GratitudeEntry.user_id == user_id)
            .first()
        )
        if not row:
            return False
        db.delete(row)
        db.commit()
        # Recompute streak after deletion in case it removed the latest day.
        _recompute_streak(db, user_id)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------

def get_streak(user_id: int) -> StreakSummary:
    db = SessionLocal()
    try:
        row = db.query(GratitudeStreak).filter(GratitudeStreak.user_id == user_id).first()
        if not row:
            return StreakSummary(0, 0, 0, None)
        return StreakSummary(
            current_streak=row.current_streak,
            longest_streak=row.longest_streak,
            total_entries=row.total_entries,
            last_entry_date=row.last_entry_date.isoformat() if row.last_entry_date else None,
        )
    finally:
        db.close()


def _update_streak(db, user_id: int, entry_date: datetime) -> None:
    row = db.query(GratitudeStreak).filter(GratitudeStreak.user_id == user_id).first()
    today = entry_date.date()
    if not row:
        row = GratitudeStreak(
            user_id=user_id,
            current_streak=1,
            longest_streak=1,
            last_entry_date=entry_date,
            total_entries=1,
        )
        db.add(row)
        return

    row.total_entries = (row.total_entries or 0) + 1

    last = row.last_entry_date.date() if row.last_entry_date else None
    if last is None:
        row.current_streak = 1
    elif last == today:
        # Same day, streak unchanged.
        pass
    elif (today - last).days == 1:
        row.current_streak = (row.current_streak or 0) + 1
    else:
        row.current_streak = 1

    row.longest_streak = max(row.longest_streak or 0, row.current_streak or 0)
    row.last_entry_date = entry_date
    row.updated_at = datetime.now(timezone.utc)


def _recompute_streak(db, user_id: int) -> None:
    """Rebuild streak rows from scratch after a deletion."""
    rows = (
        db.query(GratitudeEntry)
        .filter(GratitudeEntry.user_id == user_id)
        .order_by(GratitudeEntry.created_at.asc())
        .all()
    )
    streak = db.query(GratitudeStreak).filter(GratitudeStreak.user_id == user_id).first()
    if not rows:
        if streak:
            db.delete(streak)
        return

    if not streak:
        streak = GratitudeStreak(user_id=user_id)
        db.add(streak)
        db.flush()

    streak.total_entries = len(rows)
    streak.last_entry_date = rows[-1].created_at

    distinct_dates = sorted({r.created_at.date() for r in rows})
    longest = current = 1
    for prev, curr in zip(distinct_dates, distinct_dates[1:]):
        if (curr - prev).days == 1:
            current += 1
            longest = max(longest, current)
        elif (curr - prev).days == 0:
            continue
        else:
            current = 1

    today = datetime.now(timezone.utc).date()
    last = distinct_dates[-1]
    if (today - last).days > 1:
        current = 0
    streak.current_streak = current
    streak.longest_streak = max(streak.longest_streak or 0, longest)
    streak.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def gratitude_breakdown(user_id: int, days: int = 30) -> Dict[str, object]:
    """How are the user's gratitudes distributed by category, people, days?"""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.user_id == user_id, GratitudeEntry.created_at >= cutoff)
            .all()
        )
        category_counts: Counter = Counter()
        people_counts: Counter = Counter()
        per_day: Dict[str, int] = {}
        intensity_total = 0.0
        for r in rows:
            category_counts[r.category or "other"] += 1
            if r.related_person:
                people_counts[r.related_person.strip()] += 1
            day = r.created_at.date().isoformat()
            per_day[day] = per_day.get(day, 0) + 1
            intensity_total += float(r.intensity or 0)
        return {
            "window_days": days,
            "total": len(rows),
            "avg_intensity": round(intensity_total / len(rows), 2) if rows else 0,
            "categories": dict(category_counts.most_common()),
            "top_people": dict(people_counts.most_common(5)),
            "per_day": per_day,
        }
    finally:
        db.close()


def suggest_categories_for_user(user_id: int) -> List[str]:
    """If a user has been heavy on one category, gently suggest under-used ones."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        rows = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.user_id == user_id, GratitudeEntry.created_at >= cutoff)
            .all()
        )
        used: Counter = Counter()
        for r in rows:
            used[r.category or "other"] += 1
        ranked = sorted(
            GRATITUDE_CATEGORIES,
            key=lambda c: used.get(c, 0),
        )
        return [c for c in ranked if c != "other"][:5]
    finally:
        db.close()


def recent_gratitude_summary(user_id: int, limit: int = 7) -> List[str]:
    """Latest gratitudes as plain strings (used in reflections)."""
    db = SessionLocal()
    try:
        rows = (
            db.query(GratitudeEntry)
            .filter(GratitudeEntry.user_id == user_id)
            .order_by(GratitudeEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [r.content for r in rows]
    finally:
        db.close()


def gratitude_completion_today(user_id: int) -> bool:
    """Did the user write a gratitude entry today?"""
    db = SessionLocal()
    try:
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
        row = (
            db.query(GratitudeEntry)
            .filter(
                GratitudeEntry.user_id == user_id,
                GratitudeEntry.created_at >= today_start,
            )
            .first()
        )
        return row is not None
    finally:
        db.close()


def _serialize(row: Optional[GratitudeEntry]) -> Optional[Dict[str, object]]:
    if not row:
        return None
    return {
        "id": row.id,
        "content": row.content,
        "category": row.category,
        "intensity": row.intensity,
        "related_person": row.related_person,
        "related_event": row.related_event,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
