"""
Behavior event tracker.

Generic event log for sleep, exercise, hydration, meals, screen time,
caffeine, alcohol, outdoor time, social time, reading, creative work,
stretching, and step counts. Each event type has a sensible "good range"
defined in BEHAVIOR_EVENT_TYPES that drives the wellness scoring.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional

from database import SessionLocal
from habit_models import BehaviorEvent, BEHAVIOR_EVENT_TYPES


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------

def log_event(
    user_id: int,
    event_type: str,
    occurred_at: Optional[datetime] = None,
    value: Optional[float] = None,
    value_unit: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    quality: Optional[float] = None,
    intensity: Optional[float] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    bedtime: Optional[datetime] = None,
    wake_time: Optional[datetime] = None,
    awakenings: Optional[int] = None,
    dream_summary: Optional[str] = None,
) -> Dict[str, object]:
    if event_type not in BEHAVIOR_EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}")
    cfg = BEHAVIOR_EVENT_TYPES[event_type]
    occurred = occurred_at or datetime.now(timezone.utc)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)

    # Derive value from bed/wake if it's a sleep event without one.
    if event_type == "sleep" and value is None and bedtime and wake_time:
        delta_hours = (wake_time - bedtime).total_seconds() / 3600.0
        value = round(delta_hours, 2)

    db = SessionLocal()
    try:
        event = BehaviorEvent(
            user_id=user_id,
            event_type=event_type,
            occurred_at=occurred,
            value=value,
            value_unit=value_unit or cfg.get("unit"),
            duration_minutes=duration_minutes,
            quality=quality,
            intensity=intensity,
            notes=(notes or "")[:1000] or None,
            tags=",".join(tags or []) or None,
            bedtime=bedtime,
            wake_time=wake_time,
            awakenings=awakenings,
            dream_summary=(dream_summary or "")[:2000] or None,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return _serialize(event)
    finally:
        db.close()


def list_events(
    user_id: int,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 200,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = db.query(BehaviorEvent).filter(
            BehaviorEvent.user_id == user_id,
            BehaviorEvent.occurred_at >= cutoff,
        )
        if event_type:
            q = q.filter(BehaviorEvent.event_type == event_type)
        rows = q.order_by(BehaviorEvent.occurred_at.desc()).limit(limit).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


def delete_event(user_id: int, event_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(BehaviorEvent)
            .filter(BehaviorEvent.id == event_id, BehaviorEvent.user_id == user_id)
            .first()
        )
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

def daily_totals(
    user_id: int, event_type: str, days: int = 30
) -> Dict[str, float]:
    """Sum of `value` per day for a given event type."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.event_type == event_type,
                BehaviorEvent.occurred_at >= cutoff,
            )
            .all()
        )
        out: Dict[str, float] = defaultdict(float)
        for r in rows:
            if r.value is None:
                continue
            out[r.occurred_at.date().isoformat()] += float(r.value)
        return dict(out)
    finally:
        db.close()


def average_by_type(user_id: int, days: int = 30) -> Dict[str, Dict[str, object]]:
    """Average value, plus in-range %, per event type over the window."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.occurred_at >= cutoff,
            )
            .all()
        )
        per_type: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            if r.value is not None:
                per_type[r.event_type].append(float(r.value))

        out: Dict[str, Dict[str, object]] = {}
        for event_type, values in per_type.items():
            if not values:
                continue
            cfg = BEHAVIOR_EVENT_TYPES.get(event_type, {})
            good_min = cfg.get("good_min")
            good_max = cfg.get("good_max")
            in_range = sum(
                1
                for v in values
                if good_min is not None and good_max is not None and good_min <= v <= good_max
            )
            out[event_type] = {
                "samples": len(values),
                "average": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "good_min": good_min,
                "good_max": good_max,
                "in_range_pct": round((in_range / len(values)) * 100, 1) if values else 0.0,
                "unit": cfg.get("unit"),
            }
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Sleep-specific helpers
# ---------------------------------------------------------------------------

def sleep_summary(user_id: int, days: int = 14) -> Dict[str, object]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.event_type == "sleep",
                BehaviorEvent.occurred_at >= cutoff,
            )
            .order_by(BehaviorEvent.occurred_at.asc())
            .all()
        )
        if not rows:
            return {
                "window_days": days,
                "samples": 0,
                "average_hours": None,
                "average_quality": None,
                "average_awakenings": None,
                "sleep_debt_hours": 0.0,
                "target_per_night": 8.0,
            }
        values = [r.value for r in rows if r.value is not None]
        qualities = [r.quality for r in rows if r.quality is not None]
        awakenings = [r.awakenings for r in rows if r.awakenings is not None]

        avg_hours = round(sum(values) / len(values), 2) if values else None
        avg_quality = round(sum(qualities) / len(qualities), 2) if qualities else None
        avg_awakenings = round(sum(awakenings) / len(awakenings), 2) if awakenings else None

        # Sleep debt vs 8h baseline over the window's actual nights.
        target = 8.0
        debt = sum(max(0.0, target - v) for v in values) if values else 0.0

        return {
            "window_days": days,
            "samples": len(rows),
            "average_hours": avg_hours,
            "average_quality": avg_quality,
            "average_awakenings": avg_awakenings,
            "sleep_debt_hours": round(debt, 1),
            "target_per_night": target,
        }
    finally:
        db.close()


def dream_log(user_id: int, days: int = 30) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.event_type == "sleep",
                BehaviorEvent.dream_summary.isnot(None),
                BehaviorEvent.occurred_at >= cutoff,
            )
            .order_by(BehaviorEvent.occurred_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat(),
                "dream_summary": r.dream_summary,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Daily snapshot
# ---------------------------------------------------------------------------

def daily_snapshot(user_id: int, target_date: Optional[date] = None) -> Dict[str, object]:
    if target_date is None:
        target_date = date.today()
    day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    db = SessionLocal()
    try:
        rows = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.occurred_at >= day_start,
                BehaviorEvent.occurred_at < day_end,
            )
            .order_by(BehaviorEvent.occurred_at.asc())
            .all()
        )
        per_type: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for r in rows:
            per_type[r.event_type].append(_serialize(r))
        return {
            "date": target_date.isoformat(),
            "by_type": dict(per_type),
            "event_count": len(rows),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize(row: BehaviorEvent) -> Dict[str, object]:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        "value": row.value,
        "value_unit": row.value_unit,
        "duration_minutes": row.duration_minutes,
        "quality": row.quality,
        "intensity": row.intensity,
        "notes": row.notes,
        "tags": [t for t in (row.tags or "").split(",") if t],
        "bedtime": row.bedtime.isoformat() if row.bedtime else None,
        "wake_time": row.wake_time.isoformat() if row.wake_time else None,
        "awakenings": row.awakenings,
        "dream_summary": row.dream_summary,
    }
