"""
FastAPI router for the Habit Loop & Behavior Tracker.

Mounted from bot.py under /habits/*. Covers habits, check-ins, stacks,
routines, generic behavior events, analytics, and the AI/rule-based coach.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import habit_service
import behavior_tracker
import habit_analytics
import habit_coach
from habit_models import init_habit_models, seed_default_habits, seed_default_routines, HABIT_CATEGORIES, BEHAVIOR_EVENT_TYPES


router = APIRouter(prefix="/habits", tags=["habits"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateHabitRequest(BaseModel):
    user_id: int
    name: str
    description: Optional[str] = None
    category: str = "general"
    cadence: str = "daily"
    frequency_per_week: Optional[int] = None
    interval_days: Optional[int] = None
    target_minutes: Optional[int] = None
    target_count: Optional[int] = None
    unit: Optional[str] = None
    reminder_time: Optional[str] = None
    reminder_enabled: bool = False
    cue: Optional[str] = None
    reward: Optional[str] = None
    motivation: Optional[str] = None
    difficulty: str = "easy"
    is_keystone: bool = False
    icon: Optional[str] = None
    color: Optional[str] = None
    target_streak: Optional[int] = None


class UpdateHabitRequest(BaseModel):
    user_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cadence: Optional[str] = None
    frequency_per_week: Optional[int] = None
    interval_days: Optional[int] = None
    target_minutes: Optional[int] = None
    target_count: Optional[int] = None
    unit: Optional[str] = None
    reminder_time: Optional[str] = None
    reminder_enabled: Optional[bool] = None
    cue: Optional[str] = None
    reward: Optional[str] = None
    motivation: Optional[str] = None
    difficulty: Optional[str] = None
    is_keystone: Optional[bool] = None
    is_archived: Optional[bool] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    target_streak: Optional[int] = None


class CheckInRequest(BaseModel):
    user_id: int
    habit_id: int
    status: str = "done"
    occurred_on: Optional[datetime] = None
    quantity: Optional[float] = None
    duration_minutes: Optional[int] = None
    quality: Optional[float] = None
    notes: Optional[str] = None


class StackRequest(BaseModel):
    user_id: int
    name: str
    anchor_habit_id: int
    follow_up_habit_ids: List[int] = Field(default_factory=list)
    description: Optional[str] = None


class RoutineStepIn(BaseModel):
    text: str
    expected_minutes: Optional[int] = None
    habit_id: Optional[int] = None


class CreateRoutineRequest(BaseModel):
    user_id: int
    name: str
    steps: List[RoutineStepIn]
    when_to_run: Optional[str] = None
    estimated_minutes: Optional[int] = None
    description: Optional[str] = None


class UpdateRoutineRequest(BaseModel):
    user_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    when_to_run: Optional[str] = None
    estimated_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    steps: Optional[List[RoutineStepIn]] = None


class RoutineRunRequest(BaseModel):
    user_id: int
    routine_id: int
    completed_steps: int
    duration_minutes: Optional[float] = None
    notes: Optional[str] = None


class BehaviorEventRequest(BaseModel):
    user_id: int
    event_type: str
    occurred_at: Optional[datetime] = None
    value: Optional[float] = None
    value_unit: Optional[str] = None
    duration_minutes: Optional[int] = None
    quality: Optional[float] = None
    intensity: Optional[float] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    bedtime: Optional[datetime] = None
    wake_time: Optional[datetime] = None
    awakenings: Optional[int] = None
    dream_summary: Optional[str] = None


class CoachRequest(BaseModel):
    user_id: int
    use_llm: bool = True
    persist: bool = True


# ---------------------------------------------------------------------------
# Init / catalog
# ---------------------------------------------------------------------------

@router.post("/init")
def init_tables() -> Dict[str, object]:
    return init_habit_models()


@router.post("/seed-defaults")
def seed_defaults(user_id: int = Query(...)) -> Dict[str, object]:
    habits = seed_default_habits(user_id)
    routines = seed_default_routines(user_id)
    return {"habits_seeded": habits, "routines_seeded": routines}


@router.get("/catalog/categories")
def list_categories() -> Dict[str, List[str]]:
    return {"categories": HABIT_CATEGORIES}


@router.get("/catalog/event-types")
def list_event_types() -> Dict[str, Dict[str, object]]:
    return {"event_types": BEHAVIOR_EVENT_TYPES}


# ---------------------------------------------------------------------------
# Habit CRUD
# ---------------------------------------------------------------------------

@router.post("")
def create_habit(req: CreateHabitRequest) -> Dict:
    try:
        return {"habit": habit_service.create_habit(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{habit_id}")
def update_habit(habit_id: int, req: UpdateHabitRequest) -> Dict:
    payload = req.model_dump(exclude_none=True)
    user_id = payload.pop("user_id")
    try:
        return {"habit": habit_service.update_habit(user_id=user_id, habit_id=habit_id, **payload)}
    except LookupError:
        raise HTTPException(status_code=404, detail="Habit not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{habit_id}")
def delete_habit(habit_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_service.delete_habit(user_id=user_id, habit_id=habit_id):
        raise HTTPException(status_code=404, detail="Habit not found")
    return {"deleted": True}


@router.post("/{habit_id}/archive")
def archive_habit(habit_id: int, user_id: int = Query(...), archived: bool = Query(True)) -> Dict[str, bool]:
    if not habit_service.archive_habit(user_id=user_id, habit_id=habit_id, archived=archived):
        raise HTTPException(status_code=404, detail="Habit not found")
    return {"archived": archived}


@router.get("/{habit_id}")
def get_habit(habit_id: int, user_id: int = Query(...)) -> Dict:
    habit = habit_service.get_habit(user_id=user_id, habit_id=habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return {"habit": habit}


@router.get("")
def list_habits(
    user_id: int = Query(...),
    include_archived: bool = Query(False),
    category: Optional[str] = Query(None),
) -> Dict:
    return {
        "habits": habit_service.list_habits(
            user_id=user_id,
            include_archived=include_archived,
            category=category,
        )
    }


@router.get("/due/today")
def due_today(user_id: int = Query(...)) -> Dict:
    return {"habits": habit_service.habits_due_today(user_id=user_id)}


# ---------------------------------------------------------------------------
# Check-ins
# ---------------------------------------------------------------------------

@router.post("/check-ins")
def post_check_in(req: CheckInRequest) -> Dict:
    try:
        return {
            "check_in": habit_service.check_in(
                user_id=req.user_id,
                habit_id=req.habit_id,
                occurred_on=req.occurred_on,
                status=req.status,
                quantity=req.quantity,
                duration_minutes=req.duration_minutes,
                quality=req.quality,
                notes=req.notes,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Habit not found")


@router.delete("/check-ins/{check_in_id}")
def remove_check_in(check_in_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_service.delete_check_in(user_id=user_id, check_in_id=check_in_id):
        raise HTTPException(status_code=404, detail="Check-in not found")
    return {"deleted": True}


@router.get("/check-ins")
def get_check_ins(
    user_id: int = Query(...),
    habit_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
) -> Dict:
    return {
        "check_ins": habit_service.list_check_ins(
            user_id=user_id, habit_id=habit_id, days=days, limit=limit
        )
    }


# ---------------------------------------------------------------------------
# Stacks
# ---------------------------------------------------------------------------

@router.post("/stacks")
def post_stack(req: StackRequest) -> Dict:
    try:
        return {"stack": habit_service.create_stack(**req.model_dump())}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/stacks")
def get_stacks(user_id: int = Query(...)) -> Dict:
    return {"stacks": habit_service.list_stacks(user_id=user_id)}


@router.delete("/stacks/{stack_id}")
def remove_stack(stack_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_service.delete_stack(user_id=user_id, stack_id=stack_id):
        raise HTTPException(status_code=404, detail="Stack not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

@router.post("/routines")
def post_routine(req: CreateRoutineRequest) -> Dict:
    try:
        return {
            "routine": habit_service.create_routine(
                user_id=req.user_id,
                name=req.name,
                steps=[s.model_dump() for s in req.steps],
                when_to_run=req.when_to_run,
                estimated_minutes=req.estimated_minutes,
                description=req.description,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/routines/{routine_id}")
def patch_routine(routine_id: int, req: UpdateRoutineRequest) -> Dict:
    payload = req.model_dump(exclude_none=True)
    user_id = payload.pop("user_id")
    if "steps" in payload:
        payload["steps"] = [
            s if isinstance(s, dict) else s.model_dump() for s in payload["steps"]
        ]
    try:
        return {
            "routine": habit_service.update_routine(
                user_id=user_id, routine_id=routine_id, **payload
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Routine not found")


@router.get("/routines")
def get_routines(user_id: int = Query(...), include_inactive: bool = Query(False)) -> Dict:
    return {"routines": habit_service.list_routines(user_id=user_id, include_inactive=include_inactive)}


@router.get("/routines/{routine_id}")
def get_routine(routine_id: int, user_id: int = Query(...)) -> Dict:
    routine = habit_service.get_routine(user_id=user_id, routine_id=routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"routine": routine}


@router.delete("/routines/{routine_id}")
def remove_routine(routine_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_service.delete_routine(user_id=user_id, routine_id=routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"deleted": True}


@router.post("/routines/runs")
def post_routine_run(req: RoutineRunRequest) -> Dict:
    try:
        return {
            "run": habit_service.record_routine_run(
                user_id=req.user_id,
                routine_id=req.routine_id,
                completed_steps=req.completed_steps,
                duration_minutes=req.duration_minutes,
                notes=req.notes,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Routine not found")


@router.get("/routines/runs")
def get_routine_runs(
    user_id: int = Query(...),
    routine_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
) -> Dict:
    return {
        "runs": habit_service.list_routine_runs(
            user_id=user_id, routine_id=routine_id, days=days
        )
    }


# ---------------------------------------------------------------------------
# Behavior events
# ---------------------------------------------------------------------------

@router.post("/behavior/events")
def post_event(req: BehaviorEventRequest) -> Dict:
    try:
        return {"event": behavior_tracker.log_event(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/behavior/events")
def get_events(
    user_id: int = Query(...),
    event_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
) -> Dict:
    return {
        "events": behavior_tracker.list_events(
            user_id=user_id, event_type=event_type, days=days, limit=limit
        )
    }


@router.delete("/behavior/events/{event_id}")
def remove_event(event_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not behavior_tracker.delete_event(user_id=user_id, event_id=event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True}


@router.get("/behavior/sleep/summary")
def sleep_summary(user_id: int = Query(...), days: int = Query(14, ge=1, le=180)) -> Dict:
    return behavior_tracker.sleep_summary(user_id=user_id, days=days)


@router.get("/behavior/sleep/dreams")
def sleep_dreams(user_id: int = Query(...), days: int = Query(30, ge=1, le=180)) -> Dict:
    return {"dreams": behavior_tracker.dream_log(user_id=user_id, days=days)}


@router.get("/behavior/totals")
def daily_totals(user_id: int = Query(...), event_type: str = Query(...), days: int = Query(30, ge=1, le=180)) -> Dict:
    return {"per_day": behavior_tracker.daily_totals(user_id=user_id, event_type=event_type, days=days)}


@router.get("/behavior/averages")
def behavior_averages(user_id: int = Query(...), days: int = Query(30, ge=1, le=180)) -> Dict:
    return {"averages": behavior_tracker.average_by_type(user_id=user_id, days=days)}


@router.get("/behavior/snapshot")
def behavior_snapshot(user_id: int = Query(...), target: Optional[str] = Query(None)) -> Dict:
    target_date = None
    if target:
        try:
            target_date = datetime.fromisoformat(target).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return behavior_tracker.daily_snapshot(user_id=user_id, target_date=target_date)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/health")
def analytics_health(user_id: int = Query(...), days: int = Query(14, ge=7, le=180)) -> Dict:
    h = habit_analytics.habit_health(user_id=user_id, days=days)
    return {
        "score": h.score,
        "label": h.label,
        "completion_rate": h.completion_rate,
        "streak_rate": h.streak_rate,
        "diversity": h.diversity,
        "components": h.components,
        "window_days": h.window_days,
    }


@router.get("/analytics/grid")
def analytics_grid(user_id: int = Query(...), days: int = Query(30, ge=7, le=180)) -> Dict:
    return habit_analytics.completion_grid(user_id=user_id, days=days)


@router.get("/analytics/weekly-compliance")
def analytics_weekly(user_id: int = Query(...), weeks: int = Query(8, ge=1, le=52)) -> Dict:
    return habit_analytics.weekly_compliance(user_id=user_id, weeks=weeks)


@router.get("/analytics/window")
def analytics_window(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return habit_analytics.best_check_in_window(user_id=user_id, days=days)


@router.get("/analytics/correlation/{habit_id}")
def analytics_correlation(habit_id: int, user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return habit_analytics.habit_vs_mood_correlation(user_id=user_id, habit_id=habit_id, days=days)


@router.get("/analytics/routines")
def analytics_routines(user_id: int = Query(...), days: int = Query(30, ge=7, le=180)) -> Dict:
    return {"routines": habit_analytics.routine_adherence(user_id=user_id, days=days)}


@router.get("/analytics/alignment")
def analytics_alignment(user_id: int = Query(...), days: int = Query(14, ge=7, le=180)) -> Dict:
    return habit_analytics.behavior_alignment(user_id=user_id, days=days)


# ---------------------------------------------------------------------------
# Coach
# ---------------------------------------------------------------------------

@router.post("/coach/generate")
def coach_generate(req: CoachRequest) -> Dict:
    return {
        "notes": habit_coach.generate_coaching(
            user_id=req.user_id, use_llm=req.use_llm, persist=req.persist
        )
    }


@router.get("/coach/notes")
def coach_notes(
    user_id: int = Query(...),
    include_dismissed: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
) -> Dict:
    return {
        "notes": habit_coach.list_coach_notes(
            user_id=user_id, include_dismissed=include_dismissed, limit=limit
        )
    }


@router.post("/coach/notes/{note_id}/dismiss")
def coach_dismiss(note_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_coach.dismiss_coach_note(user_id=user_id, note_id=note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"dismissed": True}


@router.delete("/coach/notes/{note_id}")
def coach_delete(note_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not habit_coach.delete_coach_note(user_id=user_id, note_id=note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": True}
