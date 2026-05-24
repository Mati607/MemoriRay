"""
Service layer for CBT thought records.

CRUD over the seven-column thought record, with helpers for attaching/
detaching cognitive distortions, progressing a record through draft →
complete, and computing intensity-shift metrics.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterable, List, Dict, Optional

from sqlalchemy import or_

from database import SessionLocal
from cbt_models import (
    ThoughtRecord,
    CognitiveDistortion,
    ThoughtRecordDistortion,
)


VALID_EMOTIONS = [
    "anxious", "sad", "angry", "ashamed", "guilty", "lonely",
    "hopeless", "frustrated", "afraid", "hurt", "disappointed",
    "embarrassed", "overwhelmed", "numb", "envious", "worried",
    "panicked", "irritated", "rejected", "bitter", "tense",
]


@dataclass
class ShiftMetrics:
    """Before/after metrics for a single thought record."""
    intensity_before: Optional[float]
    intensity_after: Optional[float]
    intensity_delta: Optional[float]
    belief_before: Optional[float]
    belief_after: Optional[float]
    belief_delta: Optional[float]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_record(
    user_id: int,
    situation: str,
    automatic_thought: str,
    primary_emotion: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    secondary_emotions: Optional[List[str]] = None,
    body_sensations: Optional[str] = None,
    behavior_response: Optional[str] = None,
    hot_thought: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    belief_in_original_thought: Optional[float] = None,
) -> Dict[str, object]:
    """Create a draft thought record. The user can come back and complete
    the evidence + balanced-thought columns later.
    """
    if not situation or not situation.strip():
        raise ValueError("Situation is required.")
    if not automatic_thought or not automatic_thought.strip():
        raise ValueError("Automatic thought is required.")

    db = SessionLocal()
    try:
        record = ThoughtRecord(
            user_id=user_id,
            situation=situation.strip(),
            automatic_thought=automatic_thought.strip(),
            hot_thought=(hot_thought or "").strip() or None,
            primary_emotion=primary_emotion,
            emotion_intensity=_clamp_pct(emotion_intensity),
            secondary_emotions=",".join(secondary_emotions or []) or None,
            body_sensations=(body_sensations or "").strip()[:1000] or None,
            behavior_response=(behavior_response or "").strip()[:1000] or None,
            belief_in_original_thought=_clamp_pct(belief_in_original_thought),
            occurred_at=occurred_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return _serialize(db, record)
    finally:
        db.close()


def complete_record(
    user_id: int,
    record_id: int,
    evidence_for: Optional[str] = None,
    evidence_against: Optional[str] = None,
    alternative_view: Optional[str] = None,
    balanced_thought: Optional[str] = None,
    new_emotion_intensity: Optional[float] = None,
    new_behavior_plan: Optional[str] = None,
    belief_in_balanced_thought: Optional[float] = None,
    confidence_in_reframe: Optional[float] = None,
) -> Dict[str, object]:
    """Finish the reframe half of a record."""
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise LookupError("Thought record not found.")

        if evidence_for is not None:
            record.evidence_for = evidence_for.strip() or None
        if evidence_against is not None:
            record.evidence_against = evidence_against.strip() or None
        if alternative_view is not None:
            record.alternative_view = alternative_view.strip() or None
        if balanced_thought is not None:
            record.balanced_thought = balanced_thought.strip() or None
        if new_emotion_intensity is not None:
            record.new_emotion_intensity = _clamp_pct(new_emotion_intensity)
        if new_behavior_plan is not None:
            record.new_behavior_plan = new_behavior_plan.strip() or None
        if belief_in_balanced_thought is not None:
            record.belief_in_balanced_thought = _clamp_pct(belief_in_balanced_thought)
        if confidence_in_reframe is not None:
            record.confidence_in_reframe = _clamp_pct(confidence_in_reframe)

        # A record is "complete" once it has a balanced thought.
        record.is_complete = bool(record.balanced_thought)
        record.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(record)
        return _serialize(db, record)
    finally:
        db.close()


def update_record(user_id: int, record_id: int, **changes) -> Dict[str, object]:
    """Generic update — change any field by name."""
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise LookupError("Thought record not found.")

        text_fields = {
            "situation", "automatic_thought", "hot_thought",
            "body_sensations", "behavior_response",
            "evidence_for", "evidence_against", "alternative_view",
            "balanced_thought", "new_behavior_plan",
        }
        for field, value in changes.items():
            if value is None:
                continue
            if field in text_fields and isinstance(value, str):
                value = value.strip() or None
            if field in {
                "emotion_intensity", "new_emotion_intensity",
                "belief_in_original_thought", "belief_in_balanced_thought",
                "confidence_in_reframe",
            }:
                value = _clamp_pct(value)
            if field == "secondary_emotions" and isinstance(value, list):
                value = ",".join(value) or None
            if hasattr(record, field):
                setattr(record, field, value)
        record.is_complete = bool(record.balanced_thought)
        record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return _serialize(db, record)
    finally:
        db.close()


def delete_record(user_id: int, record_id: int) -> bool:
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            return False
        db.query(ThoughtRecordDistortion).filter(
            ThoughtRecordDistortion.record_id == record.id
        ).delete()
        db.delete(record)
        db.commit()
        return True
    finally:
        db.close()


def get_record(user_id: int, record_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        return _serialize(db, record, include_full=True) if record else None
    finally:
        db.close()


def list_records(
    user_id: int,
    limit: int = 30,
    offset: int = 0,
    is_complete: Optional[bool] = None,
    primary_emotion: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(ThoughtRecord).filter(ThoughtRecord.user_id == user_id)
        if is_complete is not None:
            q = q.filter(ThoughtRecord.is_complete.is_(is_complete))
        if primary_emotion:
            q = q.filter(ThoughtRecord.primary_emotion == primary_emotion)
        if start_date:
            q = q.filter(ThoughtRecord.created_at >= start_date)
        if end_date:
            q = q.filter(ThoughtRecord.created_at <= end_date)
        rows = q.order_by(ThoughtRecord.created_at.desc()).offset(offset).limit(limit).all()
        return [_serialize(db, r) for r in rows]
    finally:
        db.close()


def search_records(user_id: int, query: str, limit: int = 30) -> List[Dict[str, object]]:
    if not query or not query.strip():
        return []
    db = SessionLocal()
    try:
        like = f"%{query.strip()}%"
        rows = (
            db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                or_(
                    ThoughtRecord.situation.ilike(like),
                    ThoughtRecord.automatic_thought.ilike(like),
                    ThoughtRecord.balanced_thought.ilike(like),
                    ThoughtRecord.evidence_for.ilike(like),
                    ThoughtRecord.evidence_against.ilike(like),
                ),
            )
            .order_by(ThoughtRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_serialize(db, r, include_full=True) for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Distortion attachments
# ---------------------------------------------------------------------------

def attach_distortion(
    user_id: int,
    record_id: int,
    distortion_id: int,
    confidence: float = 1.0,
    auto_detected: bool = False,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise LookupError("Thought record not found.")
        distortion = (
            db.query(CognitiveDistortion).filter(CognitiveDistortion.id == distortion_id).first()
        )
        if not distortion:
            raise LookupError("Distortion not found.")

        existing = (
            db.query(ThoughtRecordDistortion)
            .filter(
                ThoughtRecordDistortion.record_id == record_id,
                ThoughtRecordDistortion.distortion_id == distortion_id,
            )
            .first()
        )
        if existing:
            existing.confidence = max(existing.confidence or 0.0, float(confidence))
            link = existing
        else:
            link = ThoughtRecordDistortion(
                record_id=record_id,
                distortion_id=distortion_id,
                confidence=float(confidence),
                auto_detected=bool(auto_detected),
            )
            db.add(link)
        db.commit()
        db.refresh(link)
        return {
            "id": link.id,
            "record_id": link.record_id,
            "distortion_id": link.distortion_id,
            "distortion_key": distortion.key,
            "distortion_name": distortion.name,
            "confidence": link.confidence,
            "auto_detected": link.auto_detected,
        }
    finally:
        db.close()


def detach_distortion(user_id: int, record_id: int, distortion_id: int) -> bool:
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            return False
        deleted = (
            db.query(ThoughtRecordDistortion)
            .filter(
                ThoughtRecordDistortion.record_id == record_id,
                ThoughtRecordDistortion.distortion_id == distortion_id,
            )
            .delete()
        )
        db.commit()
        return bool(deleted)
    finally:
        db.close()


def list_distortion_catalog() -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        rows = db.query(CognitiveDistortion).order_by(CognitiveDistortion.name).all()
        return [
            {
                "id": r.id,
                "key": r.key,
                "name": r.name,
                "short_description": r.short_description,
                "example": r.example,
                "reframe_guidance": r.reframe_guidance,
                "severity_weight": r.severity_weight,
            }
            for r in rows
        ]
    finally:
        db.close()


def list_distortions_for_record(record_id: int) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        links = (
            db.query(ThoughtRecordDistortion)
            .filter(ThoughtRecordDistortion.record_id == record_id)
            .all()
        )
        if not links:
            return []
        ids = [l.distortion_id for l in links]
        cat_map = {
            d.id: d
            for d in db.query(CognitiveDistortion).filter(CognitiveDistortion.id.in_(ids)).all()
        }
        out: List[Dict[str, object]] = []
        for link in links:
            d = cat_map.get(link.distortion_id)
            if not d:
                continue
            out.append(
                {
                    "id": link.id,
                    "distortion_id": d.id,
                    "key": d.key,
                    "name": d.name,
                    "confidence": link.confidence,
                    "auto_detected": link.auto_detected,
                    "reframe_guidance": d.reframe_guidance,
                }
            )
        out.sort(key=lambda r: (r["confidence"] or 0), reverse=True)
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def shift_metrics(user_id: int, record_id: int) -> Optional[ShiftMetrics]:
    db = SessionLocal()
    try:
        record = (
            db.query(ThoughtRecord)
            .filter(ThoughtRecord.id == record_id, ThoughtRecord.user_id == user_id)
            .first()
        )
        if not record:
            return None
        intensity_delta = (
            (record.new_emotion_intensity - record.emotion_intensity)
            if record.new_emotion_intensity is not None and record.emotion_intensity is not None
            else None
        )
        belief_delta = (
            (record.belief_in_balanced_thought - record.belief_in_original_thought)
            if record.belief_in_balanced_thought is not None and record.belief_in_original_thought is not None
            else None
        )
        return ShiftMetrics(
            intensity_before=record.emotion_intensity,
            intensity_after=record.new_emotion_intensity,
            intensity_delta=intensity_delta,
            belief_before=record.belief_in_original_thought,
            belief_after=record.belief_in_balanced_thought,
            belief_delta=belief_delta,
        )
    finally:
        db.close()


def aggregate_shift_metrics(user_id: int, days: int = 60) -> Dict[str, object]:
    """Average intensity drop across completed records in the window."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                ThoughtRecord.created_at >= cutoff,
                ThoughtRecord.is_complete.is_(True),
            )
            .all()
        )
        deltas: List[float] = []
        positive_shifts = 0
        for r in rows:
            if r.emotion_intensity is not None and r.new_emotion_intensity is not None:
                delta = r.new_emotion_intensity - r.emotion_intensity
                deltas.append(delta)
                if delta < 0:
                    positive_shifts += 1

        avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else None
        return {
            "window_days": days,
            "completed": len(rows),
            "with_intensity_pair": len(deltas),
            "avg_intensity_delta": avg_delta,
            "positive_shifts": positive_shifts,
            "shift_success_rate": (
                round(positive_shifts / len(deltas), 3) if deltas else None
            ),
        }
    finally:
        db.close()


def emotion_breakdown(user_id: int, days: int = 60) -> Dict[str, int]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                ThoughtRecord.created_at >= cutoff,
            )
            .all()
        )
        counts: Counter = Counter()
        for r in rows:
            if r.primary_emotion:
                counts[r.primary_emotion] += 1
        return dict(counts.most_common())
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp_pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, v))


def _serialize(db, record: ThoughtRecord, include_full: bool = False) -> Dict[str, object]:
    distortions = list_distortions_for_record(record.id) if include_full else []
    base = {
        "id": record.id,
        "situation": record.situation if include_full else (record.situation or "")[:160],
        "automatic_thought": record.automatic_thought if include_full else (record.automatic_thought or "")[:160],
        "primary_emotion": record.primary_emotion,
        "emotion_intensity": record.emotion_intensity,
        "new_emotion_intensity": record.new_emotion_intensity,
        "is_complete": record.is_complete,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if not include_full:
        return base
    base.update(
        {
            "hot_thought": record.hot_thought,
            "secondary_emotions": [
                e for e in (record.secondary_emotions or "").split(",") if e
            ],
            "body_sensations": record.body_sensations,
            "behavior_response": record.behavior_response,
            "evidence_for": record.evidence_for,
            "evidence_against": record.evidence_against,
            "alternative_view": record.alternative_view,
            "balanced_thought": record.balanced_thought,
            "new_behavior_plan": record.new_behavior_plan,
            "belief_in_original_thought": record.belief_in_original_thought,
            "belief_in_balanced_thought": record.belief_in_balanced_thought,
            "confidence_in_reframe": record.confidence_in_reframe,
            "occurred_at": record.occurred_at.isoformat() if record.occurred_at else None,
            "distortions": distortions,
        }
    )
    return base
