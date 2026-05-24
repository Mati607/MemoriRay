"""
Cross-cutting CBT analytics.

Combines thought records, worry trees, behavioral experiments, activity
schedules, and core belief ratings into higher-level summaries:
  - distortion frequency leaderboards
  - reframe-success rates
  - worry tree split (solvable vs unsolvable) and intensity drop
  - experiment learning rate
  - activity-scheduling balance (pleasure vs mastery) and weekly trend
  - core belief drift (mean strength over time)
  - composite CBT engagement score
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple

from database import SessionLocal
from cbt_models import (
    ThoughtRecord,
    ThoughtRecordDistortion,
    CognitiveDistortion,
    WorryTree,
    BehavioralExperiment,
    ActivitySchedule,
    CoreBelief,
    CoreBeliefRating,
)


@dataclass
class EngagementScore:
    score: float
    label: str
    components: Dict[str, float]
    window_days: int


# ---------------------------------------------------------------------------
# Distortion leaderboard
# ---------------------------------------------------------------------------

def distortion_leaderboard(user_id: int, days: int = 60) -> List[Dict[str, object]]:
    """Most-frequent distortions in the window, with average confidence."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        record_ids = [
            r.id
            for r in db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                ThoughtRecord.created_at >= cutoff,
            )
            .all()
        ]
        if not record_ids:
            return []

        links = (
            db.query(ThoughtRecordDistortion)
            .filter(ThoughtRecordDistortion.record_id.in_(record_ids))
            .all()
        )
        if not links:
            return []

        per_distortion: Dict[int, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "confidence_sum": 0.0, "auto_count": 0}
        )
        for link in links:
            d = per_distortion[link.distortion_id]
            d["count"] = int(d["count"]) + 1
            d["confidence_sum"] = float(d["confidence_sum"]) + float(link.confidence or 0)
            if link.auto_detected:
                d["auto_count"] = int(d["auto_count"]) + 1

        catalog = {
            d.id: d
            for d in db.query(CognitiveDistortion)
            .filter(CognitiveDistortion.id.in_(list(per_distortion.keys())))
            .all()
        }

        out: List[Dict[str, object]] = []
        for did, stats in per_distortion.items():
            d = catalog.get(did)
            if not d:
                continue
            count = int(stats["count"])
            out.append(
                {
                    "distortion_id": did,
                    "key": d.key,
                    "name": d.name,
                    "count": count,
                    "auto_detected": int(stats["auto_count"]),
                    "avg_confidence": round(stats["confidence_sum"] / count, 3) if count else 0.0,
                    "severity_weight": d.severity_weight,
                }
            )
        out.sort(key=lambda r: r["count"], reverse=True)
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Reframe success rate
# ---------------------------------------------------------------------------

def reframe_success(user_id: int, days: int = 60) -> Dict[str, object]:
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
        completed = [r for r in rows if r.is_complete]
        with_intensity = [
            r for r in completed
            if r.emotion_intensity is not None and r.new_emotion_intensity is not None
        ]
        deltas = [
            (r.new_emotion_intensity - r.emotion_intensity) for r in with_intensity
        ]
        positive = sum(1 for d in deltas if d < 0)
        return {
            "window_days": days,
            "total_records": len(rows),
            "completed_records": len(completed),
            "completion_rate": round(len(completed) / len(rows), 3) if rows else 0.0,
            "avg_intensity_delta": round(sum(deltas) / len(deltas), 2) if deltas else None,
            "shift_success_rate": round(positive / len(deltas), 3) if deltas else None,
            "median_belief_drop": _median(
                [
                    (r.belief_in_original_thought or 0) - (r.belief_in_balanced_thought or 0)
                    for r in completed
                    if r.belief_in_original_thought is not None and r.belief_in_balanced_thought is not None
                ]
            ),
        }
    finally:
        db.close()


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return round(s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0, 2)


# ---------------------------------------------------------------------------
# Worry-tree split
# ---------------------------------------------------------------------------

def worry_split(user_id: int, days: int = 60) -> Dict[str, object]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(WorryTree)
            .filter(WorryTree.user_id == user_id, WorryTree.created_at >= cutoff)
            .all()
        )
        if not rows:
            return {
                "window_days": days,
                "total": 0,
                "solvable": 0,
                "unsolvable": 0,
                "unclassified": 0,
                "avg_intensity_drop": None,
                "completed_rate": 0.0,
                "let_go_breakdown": {},
            }
        solvable = sum(1 for r in rows if r.is_solvable is True)
        unsolvable = sum(1 for r in rows if r.is_solvable is False)
        unclassified = len(rows) - solvable - unsolvable
        drops = [
            (r.worry_intensity_before - r.worry_intensity_after)
            for r in rows
            if r.worry_intensity_before is not None and r.worry_intensity_after is not None
        ]
        completed = sum(1 for r in rows if r.is_complete)
        let_go: Counter = Counter()
        for r in rows:
            if r.let_go_strategy:
                let_go[r.let_go_strategy] += 1
        return {
            "window_days": days,
            "total": len(rows),
            "solvable": solvable,
            "unsolvable": unsolvable,
            "unclassified": unclassified,
            "avg_intensity_drop": round(sum(drops) / len(drops), 2) if drops else None,
            "completed_rate": round(completed / len(rows), 3) if rows else 0.0,
            "let_go_breakdown": dict(let_go.most_common()),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Experiment learning rate
# ---------------------------------------------------------------------------

def experiment_summary(user_id: int, days: int = 90) -> Dict[str, object]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(BehavioralExperiment)
            .filter(
                BehavioralExperiment.user_id == user_id,
                BehavioralExperiment.created_at >= cutoff,
            )
            .all()
        )
        if not rows:
            return {
                "window_days": days,
                "total": 0,
                "by_status": {},
                "avg_belief_drop": None,
                "avg_surprise": None,
                "conducted_rate": 0.0,
            }
        statuses: Counter = Counter(r.status for r in rows)
        belief_drops: List[float] = [
            (r.belief_strength_before - r.belief_strength_after)
            for r in rows
            if r.belief_strength_before is not None and r.belief_strength_after is not None
        ]
        surprises: List[float] = [r.surprise_factor for r in rows if r.surprise_factor is not None]
        conducted = statuses.get("conducted", 0) + statuses.get("reviewed", 0)
        return {
            "window_days": days,
            "total": len(rows),
            "by_status": dict(statuses),
            "avg_belief_drop": round(sum(belief_drops) / len(belief_drops), 2) if belief_drops else None,
            "avg_surprise": round(sum(surprises) / len(surprises), 2) if surprises else None,
            "conducted_rate": round(conducted / len(rows), 3) if rows else 0.0,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Activity balance
# ---------------------------------------------------------------------------

def activity_balance(user_id: int, days: int = 30) -> Dict[str, object]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(ActivitySchedule)
            .filter(
                ActivitySchedule.user_id == user_id,
                ActivitySchedule.scheduled_for >= cutoff,
            )
            .all()
        )
        if not rows:
            return {
                "window_days": days,
                "scheduled": 0,
                "completed": 0,
                "pleasure_ratio": 0.0,
                "mastery_ratio": 0.0,
                "avg_pleasure": None,
                "avg_mastery": None,
                "categories": {},
                "top_titles": [],
            }
        completed_rows = [r for r in rows if r.is_completed]
        pleasure_count = sum(1 for r in rows if r.is_pleasure_activity)
        mastery_count = sum(1 for r in rows if r.is_mastery_activity)
        pleasure_scores = [r.pleasure_rating for r in completed_rows if r.pleasure_rating is not None]
        mastery_scores = [r.mastery_rating for r in completed_rows if r.mastery_rating is not None]
        category_counts: Counter = Counter(r.category for r in rows)
        title_scored: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"title": "", "count": 0, "score_sum": 0.0}
        )
        for r in completed_rows:
            key = r.title.lower()
            slot = title_scored[key]
            slot["title"] = r.title
            slot["count"] = int(slot["count"]) + 1
            slot["score_sum"] = float(slot["score_sum"]) + (
                (r.pleasure_rating or 0) + (r.mastery_rating or 0) + (r.energy_after or 0)
            )
        top_titles = sorted(
            (
                {
                    "title": s["title"],
                    "samples": s["count"],
                    "avg_score": round(s["score_sum"] / (s["count"] * 3), 2),
                }
                for s in title_scored.values()
                if s["count"]
            ),
            key=lambda r: r["avg_score"],
            reverse=True,
        )[:5]

        return {
            "window_days": days,
            "scheduled": len(rows),
            "completed": len(completed_rows),
            "completion_rate": round(len(completed_rows) / len(rows), 3) if rows else 0.0,
            "pleasure_ratio": round(pleasure_count / len(rows), 3) if rows else 0.0,
            "mastery_ratio": round(mastery_count / len(rows), 3) if rows else 0.0,
            "avg_pleasure": round(sum(pleasure_scores) / len(pleasure_scores), 2) if pleasure_scores else None,
            "avg_mastery": round(sum(mastery_scores) / len(mastery_scores), 2) if mastery_scores else None,
            "categories": dict(category_counts.most_common()),
            "top_titles": top_titles,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Core belief drift
# ---------------------------------------------------------------------------

def belief_drift(user_id: int, days: int = 180) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        beliefs = (
            db.query(CoreBelief)
            .filter(CoreBelief.user_id == user_id)
            .all()
        )
        out: List[Dict[str, object]] = []
        for belief in beliefs:
            ratings = (
                db.query(CoreBeliefRating)
                .filter(
                    CoreBeliefRating.belief_id == belief.id,
                    CoreBeliefRating.rated_at >= cutoff,
                )
                .order_by(CoreBeliefRating.rated_at.asc())
                .all()
            )
            if not ratings:
                continue
            strengths = [r.strength for r in ratings]
            alts = [r.alternative_strength for r in ratings if r.alternative_strength is not None]
            out.append(
                {
                    "belief_id": belief.id,
                    "statement": belief.statement,
                    "samples": len(strengths),
                    "first": strengths[0],
                    "last": strengths[-1],
                    "delta": round(strengths[-1] - strengths[0], 2),
                    "alternative_first": alts[0] if alts else None,
                    "alternative_last": alts[-1] if alts else None,
                    "alternative_delta": round(alts[-1] - alts[0], 2) if len(alts) >= 2 else None,
                }
            )
        out.sort(key=lambda r: abs(r["delta"]), reverse=True)
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Composite engagement score
# ---------------------------------------------------------------------------

def engagement_score(user_id: int, days: int = 30) -> EngagementScore:
    """0..100 composite of how actively the user is using the CBT workbook."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        n_records = (
            db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                ThoughtRecord.created_at >= cutoff,
            )
            .count()
        )
        n_complete = (
            db.query(ThoughtRecord)
            .filter(
                ThoughtRecord.user_id == user_id,
                ThoughtRecord.created_at >= cutoff,
                ThoughtRecord.is_complete.is_(True),
            )
            .count()
        )
        n_worry = (
            db.query(WorryTree)
            .filter(WorryTree.user_id == user_id, WorryTree.created_at >= cutoff)
            .count()
        )
        n_experiment = (
            db.query(BehavioralExperiment)
            .filter(
                BehavioralExperiment.user_id == user_id,
                BehavioralExperiment.created_at >= cutoff,
            )
            .count()
        )
        n_activity_completed = (
            db.query(ActivitySchedule)
            .filter(
                ActivitySchedule.user_id == user_id,
                ActivitySchedule.is_completed.is_(True),
                ActivitySchedule.scheduled_for >= cutoff,
            )
            .count()
        )
        n_beliefs = (
            db.query(CoreBeliefRating)
            .filter(
                CoreBeliefRating.user_id == user_id,
                CoreBeliefRating.rated_at >= cutoff,
            )
            .count()
        )

        # Targets per 30-day window — each saturates a component.
        records_component = min(n_records / (days / 2), 1.0) * 25
        complete_component = min(
            n_complete / max(1, n_records), 1.0
        ) * 15 if n_records else 0.0
        worry_component = min(n_worry / 4.0, 1.0) * 15
        experiment_component = min(n_experiment / 2.0, 1.0) * 15
        activity_component = min(n_activity_completed / (days / 3), 1.0) * 20
        belief_component = min(n_beliefs / 2.0, 1.0) * 10

        total = (
            records_component
            + complete_component
            + worry_component
            + experiment_component
            + activity_component
            + belief_component
        )
        total = max(0.0, min(100.0, total))

        if total >= 80:
            label = "deep_practice"
        elif total >= 60:
            label = "steady_practice"
        elif total >= 40:
            label = "building_habit"
        elif total >= 20:
            label = "warming_up"
        else:
            label = "barely_started"

        return EngagementScore(
            score=round(total, 1),
            label=label,
            components={
                "thought_records": round(records_component, 1),
                "completion": round(complete_component, 1),
                "worry_trees": round(worry_component, 1),
                "experiments": round(experiment_component, 1),
                "activity_scheduling": round(activity_component, 1),
                "core_beliefs": round(belief_component, 1),
            },
            window_days=days,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Master summary
# ---------------------------------------------------------------------------

def master_summary(user_id: int, days: int = 30) -> Dict[str, object]:
    return {
        "window_days": days,
        "engagement": asdict(engagement_score(user_id, days=days)),
        "reframe": reframe_success(user_id, days=days),
        "distortion_leaderboard": distortion_leaderboard(user_id, days=days),
        "worry": worry_split(user_id, days=days),
        "experiments": experiment_summary(user_id, days=max(days, 90)),
        "activity": activity_balance(user_id, days=days),
        "belief_drift": belief_drift(user_id, days=max(days, 180)),
    }
