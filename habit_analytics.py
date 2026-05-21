"""
Cross-cutting analytics for habits, routines, and behavior events.

Provides completion grids, weekly compliance rates, "habit health"
scoring, mood-vs-habit correlations, and best-time-of-day windows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple

from database import SessionLocal
from habit_models import (
    Habit, HabitCheckIn, HabitStreak,
    BehaviorEvent, BEHAVIOR_EVENT_TYPES,
    Routine, RoutineRun,
)


@dataclass
class HabitHealth:
    score: float           # 0-100
    label: str
    completion_rate: float
    streak_rate: float
    diversity: float
    components: Dict[str, float]
    window_days: int


# ---------------------------------------------------------------------------
# Completion grid
# ---------------------------------------------------------------------------

def completion_grid(user_id: int, days: int = 30) -> Dict[str, object]:
    """Per-habit-per-day status grid. Useful for a heatmap view."""
    db = SessionLocal()
    try:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_archived.is_(False))
            .all()
        )
        check_ins = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.occurred_on >= cutoff_dt,
            )
            .all()
        )

        ins_by_habit: Dict[int, Dict[str, str]] = defaultdict(dict)
        for ci in check_ins:
            ins_by_habit[ci.habit_id][ci.occurred_on.date().isoformat()] = ci.status

        # Build day list (today included).
        today = date.today()
        day_list = [
            (today - timedelta(days=i)).isoformat() for i in range(days)
        ]
        day_list.reverse()

        rows: List[Dict[str, object]] = []
        for h in habits:
            statuses = ins_by_habit.get(h.id, {})
            rows.append(
                {
                    "habit_id": h.id,
                    "name": h.name,
                    "cadence": h.cadence,
                    "days": [
                        {"date": d, "status": statuses.get(d, "missing")}
                        for d in day_list
                    ],
                }
            )
        return {"window_days": days, "days": day_list, "habits": rows}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Weekly compliance
# ---------------------------------------------------------------------------

def weekly_compliance(user_id: int, weeks: int = 8) -> Dict[str, object]:
    """For each habit, fraction of expected occurrences hit per ISO week."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_archived.is_(False))
            .all()
        )
        if not habits:
            return {"weeks": weeks, "compliance": []}

        check_ins = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.occurred_on >= cutoff,
                HabitCheckIn.status != "skipped",
            )
            .all()
        )
        per_habit_weeks: Dict[int, Counter] = defaultdict(Counter)
        for c in check_ins:
            iso_year, iso_week, _ = c.occurred_on.isocalendar()
            per_habit_weeks[c.habit_id][(iso_year, iso_week)] += 1

        out: List[Dict[str, object]] = []
        for h in habits:
            target = _weekly_target(h)
            data_per_week: List[Dict[str, object]] = []
            now = datetime.now(timezone.utc)
            for back in range(weeks - 1, -1, -1):
                ref_day = now - timedelta(weeks=back)
                iy, iw, _ = ref_day.isocalendar()
                hits = per_habit_weeks[h.id].get((iy, iw), 0)
                ratio = round(hits / target, 2) if target else 0.0
                data_per_week.append(
                    {
                        "iso_year": iy,
                        "iso_week": iw,
                        "hits": hits,
                        "target": target,
                        "ratio": ratio,
                    }
                )
            out.append(
                {
                    "habit_id": h.id,
                    "name": h.name,
                    "weeks": data_per_week,
                }
            )
        return {"weeks": weeks, "compliance": out}
    finally:
        db.close()


def _weekly_target(habit: Habit) -> int:
    if habit.cadence == "daily":
        return 7
    if habit.cadence == "weekdays":
        return 5
    if habit.cadence == "weekends":
        return 2
    if habit.cadence == "every_n_days":
        n = habit.interval_days or 1
        return max(1, round(7 / n))
    if habit.cadence == "weekly_n":
        return habit.frequency_per_week or 1
    return 7


# ---------------------------------------------------------------------------
# Habit health composite
# ---------------------------------------------------------------------------

def habit_health(user_id: int, days: int = 14) -> HabitHealth:
    """Composite 0-100 score across completion, streaks, and diversity."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_archived.is_(False))
            .all()
        )
        if not habits:
            return HabitHealth(
                score=0.0, label="no_habits", completion_rate=0.0,
                streak_rate=0.0, diversity=0.0,
                components={"completion": 0.0, "streak": 0.0, "diversity": 0.0},
                window_days=days,
            )

        check_ins = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.occurred_on >= cutoff,
                HabitCheckIn.status != "skipped",
            )
            .all()
        )

        # Completion rate (vs ideal target across all habits)
        ideal = sum(
            _weekly_target(h) * (days / 7.0) for h in habits
        )
        completion_rate = round(len(check_ins) / ideal, 3) if ideal else 0.0
        completion_rate = max(0.0, min(1.0, completion_rate))

        # Streak rate — fraction of habits with at least a small current streak
        streaks = (
            db.query(HabitStreak)
            .filter(HabitStreak.user_id == user_id)
            .all()
        )
        with_streak = sum(1 for s in streaks if (s.current_streak or 0) >= 3)
        streak_rate = round(with_streak / len(habits), 3) if habits else 0.0

        # Diversity — how spread across categories the active habits are
        categories = {h.category for h in habits}
        diversity = round(min(len(categories) / 6.0, 1.0), 3)

        completion_component = round(completion_rate * 50.0, 1)
        streak_component = round(streak_rate * 30.0, 1)
        diversity_component = round(diversity * 20.0, 1)
        total = max(0.0, min(100.0, completion_component + streak_component + diversity_component))

        if total >= 80:
            label = "thriving"
        elif total >= 60:
            label = "consistent"
        elif total >= 40:
            label = "building"
        elif total >= 20:
            label = "starting"
        else:
            label = "stalled"

        return HabitHealth(
            score=round(total, 1),
            label=label,
            completion_rate=completion_rate,
            streak_rate=streak_rate,
            diversity=diversity,
            components={
                "completion": completion_component,
                "streak": streak_component,
                "diversity": diversity_component,
            },
            window_days=days,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Time-of-day window
# ---------------------------------------------------------------------------

def best_check_in_window(user_id: int, days: int = 60) -> Dict[str, object]:
    """When during the day does the user actually do their habits?"""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.occurred_on >= cutoff,
                HabitCheckIn.status != "skipped",
            )
            .all()
        )
        if not rows:
            return {"samples": 0, "best_window": None, "buckets": {}}

        buckets: Counter = Counter()
        for r in rows:
            hour = r.occurred_on.hour
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
        best = buckets.most_common(1)[0][0]
        return {
            "samples": len(rows),
            "best_window": best,
            "buckets": dict(buckets),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Habit-vs-mood correlation
# ---------------------------------------------------------------------------

def habit_vs_mood_correlation(user_id: int, habit_id: int, days: int = 60) -> Dict[str, object]:
    """Pearson correlation between days the habit was done and mood scores
    from journal entries (if the journal feature is available).
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        check_ins = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.habit_id == habit_id,
                HabitCheckIn.occurred_on >= cutoff,
                HabitCheckIn.status != "skipped",
            )
            .all()
        )
        done_days = {c.occurred_on.date() for c in check_ins}

        # Try to pull moods from journal entries if available.
        moods_by_day: Dict[date, List[float]] = defaultdict(list)
        try:
            from journal_models import JournalEntry
            entries = (
                db.query(JournalEntry)
                .filter(
                    JournalEntry.user_id == user_id,
                    JournalEntry.created_at >= cutoff,
                    JournalEntry.mood_score.isnot(None),
                )
                .all()
            )
            for e in entries:
                moods_by_day[e.created_at.date()].append(float(e.mood_score))
        except Exception:
            pass

        if not moods_by_day or not done_days:
            return {
                "samples": 0,
                "pearson_r": None,
                "interpretation": "Need more journal mood entries to correlate.",
            }

        xs: List[float] = []
        ys: List[float] = []
        for d, moods in moods_by_day.items():
            xs.append(1.0 if d in done_days else 0.0)
            ys.append(sum(moods) / len(moods))

        if len(xs) < 5:
            return {
                "samples": len(xs),
                "pearson_r": None,
                "interpretation": "Need more days of journaling to correlate.",
            }

        r = _pearson(xs, ys)
        return {
            "samples": len(xs),
            "pearson_r": round(r, 3),
            "interpretation": _interpret_correlation(r),
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
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _interpret_correlation(r: float) -> str:
    abs_r = abs(r)
    if abs_r < 0.1:
        return "No clear connection yet."
    if r > 0.4:
        return "On days you do this habit, mood is notably higher."
    if r > 0.1:
        return "A small positive lift on habit days."
    if r < -0.4:
        return "Curious — you often skip this on bad days; the habit may be a casualty of low mood."
    if r < -0.1:
        return "Slight negative trend; observe before drawing conclusions."
    return "Mixed pattern."


# ---------------------------------------------------------------------------
# Routine adherence
# ---------------------------------------------------------------------------

def routine_adherence(user_id: int, days: int = 30) -> List[Dict[str, object]]:
    """Per-routine completion ratio across recent runs."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        runs = (
            db.query(RoutineRun)
            .filter(
                RoutineRun.user_id == user_id,
                RoutineRun.started_at >= cutoff,
            )
            .all()
        )
        per_routine: Dict[int, List[float]] = defaultdict(list)
        for r in runs:
            if r.total_steps:
                per_routine[r.routine_id].append(r.completed_steps / r.total_steps)

        routines = (
            db.query(Routine).filter(Routine.user_id == user_id).all()
        )
        name_map = {r.id: r.name for r in routines}

        out: List[Dict[str, object]] = []
        for rid, ratios in per_routine.items():
            out.append(
                {
                    "routine_id": rid,
                    "name": name_map.get(rid, "?"),
                    "runs": len(ratios),
                    "avg_completion": round(sum(ratios) / len(ratios), 2),
                    "best_run": round(max(ratios), 2),
                }
            )
        out.sort(key=lambda r: r["avg_completion"], reverse=True)
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Behavior overlay
# ---------------------------------------------------------------------------

def behavior_alignment(user_id: int, days: int = 14) -> Dict[str, object]:
    """How well are user's behavior events aligned with their good-range targets?"""
    from behavior_tracker import average_by_type
    summary = average_by_type(user_id=user_id, days=days)
    if not summary:
        return {"window_days": days, "events": {}, "alignment_score": 0.0}

    scores: List[float] = []
    for cfg in summary.values():
        scores.append(float(cfg["in_range_pct"]))
    alignment = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {
        "window_days": days,
        "events": summary,
        "alignment_score": alignment,
    }
