"""
Service layer for habits, check-ins, stacks, and routines.

Handles CRUD, cadence-aware "is the habit due today" logic, streak
recomputation (which is more involved than a simple counter because
weekly-N habits don't need consecutive days), habit stack ordering,
and routine execution tracking.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Iterable, List, Dict, Optional, Tuple

from database import SessionLocal
from habit_models import (
    Habit, HabitCheckIn, HabitStreak,
    HabitStack, HabitStackStep,
    Routine, RoutineStep, RoutineRun,
    HABIT_CATEGORIES,
)


VALID_CADENCES = {"daily", "weekdays", "weekends", "weekly_n", "every_n_days"}
VALID_STATUS = {"done", "partial", "skipped"}


# ---------------------------------------------------------------------------
# Habit CRUD
# ---------------------------------------------------------------------------

def create_habit(
    user_id: int,
    name: str,
    category: str = "general",
    cadence: str = "daily",
    frequency_per_week: Optional[int] = None,
    interval_days: Optional[int] = None,
    description: Optional[str] = None,
    target_minutes: Optional[int] = None,
    target_count: Optional[int] = None,
    unit: Optional[str] = None,
    reminder_time: Optional[str] = None,
    reminder_enabled: bool = False,
    cue: Optional[str] = None,
    reward: Optional[str] = None,
    motivation: Optional[str] = None,
    difficulty: str = "easy",
    is_keystone: bool = False,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    target_streak: Optional[int] = None,
) -> Dict[str, object]:
    if not name or not name.strip():
        raise ValueError("Habit name is required.")
    if cadence not in VALID_CADENCES:
        raise ValueError(f"Unknown cadence: {cadence}")
    if cadence == "weekly_n" and (frequency_per_week or 0) < 1:
        raise ValueError("weekly_n cadence requires frequency_per_week >= 1.")
    if cadence == "every_n_days" and (interval_days or 0) < 1:
        raise ValueError("every_n_days cadence requires interval_days >= 1.")
    if category not in HABIT_CATEGORIES:
        category = "general"

    db = SessionLocal()
    try:
        habit = Habit(
            user_id=user_id,
            name=name.strip()[:200],
            description=(description or "").strip()[:1000] or None,
            category=category,
            cadence=cadence,
            frequency_per_week=frequency_per_week,
            interval_days=interval_days,
            target_minutes=target_minutes,
            target_count=target_count,
            unit=unit,
            reminder_time=reminder_time,
            reminder_enabled=reminder_enabled,
            cue=cue,
            reward=reward,
            motivation=motivation,
            difficulty=difficulty,
            is_keystone=is_keystone,
            icon=icon,
            color=color,
            target_streak=target_streak,
        )
        db.add(habit)
        db.commit()
        db.refresh(habit)
        # Initialize the streak row so we always have one to update.
        streak = HabitStreak(habit_id=habit.id, user_id=user_id)
        db.add(streak)
        db.commit()
        return _serialize_habit(db, habit)
    finally:
        db.close()


def update_habit(user_id: int, habit_id: int, **changes) -> Dict[str, object]:
    db = SessionLocal()
    try:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        if not habit:
            raise LookupError("Habit not found.")

        for field in [
            "name", "description", "category", "cadence", "frequency_per_week",
            "interval_days", "target_minutes", "target_count", "unit",
            "reminder_time", "reminder_enabled", "cue", "reward",
            "motivation", "difficulty", "is_keystone", "icon", "color",
            "target_streak", "is_archived",
        ]:
            if field in changes and changes[field] is not None:
                setattr(habit, field, changes[field])
        if habit.cadence not in VALID_CADENCES:
            raise ValueError(f"Unknown cadence: {habit.cadence}")
        habit.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(habit)
        return _serialize_habit(db, habit)
    finally:
        db.close()


def archive_habit(user_id: int, habit_id: int, archived: bool = True) -> bool:
    db = SessionLocal()
    try:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        if not habit:
            return False
        habit.is_archived = bool(archived)
        habit.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    finally:
        db.close()


def delete_habit(user_id: int, habit_id: int) -> bool:
    db = SessionLocal()
    try:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        if not habit:
            return False
        db.query(HabitCheckIn).filter(HabitCheckIn.habit_id == habit_id).delete()
        db.query(HabitStreak).filter(HabitStreak.habit_id == habit_id).delete()
        # Detach stack steps that point to this habit
        db.query(HabitStackStep).filter(HabitStackStep.habit_id == habit_id).delete()
        # Detach routine steps too
        db.query(RoutineStep).filter(RoutineStep.habit_id == habit_id).update(
            {RoutineStep.habit_id: None}
        )
        db.delete(habit)
        db.commit()
        return True
    finally:
        db.close()


def get_habit(user_id: int, habit_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        return _serialize_habit(db, habit) if habit else None
    finally:
        db.close()


def list_habits(
    user_id: int,
    include_archived: bool = False,
    category: Optional[str] = None,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(Habit).filter(Habit.user_id == user_id)
        if not include_archived:
            q = q.filter(Habit.is_archived.is_(False))
        if category:
            q = q.filter(Habit.category == category)
        rows = q.order_by(Habit.is_keystone.desc(), Habit.created_at.desc()).all()
        return [_serialize_habit(db, h) for h in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Cadence helpers
# ---------------------------------------------------------------------------

def is_due_on(habit: Habit, day: date, last_check_in: Optional[date] = None) -> bool:
    """Return True if the habit should be done on `day`."""
    if habit.cadence == "daily":
        return True
    if habit.cadence == "weekdays":
        return day.weekday() < 5
    if habit.cadence == "weekends":
        return day.weekday() >= 5
    if habit.cadence == "every_n_days":
        if last_check_in is None:
            return True
        return (day - last_check_in).days >= (habit.interval_days or 1)
    if habit.cadence == "weekly_n":
        # The habit is "due" on any day until it's been done its frequency-per-week
        # times in the current ISO week.
        week_start = day - timedelta(days=day.weekday())
        # Inspection is up to the caller — here we just say "any weekday is okay".
        return True
    return True


def habits_due_today(user_id: int, day: Optional[date] = None) -> List[Dict[str, object]]:
    """List habits that are due today, with check-in status."""
    target_day = day or date.today()
    db = SessionLocal()
    try:
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_archived.is_(False))
            .all()
        )
        out: List[Dict[str, object]] = []
        for h in habits:
            streak = (
                db.query(HabitStreak)
                .filter(HabitStreak.habit_id == h.id)
                .first()
            )
            last_day = streak.last_check_in.date() if streak and streak.last_check_in else None
            if not is_due_on(h, target_day, last_day):
                continue

            # Check today's status
            day_start = datetime.combine(target_day, datetime.min.time()).replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            check = (
                db.query(HabitCheckIn)
                .filter(
                    HabitCheckIn.habit_id == h.id,
                    HabitCheckIn.occurred_on >= day_start,
                    HabitCheckIn.occurred_on < day_end,
                )
                .first()
            )

            data = _serialize_habit(db, h)
            data["today_status"] = check.status if check else "pending"
            data["today_check_in_id"] = check.id if check else None
            out.append(data)
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Check-ins
# ---------------------------------------------------------------------------

def check_in(
    user_id: int,
    habit_id: int,
    occurred_on: Optional[datetime] = None,
    status: str = "done",
    quantity: Optional[float] = None,
    duration_minutes: Optional[int] = None,
    quality: Optional[float] = None,
    notes: Optional[str] = None,
) -> Dict[str, object]:
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status}")
    occurred = occurred_on or datetime.now(timezone.utc)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)

    db = SessionLocal()
    try:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        if not habit:
            raise LookupError("Habit not found.")

        # Replace existing same-day check-in to keep one-per-day semantics.
        day_start = datetime.combine(occurred.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        db.query(HabitCheckIn).filter(
            HabitCheckIn.habit_id == habit_id,
            HabitCheckIn.occurred_on >= day_start,
            HabitCheckIn.occurred_on < day_end,
        ).delete()

        check = HabitCheckIn(
            habit_id=habit_id,
            user_id=user_id,
            occurred_on=occurred,
            status=status,
            quantity=quantity,
            duration_minutes=duration_minutes,
            quality=quality,
            notes=(notes or "")[:1000] or None,
        )
        db.add(check)
        db.commit()
        db.refresh(check)

        _recompute_streak(db, habit)
        db.commit()

        return _serialize_check_in(check)
    finally:
        db.close()


def delete_check_in(user_id: int, check_in_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(HabitCheckIn)
            .filter(HabitCheckIn.id == check_in_id, HabitCheckIn.user_id == user_id)
            .first()
        )
        if not row:
            return False
        habit_id = row.habit_id
        db.delete(row)
        db.commit()
        habit = db.query(Habit).filter(Habit.id == habit_id).first()
        if habit:
            _recompute_streak(db, habit)
            db.commit()
        return True
    finally:
        db.close()


def list_check_ins(
    user_id: int,
    habit_id: Optional[int] = None,
    days: int = 30,
    limit: int = 200,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = db.query(HabitCheckIn).filter(
            HabitCheckIn.user_id == user_id,
            HabitCheckIn.occurred_on >= cutoff,
        )
        if habit_id:
            q = q.filter(HabitCheckIn.habit_id == habit_id)
        rows = q.order_by(HabitCheckIn.occurred_on.desc()).limit(limit).all()
        return [_serialize_check_in(r) for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Streak recomputation
# ---------------------------------------------------------------------------

def _recompute_streak(db, habit: Habit) -> None:
    streak = (
        db.query(HabitStreak).filter(HabitStreak.habit_id == habit.id).first()
    )
    if not streak:
        streak = HabitStreak(habit_id=habit.id, user_id=habit.user_id)
        db.add(streak)
        db.flush()

    check_ins = (
        db.query(HabitCheckIn)
        .filter(HabitCheckIn.habit_id == habit.id)
        .order_by(HabitCheckIn.occurred_on.asc())
        .all()
    )

    streak.total_check_ins = sum(1 for c in check_ins if c.status != "skipped")
    streak.total_skips = sum(1 for c in check_ins if c.status == "skipped")

    if not check_ins:
        streak.current_streak = 0
        streak.longest_streak = max(streak.longest_streak or 0, 0)
        streak.last_check_in = None
        streak.next_due = None
        streak.updated_at = datetime.now(timezone.utc)
        return

    streak.last_check_in = check_ins[-1].occurred_on

    if habit.cadence in ("daily", "weekdays", "weekends", "every_n_days"):
        longest, current = _calc_consecutive_streak(habit, check_ins)
    else:
        # weekly_n: count weeks where the habit hit its frequency.
        longest, current = _calc_weekly_n_streak(habit, check_ins)

    streak.current_streak = current
    streak.longest_streak = max(streak.longest_streak or 0, longest)
    streak.next_due = _compute_next_due(habit, check_ins[-1].occurred_on)
    streak.updated_at = datetime.now(timezone.utc)


def _calc_consecutive_streak(habit: Habit, check_ins: List[HabitCheckIn]) -> Tuple[int, int]:
    """Longest and current consecutive on-day streak, respecting cadence."""
    done_days = sorted({c.occurred_on.date() for c in check_ins if c.status != "skipped"})
    if not done_days:
        return 0, 0

    def increment(prev: date, curr: date) -> bool:
        if habit.cadence == "daily":
            return (curr - prev).days == 1
        if habit.cadence == "weekdays":
            # Skip Saturday/Sunday in the gap.
            d = prev
            while True:
                d += timedelta(days=1)
                if d.weekday() < 5:
                    return d == curr
                if d > curr:
                    return False
        if habit.cadence == "weekends":
            d = prev
            while True:
                d += timedelta(days=1)
                if d.weekday() >= 5:
                    return d == curr
                if d > curr:
                    return False
        if habit.cadence == "every_n_days":
            return (curr - prev).days == (habit.interval_days or 1)
        return False

    longest = current = 1
    for prev, curr in zip(done_days, done_days[1:]):
        if increment(prev, curr):
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    today = datetime.now(timezone.utc).date()
    last = done_days[-1]
    gap = (today - last).days
    if habit.cadence == "daily" and gap > 1:
        current = 0
    elif habit.cadence == "weekdays" and gap > 3:
        current = 0
    elif habit.cadence == "weekends" and gap > 7:
        current = 0
    elif habit.cadence == "every_n_days" and gap > (habit.interval_days or 1) * 2:
        current = 0
    return longest, current


def _calc_weekly_n_streak(habit: Habit, check_ins: List[HabitCheckIn]) -> Tuple[int, int]:
    """Streak measured in weeks where the habit hit its frequency_per_week."""
    target = habit.frequency_per_week or 1
    weeks: Dict[Tuple[int, int], int] = defaultdict(int)
    for c in check_ins:
        if c.status == "skipped":
            continue
        iso_year, iso_week, _ = c.occurred_on.isocalendar()
        weeks[(iso_year, iso_week)] += 1

    sorted_weeks = sorted(weeks.keys())
    if not sorted_weeks:
        return 0, 0

    longest = current = 1 if weeks[sorted_weeks[0]] >= target else 0
    for prev, curr in zip(sorted_weeks, sorted_weeks[1:]):
        prev_hit = weeks[prev] >= target
        curr_hit = weeks[curr] >= target
        if not curr_hit:
            current = 0
            continue
        if not prev_hit:
            current = 1
            continue
        # Consecutive weeks?
        if _weeks_consecutive(prev, curr):
            current += 1
        else:
            current = 1
        longest = max(longest, current)

    now = datetime.now(timezone.utc)
    iso_now = (now.isocalendar().year, now.isocalendar().week)
    if iso_now not in weeks or weeks[iso_now] < target:
        # Current week not yet hit — streak preserved from last completed week
        # only if it was last week.
        if sorted_weeks:
            last = sorted_weeks[-1]
            if not _weeks_consecutive(last, iso_now):
                current = 0
    return longest, current


def _weeks_consecutive(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    year_a, week_a = a
    year_b, week_b = b
    if year_a == year_b:
        return week_b - week_a == 1
    if year_b == year_a + 1 and week_a >= 52 and week_b == 1:
        return True
    return False


def _compute_next_due(habit: Habit, last: datetime) -> Optional[datetime]:
    if habit.cadence == "daily":
        return last + timedelta(days=1)
    if habit.cadence == "weekdays":
        d = last + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d
    if habit.cadence == "weekends":
        d = last + timedelta(days=1)
        while d.weekday() < 5:
            d += timedelta(days=1)
        return d
    if habit.cadence == "every_n_days":
        return last + timedelta(days=habit.interval_days or 1)
    if habit.cadence == "weekly_n":
        return last + timedelta(days=1)
    return None


# ---------------------------------------------------------------------------
# Habit stacks
# ---------------------------------------------------------------------------

def create_stack(
    user_id: int,
    name: str,
    anchor_habit_id: int,
    follow_up_habit_ids: List[int],
    description: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        anchor = (
            db.query(Habit)
            .filter(Habit.id == anchor_habit_id, Habit.user_id == user_id)
            .first()
        )
        if not anchor:
            raise LookupError("Anchor habit not found.")
        stack = HabitStack(
            user_id=user_id,
            name=name.strip()[:200],
            anchor_habit_id=anchor_habit_id,
            description=(description or "").strip()[:1000] or None,
        )
        db.add(stack)
        db.flush()
        for idx, hid in enumerate(follow_up_habit_ids):
            db.add(HabitStackStep(stack_id=stack.id, habit_id=hid, order_index=idx))
        db.commit()
        db.refresh(stack)
        return _serialize_stack(db, stack)
    finally:
        db.close()


def list_stacks(user_id: int) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        stacks = (
            db.query(HabitStack)
            .filter(HabitStack.user_id == user_id)
            .order_by(HabitStack.created_at.desc())
            .all()
        )
        return [_serialize_stack(db, s) for s in stacks]
    finally:
        db.close()


def delete_stack(user_id: int, stack_id: int) -> bool:
    db = SessionLocal()
    try:
        stack = (
            db.query(HabitStack)
            .filter(HabitStack.id == stack_id, HabitStack.user_id == user_id)
            .first()
        )
        if not stack:
            return False
        db.query(HabitStackStep).filter(HabitStackStep.stack_id == stack.id).delete()
        db.delete(stack)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

def create_routine(
    user_id: int,
    name: str,
    steps: List[Dict[str, object]],
    when_to_run: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
    description: Optional[str] = None,
) -> Dict[str, object]:
    if not name or not name.strip():
        raise ValueError("Routine name is required.")
    if not steps:
        raise ValueError("Routine must have at least one step.")

    db = SessionLocal()
    try:
        routine = Routine(
            user_id=user_id,
            name=name.strip()[:200],
            description=(description or "").strip()[:1000] or None,
            when_to_run=when_to_run,
            estimated_minutes=estimated_minutes,
        )
        db.add(routine)
        db.flush()
        for idx, step in enumerate(steps):
            db.add(
                RoutineStep(
                    routine_id=routine.id,
                    order_index=idx,
                    text=str(step.get("text", "")).strip()[:1000],
                    expected_minutes=step.get("expected_minutes"),
                    habit_id=step.get("habit_id"),
                )
            )
        db.commit()
        db.refresh(routine)
        return _serialize_routine(db, routine)
    finally:
        db.close()


def update_routine(user_id: int, routine_id: int, **changes) -> Dict[str, object]:
    db = SessionLocal()
    try:
        routine = (
            db.query(Routine)
            .filter(Routine.id == routine_id, Routine.user_id == user_id)
            .first()
        )
        if not routine:
            raise LookupError("Routine not found.")
        for field in ["name", "description", "when_to_run", "estimated_minutes", "is_active"]:
            if field in changes and changes[field] is not None:
                setattr(routine, field, changes[field])
        routine.updated_at = datetime.now(timezone.utc)

        if "steps" in changes and changes["steps"] is not None:
            db.query(RoutineStep).filter(RoutineStep.routine_id == routine.id).delete()
            for idx, step in enumerate(changes["steps"]):
                db.add(
                    RoutineStep(
                        routine_id=routine.id,
                        order_index=idx,
                        text=str(step.get("text", "")).strip()[:1000],
                        expected_minutes=step.get("expected_minutes"),
                        habit_id=step.get("habit_id"),
                    )
                )

        db.commit()
        db.refresh(routine)
        return _serialize_routine(db, routine)
    finally:
        db.close()


def list_routines(user_id: int, include_inactive: bool = False) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(Routine).filter(Routine.user_id == user_id)
        if not include_inactive:
            q = q.filter(Routine.is_active.is_(True))
        return [_serialize_routine(db, r) for r in q.order_by(Routine.created_at.desc()).all()]
    finally:
        db.close()


def get_routine(user_id: int, routine_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        routine = (
            db.query(Routine)
            .filter(Routine.id == routine_id, Routine.user_id == user_id)
            .first()
        )
        return _serialize_routine(db, routine) if routine else None
    finally:
        db.close()


def delete_routine(user_id: int, routine_id: int) -> bool:
    db = SessionLocal()
    try:
        routine = (
            db.query(Routine)
            .filter(Routine.id == routine_id, Routine.user_id == user_id)
            .first()
        )
        if not routine:
            return False
        db.query(RoutineStep).filter(RoutineStep.routine_id == routine.id).delete()
        db.query(RoutineRun).filter(RoutineRun.routine_id == routine.id).delete()
        db.delete(routine)
        db.commit()
        return True
    finally:
        db.close()


def record_routine_run(
    user_id: int,
    routine_id: int,
    completed_steps: int,
    duration_minutes: Optional[float] = None,
    notes: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        routine = (
            db.query(Routine)
            .filter(Routine.id == routine_id, Routine.user_id == user_id)
            .first()
        )
        if not routine:
            raise LookupError("Routine not found.")

        total_steps = (
            db.query(RoutineStep).filter(RoutineStep.routine_id == routine.id).count()
        )

        run = RoutineRun(
            user_id=user_id,
            routine_id=routine_id,
            ended_at=datetime.now(timezone.utc),
            duration_minutes=duration_minutes,
            completed_steps=completed_steps,
            total_steps=total_steps,
            notes=(notes or "")[:1000] or None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return _serialize_routine_run(run)
    finally:
        db.close()


def list_routine_runs(
    user_id: int,
    routine_id: Optional[int] = None,
    days: int = 30,
) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = db.query(RoutineRun).filter(
            RoutineRun.user_id == user_id,
            RoutineRun.started_at >= cutoff,
        )
        if routine_id:
            q = q.filter(RoutineRun.routine_id == routine_id)
        return [
            _serialize_routine_run(r)
            for r in q.order_by(RoutineRun.started_at.desc()).all()
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_habit(db, habit: Habit) -> Dict[str, object]:
    streak = (
        db.query(HabitStreak).filter(HabitStreak.habit_id == habit.id).first()
    )
    return {
        "id": habit.id,
        "name": habit.name,
        "description": habit.description,
        "category": habit.category,
        "cadence": habit.cadence,
        "frequency_per_week": habit.frequency_per_week,
        "interval_days": habit.interval_days,
        "target_minutes": habit.target_minutes,
        "target_count": habit.target_count,
        "target_streak": habit.target_streak,
        "unit": habit.unit,
        "reminder_time": habit.reminder_time,
        "reminder_enabled": habit.reminder_enabled,
        "cue": habit.cue,
        "reward": habit.reward,
        "motivation": habit.motivation,
        "difficulty": habit.difficulty,
        "is_keystone": habit.is_keystone,
        "is_archived": habit.is_archived,
        "icon": habit.icon,
        "color": habit.color,
        "created_at": habit.created_at.isoformat() if habit.created_at else None,
        "streak": {
            "current": streak.current_streak if streak else 0,
            "longest": streak.longest_streak if streak else 0,
            "total_check_ins": streak.total_check_ins if streak else 0,
            "total_skips": streak.total_skips if streak else 0,
            "last_check_in": streak.last_check_in.isoformat() if streak and streak.last_check_in else None,
            "next_due": streak.next_due.isoformat() if streak and streak.next_due else None,
        },
    }


def _serialize_check_in(row: HabitCheckIn) -> Dict[str, object]:
    return {
        "id": row.id,
        "habit_id": row.habit_id,
        "occurred_on": row.occurred_on.isoformat() if row.occurred_on else None,
        "status": row.status,
        "quantity": row.quantity,
        "duration_minutes": row.duration_minutes,
        "quality": row.quality,
        "notes": row.notes,
    }


def _serialize_stack(db, stack: HabitStack) -> Dict[str, object]:
    steps = (
        db.query(HabitStackStep)
        .filter(HabitStackStep.stack_id == stack.id)
        .order_by(HabitStackStep.order_index.asc())
        .all()
    )
    return {
        "id": stack.id,
        "name": stack.name,
        "anchor_habit_id": stack.anchor_habit_id,
        "description": stack.description,
        "is_active": stack.is_active,
        "steps": [{"habit_id": s.habit_id, "order_index": s.order_index} for s in steps],
        "created_at": stack.created_at.isoformat() if stack.created_at else None,
    }


def _serialize_routine(db, routine: Routine) -> Dict[str, object]:
    steps = (
        db.query(RoutineStep)
        .filter(RoutineStep.routine_id == routine.id)
        .order_by(RoutineStep.order_index.asc())
        .all()
    )
    return {
        "id": routine.id,
        "name": routine.name,
        "description": routine.description,
        "when_to_run": routine.when_to_run,
        "estimated_minutes": routine.estimated_minutes,
        "is_active": routine.is_active,
        "steps": [
            {
                "id": s.id,
                "order_index": s.order_index,
                "text": s.text,
                "expected_minutes": s.expected_minutes,
                "habit_id": s.habit_id,
            }
            for s in steps
        ],
        "created_at": routine.created_at.isoformat() if routine.created_at else None,
    }


def _serialize_routine_run(row: RoutineRun) -> Dict[str, object]:
    return {
        "id": row.id,
        "routine_id": row.routine_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "duration_minutes": row.duration_minutes,
        "completed_steps": row.completed_steps,
        "total_steps": row.total_steps,
        "completion_ratio": (
            round(row.completed_steps / row.total_steps, 2)
            if row.total_steps else 0.0
        ),
        "notes": row.notes,
    }
