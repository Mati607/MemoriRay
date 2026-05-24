"""
Service layer for the non-thought-record CBT worksheets:
  - Worry trees
  - Behavioral experiments
  - Activity scheduling (Behavioral Activation)
  - Core beliefs and their ratings over time
  - Worksheet template catalog
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple

from database import SessionLocal
from cbt_models import (
    WorryTree,
    BehavioralExperiment,
    ActivitySchedule,
    CoreBelief,
    CoreBeliefRating,
    WorksheetTemplate,
)


# ---------------------------------------------------------------------------
# Worry trees
# ---------------------------------------------------------------------------

LET_GO_STRATEGIES = [
    "postpone_worry",
    "self_soothe",
    "defuse",
    "accept",
    "distract",
    "ground",
]


def create_worry(
    user_id: int,
    worry: str,
    what_am_i_worried_about: Optional[str] = None,
    worry_intensity_before: Optional[float] = None,
) -> Dict[str, object]:
    if not worry or not worry.strip():
        raise ValueError("Worry is required.")
    db = SessionLocal()
    try:
        row = WorryTree(
            user_id=user_id,
            worry=worry.strip(),
            what_am_i_worried_about=(what_am_i_worried_about or "").strip() or None,
            worry_intensity_before=_clamp_pct(worry_intensity_before),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_worry(row)
    finally:
        db.close()


def classify_worry(
    user_id: int,
    worry_id: int,
    is_solvable: bool,
    classification_reasoning: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        if not row:
            raise LookupError("Worry not found.")
        row.is_solvable = bool(is_solvable)
        if classification_reasoning is not None:
            row.classification_reasoning = classification_reasoning.strip() or None
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_worry(row)
    finally:
        db.close()


def plan_solvable_branch(
    user_id: int,
    worry_id: int,
    action_step: str,
    when_to_act: Optional[str] = None,
    obstacle_plan: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        if not row:
            raise LookupError("Worry not found.")
        if row.is_solvable is False:
            raise ValueError("This worry is classified as unsolvable.")
        row.is_solvable = True
        row.action_step = action_step.strip() or None
        row.when_to_act = (when_to_act or "").strip() or None
        row.obstacle_plan = (obstacle_plan or "").strip() or None
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_worry(row)
    finally:
        db.close()


def plan_unsolvable_branch(
    user_id: int,
    worry_id: int,
    let_go_strategy: str,
    accept_reframe: Optional[str] = None,
    self_soothing_plan: Optional[str] = None,
) -> Dict[str, object]:
    if let_go_strategy not in LET_GO_STRATEGIES:
        raise ValueError(f"Unknown let-go strategy: {let_go_strategy}")
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        if not row:
            raise LookupError("Worry not found.")
        row.is_solvable = False
        row.let_go_strategy = let_go_strategy
        row.accept_reframe = (accept_reframe or "").strip() or None
        row.self_soothing_plan = (self_soothing_plan or "").strip() or None
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_worry(row)
    finally:
        db.close()


def finish_worry(
    user_id: int,
    worry_id: int,
    worry_intensity_after: Optional[float] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        if not row:
            raise LookupError("Worry not found.")
        if worry_intensity_after is not None:
            row.worry_intensity_after = _clamp_pct(worry_intensity_after)
        row.is_complete = True
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_worry(row)
    finally:
        db.close()


def list_worries(
    user_id: int,
    limit: int = 30,
    only_open: bool = False,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(WorryTree).filter(WorryTree.user_id == user_id)
        if only_open:
            q = q.filter(WorryTree.is_complete.is_(False))
        rows = q.order_by(WorryTree.created_at.desc()).limit(limit).all()
        return [_serialize_worry(r) for r in rows]
    finally:
        db.close()


def get_worry(user_id: int, worry_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        return _serialize_worry(row) if row else None
    finally:
        db.close()


def delete_worry(user_id: int, worry_id: int) -> bool:
    db = SessionLocal()
    try:
        row = _get_worry(db, user_id, worry_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def _get_worry(db, user_id: int, worry_id: int) -> Optional[WorryTree]:
    return (
        db.query(WorryTree)
        .filter(WorryTree.id == worry_id, WorryTree.user_id == user_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Behavioral experiments
# ---------------------------------------------------------------------------

EXPERIMENT_STATUSES = {"planned", "conducted", "reviewed", "abandoned"}


def create_experiment(
    user_id: int,
    target_belief: str,
    prediction: str,
    experiment_design: str,
    belief_strength_before: Optional[float] = None,
    prediction_confidence: Optional[float] = None,
    safety_behaviors_to_drop: Optional[str] = None,
    coping_plan_if_distressing: Optional[str] = None,
    scheduled_for: Optional[datetime] = None,
) -> Dict[str, object]:
    if not target_belief.strip() or not prediction.strip() or not experiment_design.strip():
        raise ValueError("target_belief, prediction, and experiment_design are required.")
    db = SessionLocal()
    try:
        row = BehavioralExperiment(
            user_id=user_id,
            target_belief=target_belief.strip(),
            prediction=prediction.strip(),
            experiment_design=experiment_design.strip(),
            belief_strength_before=_clamp_pct(belief_strength_before),
            prediction_confidence=_clamp_pct(prediction_confidence),
            safety_behaviors_to_drop=(safety_behaviors_to_drop or "").strip() or None,
            coping_plan_if_distressing=(coping_plan_if_distressing or "").strip() or None,
            scheduled_for=scheduled_for,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_experiment(row)
    finally:
        db.close()


def record_experiment_outcome(
    user_id: int,
    experiment_id: int,
    actual_outcome: str,
    surprise_factor: Optional[float] = None,
    belief_strength_after: Optional[float] = None,
    learning_summary: Optional[str] = None,
    next_experiment_idea: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = _get_experiment(db, user_id, experiment_id)
        if not row:
            raise LookupError("Experiment not found.")
        row.actual_outcome = actual_outcome.strip() or None
        row.conducted_at = datetime.now(timezone.utc)
        row.surprise_factor = max(0.0, min(10.0, float(surprise_factor))) if surprise_factor is not None else None
        row.belief_strength_after = _clamp_pct(belief_strength_after)
        row.learning_summary = (learning_summary or "").strip() or None
        row.next_experiment_idea = (next_experiment_idea or "").strip() or None
        row.status = "conducted"
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_experiment(row)
    finally:
        db.close()


def update_experiment_status(user_id: int, experiment_id: int, status: str) -> Dict[str, object]:
    if status not in EXPERIMENT_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    db = SessionLocal()
    try:
        row = _get_experiment(db, user_id, experiment_id)
        if not row:
            raise LookupError("Experiment not found.")
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _serialize_experiment(row)
    finally:
        db.close()


def list_experiments(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 30,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(BehavioralExperiment).filter(BehavioralExperiment.user_id == user_id)
        if status:
            q = q.filter(BehavioralExperiment.status == status)
        rows = q.order_by(BehavioralExperiment.created_at.desc()).limit(limit).all()
        return [_serialize_experiment(r) for r in rows]
    finally:
        db.close()


def get_experiment(user_id: int, experiment_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = _get_experiment(db, user_id, experiment_id)
        return _serialize_experiment(row) if row else None
    finally:
        db.close()


def delete_experiment(user_id: int, experiment_id: int) -> bool:
    db = SessionLocal()
    try:
        row = _get_experiment(db, user_id, experiment_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def _get_experiment(db, user_id: int, experiment_id: int) -> Optional[BehavioralExperiment]:
    return (
        db.query(BehavioralExperiment)
        .filter(
            BehavioralExperiment.id == experiment_id,
            BehavioralExperiment.user_id == user_id,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Activity scheduling (Behavioral Activation)
# ---------------------------------------------------------------------------

ACTIVITY_CATEGORIES = [
    "movement", "social", "creative", "rest", "nature",
    "learning", "self_care", "play", "achievement", "general",
]


def schedule_activity(
    user_id: int,
    title: str,
    scheduled_for: datetime,
    category: str = "general",
    description: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    is_pleasure_activity: bool = True,
    is_mastery_activity: bool = False,
) -> Dict[str, object]:
    if not title.strip():
        raise ValueError("Title is required.")
    if category not in ACTIVITY_CATEGORIES:
        category = "general"
    db = SessionLocal()
    try:
        row = ActivitySchedule(
            user_id=user_id,
            title=title.strip()[:255],
            description=(description or "").strip() or None,
            category=category,
            scheduled_for=scheduled_for,
            duration_minutes=duration_minutes,
            is_pleasure_activity=is_pleasure_activity,
            is_mastery_activity=is_mastery_activity,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_activity(row)
    finally:
        db.close()


def complete_activity(
    user_id: int,
    activity_id: int,
    pleasure_rating: Optional[float] = None,
    mastery_rating: Optional[float] = None,
    energy_after: Optional[float] = None,
    notes: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = (
            db.query(ActivitySchedule)
            .filter(ActivitySchedule.id == activity_id, ActivitySchedule.user_id == user_id)
            .first()
        )
        if not row:
            raise LookupError("Activity not found.")
        row.is_completed = True
        row.completed_at = datetime.now(timezone.utc)
        row.pleasure_rating = _clamp10(pleasure_rating)
        row.mastery_rating = _clamp10(mastery_rating)
        row.energy_after = _clamp10(energy_after)
        row.notes = (notes or "").strip()[:1000] or None
        db.commit()
        db.refresh(row)
        return _serialize_activity(row)
    finally:
        db.close()


def skip_activity(user_id: int, activity_id: int, reason: Optional[str] = None) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = (
            db.query(ActivitySchedule)
            .filter(ActivitySchedule.id == activity_id, ActivitySchedule.user_id == user_id)
            .first()
        )
        if not row:
            raise LookupError("Activity not found.")
        row.is_completed = False
        row.skipped_reason = (reason or "").strip()[:500] or None
        db.commit()
        db.refresh(row)
        return _serialize_activity(row)
    finally:
        db.close()


def list_activities(
    user_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    completed: Optional[bool] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(ActivitySchedule).filter(ActivitySchedule.user_id == user_id)
        if start:
            q = q.filter(ActivitySchedule.scheduled_for >= start)
        if end:
            q = q.filter(ActivitySchedule.scheduled_for <= end)
        if completed is not None:
            q = q.filter(ActivitySchedule.is_completed.is_(completed))
        if category:
            q = q.filter(ActivitySchedule.category == category)
        rows = q.order_by(ActivitySchedule.scheduled_for.asc()).limit(limit).all()
        return [_serialize_activity(r) for r in rows]
    finally:
        db.close()


def delete_activity(user_id: int, activity_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(ActivitySchedule)
            .filter(ActivitySchedule.id == activity_id, ActivitySchedule.user_id == user_id)
            .first()
        )
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def suggest_activities(
    user_id: int, mood_score: Optional[float] = None, limit: int = 5
) -> List[Dict[str, object]]:
    """Suggest activities that have historically scored highest, biased by mood."""
    db = SessionLocal()
    try:
        rows = (
            db.query(ActivitySchedule)
            .filter(
                ActivitySchedule.user_id == user_id,
                ActivitySchedule.is_completed.is_(True),
            )
            .all()
        )
        if not rows:
            return _default_suggestions(mood_score)
        scored: Dict[str, Dict[str, object]] = {}
        for r in rows:
            key = r.title.lower()
            existing = scored.setdefault(
                key,
                {"title": r.title, "category": r.category, "samples": 0, "score": 0.0},
            )
            pleasure = r.pleasure_rating or 0
            mastery = r.mastery_rating or 0
            energy = r.energy_after or 0
            blend = (pleasure * 0.4) + (mastery * 0.3) + (energy * 0.3)
            existing["samples"] = int(existing["samples"]) + 1
            existing["score"] = float(existing["score"]) + blend

        ranked = sorted(scored.values(), key=lambda x: (x["score"] / x["samples"]) , reverse=True)
        if mood_score is not None and mood_score < 4:
            # Low mood — favor pleasure categories
            ranked.sort(
                key=lambda x: (
                    0 if x["category"] in {"rest", "self_care", "social", "play"} else 1,
                    -(x["score"] / x["samples"]),
                )
            )
        return ranked[:limit]
    finally:
        db.close()


def _default_suggestions(mood_score: Optional[float]) -> List[Dict[str, object]]:
    pool = [
        {"title": "Five-minute walk outside", "category": "movement"},
        {"title": "Message a friend", "category": "social"},
        {"title": "One song, eyes closed", "category": "rest"},
        {"title": "Tidy one surface", "category": "achievement"},
        {"title": "Make tea slowly", "category": "self_care"},
        {"title": "Sketch for 3 minutes", "category": "creative"},
        {"title": "Stretch your hips", "category": "movement"},
        {"title": "Look at the sky for 60 seconds", "category": "nature"},
    ]
    return pool[:5]


# ---------------------------------------------------------------------------
# Core beliefs
# ---------------------------------------------------------------------------

BELIEF_CATEGORIES = ["self", "others", "world", "future"]


def add_core_belief(
    user_id: int,
    statement: str,
    category: Optional[str] = None,
    valence: str = "negative",
    alternative_belief: Optional[str] = None,
) -> Dict[str, object]:
    if not statement.strip():
        raise ValueError("Statement is required.")
    if category and category not in BELIEF_CATEGORIES:
        category = None
    db = SessionLocal()
    try:
        row = CoreBelief(
            user_id=user_id,
            statement=statement.strip()[:500],
            category=category,
            valence=valence,
            alternative_belief=(alternative_belief or "").strip() or None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_belief(row)
    finally:
        db.close()


def update_core_belief(
    user_id: int,
    belief_id: int,
    statement: Optional[str] = None,
    category: Optional[str] = None,
    alternative_belief: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = (
            db.query(CoreBelief)
            .filter(CoreBelief.id == belief_id, CoreBelief.user_id == user_id)
            .first()
        )
        if not row:
            raise LookupError("Belief not found.")
        if statement is not None:
            row.statement = statement.strip()[:500]
        if category is not None and category in BELIEF_CATEGORIES:
            row.category = category
        if alternative_belief is not None:
            row.alternative_belief = alternative_belief.strip() or None
        if is_active is not None:
            row.is_active = bool(is_active)
        db.commit()
        db.refresh(row)
        return _serialize_belief(row)
    finally:
        db.close()


def rate_core_belief(
    user_id: int,
    belief_id: int,
    strength: float,
    alternative_strength: Optional[float] = None,
    note: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        belief = (
            db.query(CoreBelief)
            .filter(CoreBelief.id == belief_id, CoreBelief.user_id == user_id)
            .first()
        )
        if not belief:
            raise LookupError("Belief not found.")
        rating = CoreBeliefRating(
            belief_id=belief_id,
            user_id=user_id,
            strength=_clamp_pct(strength) or 0.0,
            alternative_strength=_clamp_pct(alternative_strength),
            note=(note or "").strip() or None,
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        return {
            "id": rating.id,
            "belief_id": rating.belief_id,
            "strength": rating.strength,
            "alternative_strength": rating.alternative_strength,
            "rated_at": rating.rated_at.isoformat(),
            "note": rating.note,
        }
    finally:
        db.close()


def list_core_beliefs(user_id: int, include_inactive: bool = False) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(CoreBelief).filter(CoreBelief.user_id == user_id)
        if not include_inactive:
            q = q.filter(CoreBelief.is_active.is_(True))
        rows = q.order_by(CoreBelief.created_at.desc()).all()
        return [_serialize_belief(r) for r in rows]
    finally:
        db.close()


def belief_history(user_id: int, belief_id: int, limit: int = 50) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        belief = (
            db.query(CoreBelief)
            .filter(CoreBelief.id == belief_id, CoreBelief.user_id == user_id)
            .first()
        )
        if not belief:
            return []
        rows = (
            db.query(CoreBeliefRating)
            .filter(CoreBeliefRating.belief_id == belief_id)
            .order_by(CoreBeliefRating.rated_at.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "strength": r.strength,
                "alternative_strength": r.alternative_strength,
                "rated_at": r.rated_at.isoformat(),
                "note": r.note,
            }
            for r in rows
        ]
    finally:
        db.close()


def delete_core_belief(user_id: int, belief_id: int) -> bool:
    db = SessionLocal()
    try:
        belief = (
            db.query(CoreBelief)
            .filter(CoreBelief.id == belief_id, CoreBelief.user_id == user_id)
            .first()
        )
        if not belief:
            return False
        db.query(CoreBeliefRating).filter(CoreBeliefRating.belief_id == belief_id).delete()
        db.delete(belief)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Worksheet catalog
# ---------------------------------------------------------------------------

def list_worksheet_templates(category: Optional[str] = None) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(WorksheetTemplate)
        if category:
            q = q.filter(WorksheetTemplate.category == category)
        return [_serialize_template(t) for t in q.order_by(WorksheetTemplate.name).all()]
    finally:
        db.close()


def get_worksheet_template(key: str) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = db.query(WorksheetTemplate).filter(WorksheetTemplate.key == key).first()
        return _serialize_template(row) if row else None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_worry(row: WorryTree) -> Dict[str, object]:
    return {
        "id": row.id,
        "worry": row.worry,
        "what_am_i_worried_about": row.what_am_i_worried_about,
        "is_solvable": row.is_solvable,
        "classification_reasoning": row.classification_reasoning,
        "action_step": row.action_step,
        "when_to_act": row.when_to_act,
        "obstacle_plan": row.obstacle_plan,
        "let_go_strategy": row.let_go_strategy,
        "accept_reframe": row.accept_reframe,
        "self_soothing_plan": row.self_soothing_plan,
        "worry_intensity_before": row.worry_intensity_before,
        "worry_intensity_after": row.worry_intensity_after,
        "is_complete": row.is_complete,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_experiment(row: BehavioralExperiment) -> Dict[str, object]:
    return {
        "id": row.id,
        "target_belief": row.target_belief,
        "belief_strength_before": row.belief_strength_before,
        "prediction": row.prediction,
        "prediction_confidence": row.prediction_confidence,
        "experiment_design": row.experiment_design,
        "safety_behaviors_to_drop": row.safety_behaviors_to_drop,
        "coping_plan_if_distressing": row.coping_plan_if_distressing,
        "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
        "conducted_at": row.conducted_at.isoformat() if row.conducted_at else None,
        "actual_outcome": row.actual_outcome,
        "surprise_factor": row.surprise_factor,
        "belief_strength_after": row.belief_strength_after,
        "learning_summary": row.learning_summary,
        "next_experiment_idea": row.next_experiment_idea,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_activity(row: ActivitySchedule) -> Dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
        "duration_minutes": row.duration_minutes,
        "is_completed": row.is_completed,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "pleasure_rating": row.pleasure_rating,
        "mastery_rating": row.mastery_rating,
        "energy_after": row.energy_after,
        "notes": row.notes,
        "skipped_reason": row.skipped_reason,
        "is_pleasure_activity": row.is_pleasure_activity,
        "is_mastery_activity": row.is_mastery_activity,
    }


def _serialize_belief(row: CoreBelief) -> Dict[str, object]:
    return {
        "id": row.id,
        "statement": row.statement,
        "category": row.category,
        "valence": row.valence,
        "alternative_belief": row.alternative_belief,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_template(row: WorksheetTemplate) -> Dict[str, object]:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "instructions": row.instructions,
        "estimated_minutes": row.estimated_minutes,
        "category": row.category,
        "difficulty": row.difficulty,
    }


def _clamp_pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, v))


def _clamp10(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(10.0, v))
