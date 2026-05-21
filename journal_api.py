"""
FastAPI router for the Mindful Journal & Reflection System.

Exposes routes for journal CRUD, tagging, prompts, gratitude, mindfulness
sessions and technique catalog, AI reflections, and cross-cutting analytics.

The router is mounted from bot.py so existing endpoints are untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import journal_service
import gratitude_service
import mindfulness_service
import reflection_generator
import journal_analytics
from journal_models import init_journal_models


router = APIRouter(prefix="/journal", tags=["journal"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateEntryRequest(BaseModel):
    user_id: int
    title: Optional[str] = None
    body: str
    mood_score: Optional[float] = None
    energy_level: Optional[float] = None
    stress_level: Optional[float] = None
    prompt_id: Optional[int] = None
    entry_type: str = "free_form"
    location: Optional[str] = None
    weather: Optional[str] = None
    tags: Optional[List[str]] = None
    is_draft: bool = False


class UpdateEntryRequest(BaseModel):
    user_id: int
    title: Optional[str] = None
    body: Optional[str] = None
    mood_score: Optional[float] = None
    energy_level: Optional[float] = None
    stress_level: Optional[float] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    is_draft: Optional[bool] = None
    tags: Optional[List[str]] = None


class EntryResponse(BaseModel):
    entry: Dict


class EntriesResponse(BaseModel):
    entries: List[Dict]


class GratitudeRequest(BaseModel):
    user_id: int
    content: str
    category: Optional[str] = None
    intensity: float = 3.0
    related_person: Optional[str] = None
    related_event: Optional[str] = None


class GratitudeBatchRequest(BaseModel):
    user_id: int
    items: List[str] = Field(default_factory=list)


class SessionRequest(BaseModel):
    user_id: int
    technique: str
    duration_seconds: int
    pre_mood: Optional[float] = None
    post_mood: Optional[float] = None
    perceived_calm: Optional[float] = None
    notes: Optional[str] = None
    interrupted: bool = False
    background_sound: Optional[str] = None
    completed: bool = True


class SessionFeedbackRequest(BaseModel):
    user_id: int
    session_id: int
    post_mood: Optional[float] = None
    perceived_calm: Optional[float] = None
    notes: Optional[str] = None


class GenerateReflectionRequest(BaseModel):
    user_id: int
    window_kind: str = "weekly"
    use_llm: bool = True


class ReflectionFeedbackRequest(BaseModel):
    user_id: int
    snapshot_id: int
    accuracy_rating: Optional[float] = None
    helpfulness_rating: Optional[float] = None
    comment: Optional[str] = None


class TagRenameRequest(BaseModel):
    user_id: int
    tag_id: int
    new_name: str


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

@router.post("/init")
def init_journal_tables() -> Dict[str, object]:
    """Create journal tables and seed defaults. Idempotent."""
    return init_journal_models()


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

@router.post("/entries", response_model=EntryResponse)
def create_entry(req: CreateEntryRequest) -> EntryResponse:
    try:
        entry = journal_service.create_entry(
            user_id=req.user_id,
            body=req.body,
            title=req.title,
            mood_score=req.mood_score,
            energy_level=req.energy_level,
            stress_level=req.stress_level,
            prompt_id=req.prompt_id,
            entry_type=req.entry_type,
            location=req.location,
            weather=req.weather,
            tags=req.tags,
            is_draft=req.is_draft,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EntryResponse(entry=entry)


@router.patch("/entries/{entry_id}", response_model=EntryResponse)
def update_entry(entry_id: int, req: UpdateEntryRequest) -> EntryResponse:
    try:
        entry = journal_service.update_entry(
            user_id=req.user_id,
            entry_id=entry_id,
            title=req.title,
            body=req.body,
            mood_score=req.mood_score,
            energy_level=req.energy_level,
            stress_level=req.stress_level,
            is_favorite=req.is_favorite,
            is_archived=req.is_archived,
            is_draft=req.is_draft,
            tags=req.tags,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Entry not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EntryResponse(entry=entry)


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    deleted = journal_service.delete_entry(user_id=user_id, entry_id=entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}


@router.get("/entries/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: int, user_id: int = Query(...)) -> EntryResponse:
    entry = journal_service.get_entry(user_id=user_id, entry_id=entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return EntryResponse(entry=entry)


@router.get("/entries", response_model=EntriesResponse)
def list_entries(
    user_id: int = Query(...),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False),
    include_drafts: bool = Query(True),
    tag: Optional[str] = Query(None),
    favorites_only: bool = Query(False),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
) -> EntriesResponse:
    entries = journal_service.list_entries(
        user_id=user_id,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        include_drafts=include_drafts,
        tag=tag,
        favorites_only=favorites_only,
        start_date=start_date,
        end_date=end_date,
    )
    return EntriesResponse(entries=entries)


@router.get("/entries/search/q", response_model=EntriesResponse)
def search_entries(user_id: int = Query(...), q: str = Query(...)) -> EntriesResponse:
    entries = journal_service.search_entries(user_id=user_id, query=q)
    return EntriesResponse(entries=entries)


@router.get("/entries/stats/summary")
def entry_stats(user_id: int = Query(...), days: int = Query(30, ge=1, le=365)) -> Dict:
    return journal_service.entry_stats(user_id=user_id, days=days)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@router.get("/tags")
def list_tags(user_id: int = Query(...)) -> Dict:
    return {"tags": journal_service.list_tags(user_id=user_id)}


@router.post("/tags/rename")
def rename_tag(req: TagRenameRequest) -> Dict[str, bool]:
    ok = journal_service.rename_tag(user_id=req.user_id, tag_id=req.tag_id, new_name=req.new_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"renamed": True}


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    ok = journal_service.delete_tag(user_id=user_id, tag_id=tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@router.get("/prompts")
def list_prompts(category: Optional[str] = Query(None)) -> Dict:
    return {"prompts": journal_service.list_prompts(category=category)}


@router.get("/prompts/suggest")
def suggest_prompts(
    mood_score: Optional[float] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
) -> Dict:
    return {
        "prompts": journal_service.suggest_prompts(
            mood_score=mood_score, category=category, limit=limit
        )
    }


@router.get("/prompts/random")
def random_prompt(mood_score: Optional[float] = Query(None)) -> Dict:
    prompt = journal_service.random_prompt(mood_score=mood_score)
    if not prompt:
        raise HTTPException(status_code=404, detail="No prompts available")
    return {"prompt": prompt}


# ---------------------------------------------------------------------------
# Gratitude
# ---------------------------------------------------------------------------

@router.post("/gratitude")
def add_gratitude(req: GratitudeRequest) -> Dict:
    try:
        return {
            "entry": gratitude_service.add_gratitude(
                user_id=req.user_id,
                content=req.content,
                category=req.category,
                intensity=req.intensity,
                related_person=req.related_person,
                related_event=req.related_event,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/gratitude/batch")
def add_gratitude_batch(req: GratitudeBatchRequest) -> Dict:
    items = gratitude_service.add_gratitude_batch(req.user_id, req.items)
    return {"created": items}


@router.get("/gratitude")
def list_gratitude(
    user_id: int = Query(...),
    limit: int = Query(50, ge=1, le=200),
    days: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
) -> Dict:
    return {
        "entries": gratitude_service.list_gratitude(
            user_id=user_id, limit=limit, days=days, category=category
        )
    }


@router.delete("/gratitude/{entry_id}")
def delete_gratitude(entry_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    ok = gratitude_service.delete_gratitude(user_id=user_id, entry_id=entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Gratitude not found")
    return {"deleted": True}


@router.get("/gratitude/streak")
def get_streak(user_id: int = Query(...)) -> Dict:
    summary = gratitude_service.get_streak(user_id=user_id)
    return {
        "current_streak": summary.current_streak,
        "longest_streak": summary.longest_streak,
        "total_entries": summary.total_entries,
        "last_entry_date": summary.last_entry_date,
    }


@router.get("/gratitude/breakdown")
def gratitude_breakdown(user_id: int = Query(...), days: int = Query(30, ge=1, le=365)) -> Dict:
    return gratitude_service.gratitude_breakdown(user_id=user_id, days=days)


@router.get("/gratitude/suggested-categories")
def suggested_categories(user_id: int = Query(...)) -> Dict:
    return {"categories": gratitude_service.suggest_categories_for_user(user_id=user_id)}


@router.get("/gratitude/today")
def gratitude_today(user_id: int = Query(...)) -> Dict[str, bool]:
    return {"completed_today": gratitude_service.gratitude_completion_today(user_id=user_id)}


# ---------------------------------------------------------------------------
# Mindfulness
# ---------------------------------------------------------------------------

@router.post("/mindfulness/sessions")
def record_session(req: SessionRequest) -> Dict:
    try:
        return {
            "session": mindfulness_service.record_session(
                user_id=req.user_id,
                technique=req.technique,
                duration_seconds=req.duration_seconds,
                pre_mood=req.pre_mood,
                post_mood=req.post_mood,
                perceived_calm=req.perceived_calm,
                notes=req.notes,
                interrupted=req.interrupted,
                background_sound=req.background_sound,
                completed=req.completed,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/mindfulness/sessions")
def list_sessions(
    user_id: int = Query(...),
    limit: int = Query(50, ge=1, le=200),
    days: Optional[int] = Query(None),
    technique: Optional[str] = Query(None),
) -> Dict:
    return {
        "sessions": mindfulness_service.list_sessions(
            user_id=user_id, limit=limit, days=days, technique=technique
        )
    }


@router.get("/mindfulness/sessions/{session_id}")
def get_session(session_id: int, user_id: int = Query(...)) -> Dict:
    session = mindfulness_service.get_session(user_id=user_id, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.delete("/mindfulness/sessions/{session_id}")
def delete_session(session_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    ok = mindfulness_service.delete_session(user_id=user_id, session_id=session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


@router.post("/mindfulness/sessions/feedback")
def session_feedback(req: SessionFeedbackRequest) -> Dict:
    updated = mindfulness_service.update_session_feedback(
        user_id=req.user_id,
        session_id=req.session_id,
        post_mood=req.post_mood,
        perceived_calm=req.perceived_calm,
        notes=req.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": updated}


@router.get("/mindfulness/techniques")
def list_techniques(category: Optional[str] = Query(None)) -> Dict:
    return {"techniques": mindfulness_service.list_techniques(category=category)}


@router.get("/mindfulness/techniques/{key}")
def get_technique(key: str) -> Dict:
    technique = mindfulness_service.get_technique(key=key)
    if not technique:
        raise HTTPException(status_code=404, detail="Technique not found")
    return {"technique": technique}


@router.get("/mindfulness/recommend")
def recommend_technique(
    user_id: int = Query(...),
    mood_score: Optional[float] = Query(None),
    available_minutes: int = Query(10, ge=1, le=120),
) -> Dict:
    technique = mindfulness_service.recommend_technique(
        user_id=user_id,
        mood_score=mood_score,
        available_minutes=available_minutes,
    )
    if not technique:
        raise HTTPException(status_code=404, detail="No technique fits the constraints")
    return {"technique": technique}


@router.get("/mindfulness/summary")
def mindfulness_summary(user_id: int = Query(...), days: int = Query(30, ge=1, le=365)) -> Dict:
    summary = mindfulness_service.practice_summary(user_id=user_id, days=days)
    return {
        "total_sessions": summary.total_sessions,
        "total_minutes": summary.total_minutes,
        "average_duration": summary.average_duration,
        "completion_rate": summary.completion_rate,
        "favorite_technique": summary.favorite_technique,
        "average_calm": summary.average_calm,
        "average_mood_delta": summary.average_mood_delta,
    }


@router.get("/mindfulness/streak")
def mindfulness_streak(user_id: int = Query(...)) -> Dict:
    return mindfulness_service.session_streak(user_id=user_id)


@router.get("/mindfulness/effectiveness")
def mindfulness_effectiveness(user_id: int = Query(...)) -> Dict:
    return {"techniques": mindfulness_service.technique_effectiveness(user_id=user_id)}


@router.get("/mindfulness/best-time")
def best_time(user_id: int = Query(...)) -> Dict:
    return {"best_time_of_day": mindfulness_service.best_time_of_day(user_id=user_id)}


# ---------------------------------------------------------------------------
# Reflections
# ---------------------------------------------------------------------------

@router.post("/reflections/generate")
def generate_reflection(req: GenerateReflectionRequest) -> Dict:
    try:
        reflection = reflection_generator.generate_reflection(
            user_id=req.user_id,
            window_kind=req.window_kind,
            use_llm=req.use_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"reflection": reflection}


@router.get("/reflections")
def list_reflections(
    user_id: int = Query(...),
    limit: int = Query(10, ge=1, le=100),
    window_kind: Optional[str] = Query(None),
) -> Dict:
    return {
        "reflections": reflection_generator.list_reflections(
            user_id=user_id, limit=limit, window_kind=window_kind
        )
    }


@router.get("/reflections/{snapshot_id}")
def get_reflection(snapshot_id: int, user_id: int = Query(...)) -> Dict:
    reflection = reflection_generator.get_reflection(user_id=user_id, snapshot_id=snapshot_id)
    if not reflection:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return {"reflection": reflection}


@router.post("/reflections/feedback")
def reflection_feedback(req: ReflectionFeedbackRequest) -> Dict:
    return {
        "feedback": reflection_generator.record_feedback(
            user_id=req.user_id,
            snapshot_id=req.snapshot_id,
            accuracy_rating=req.accuracy_rating,
            helpfulness_rating=req.helpfulness_rating,
            comment=req.comment,
        )
    }


# ---------------------------------------------------------------------------
# Cross-cutting analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/wellbeing")
def wellbeing(user_id: int = Query(...), days: int = Query(14, ge=1, le=180)) -> Dict:
    score = journal_analytics.compute_wellbeing(user_id=user_id, days=days)
    return {
        "score": score.score,
        "components": score.components,
        "label": score.label,
        "window_days": score.window_days,
    }


@router.get("/analytics/heatmap")
def heatmap(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return journal_analytics.activity_heatmap(user_id=user_id, days=days)


@router.get("/analytics/correlation")
def correlation(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return journal_analytics.mood_practice_correlation(user_id=user_id, days=days)


@router.get("/analytics/daily")
def daily_digest(user_id: int = Query(...), target: Optional[str] = Query(None)) -> Dict:
    target_date = None
    if target:
        try:
            target_date = datetime.fromisoformat(target).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return journal_analytics.daily_digest(user_id=user_id, target_date=target_date)


@router.get("/analytics/weekly")
def weekly_digest(user_id: int = Query(...)) -> Dict:
    return journal_analytics.weekly_digest(user_id=user_id)


@router.get("/analytics/consistency")
def consistency(user_id: int = Query(...), days: int = Query(30, ge=7, le=180)) -> Dict:
    return journal_analytics.writing_consistency(user_id=user_id, days=days)
