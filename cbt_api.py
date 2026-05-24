"""
FastAPI router for the CBT Workbook & Cognitive Restructuring System.

Mounted from bot.py under /cbt/*. Covers thought records, distortions,
worry trees, behavioral experiments, activity scheduling (BA), core
beliefs, worksheet catalog, the reframer, and analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import thought_record_service
import cbt_distortion_analyzer
import cbt_worksheets
import cbt_analytics
import cbt_reframer
from cbt_models import init_cbt_models


router = APIRouter(prefix="/cbt", tags=["cbt"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateThoughtRecordRequest(BaseModel):
    user_id: int
    situation: str
    automatic_thought: str
    hot_thought: Optional[str] = None
    primary_emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    secondary_emotions: Optional[List[str]] = None
    body_sensations: Optional[str] = None
    behavior_response: Optional[str] = None
    belief_in_original_thought: Optional[float] = None
    occurred_at: Optional[datetime] = None
    auto_detect_distortions: bool = True


class CompleteThoughtRecordRequest(BaseModel):
    user_id: int
    evidence_for: Optional[str] = None
    evidence_against: Optional[str] = None
    alternative_view: Optional[str] = None
    balanced_thought: Optional[str] = None
    new_emotion_intensity: Optional[float] = None
    new_behavior_plan: Optional[str] = None
    belief_in_balanced_thought: Optional[float] = None
    confidence_in_reframe: Optional[float] = None


class UpdateThoughtRecordRequest(BaseModel):
    user_id: int
    situation: Optional[str] = None
    automatic_thought: Optional[str] = None
    hot_thought: Optional[str] = None
    primary_emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    secondary_emotions: Optional[List[str]] = None
    body_sensations: Optional[str] = None
    behavior_response: Optional[str] = None
    evidence_for: Optional[str] = None
    evidence_against: Optional[str] = None
    alternative_view: Optional[str] = None
    balanced_thought: Optional[str] = None
    new_emotion_intensity: Optional[float] = None
    new_behavior_plan: Optional[str] = None
    belief_in_original_thought: Optional[float] = None
    belief_in_balanced_thought: Optional[float] = None
    confidence_in_reframe: Optional[float] = None


class AttachDistortionRequest(BaseModel):
    user_id: int
    distortion_id: int
    confidence: float = 1.0
    auto_detected: bool = False


class DetectDistortionsRequest(BaseModel):
    text: str
    top_n: int = 5


class CreateWorryRequest(BaseModel):
    user_id: int
    worry: str
    what_am_i_worried_about: Optional[str] = None
    worry_intensity_before: Optional[float] = None


class ClassifyWorryRequest(BaseModel):
    user_id: int
    is_solvable: bool
    classification_reasoning: Optional[str] = None


class PlanWorryRequest(BaseModel):
    user_id: int
    action_step: Optional[str] = None
    when_to_act: Optional[str] = None
    obstacle_plan: Optional[str] = None
    let_go_strategy: Optional[str] = None
    accept_reframe: Optional[str] = None
    self_soothing_plan: Optional[str] = None


class FinishWorryRequest(BaseModel):
    user_id: int
    worry_intensity_after: Optional[float] = None


class CreateExperimentRequest(BaseModel):
    user_id: int
    target_belief: str
    prediction: str
    experiment_design: str
    belief_strength_before: Optional[float] = None
    prediction_confidence: Optional[float] = None
    safety_behaviors_to_drop: Optional[str] = None
    coping_plan_if_distressing: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class RecordExperimentOutcomeRequest(BaseModel):
    user_id: int
    actual_outcome: str
    surprise_factor: Optional[float] = None
    belief_strength_after: Optional[float] = None
    learning_summary: Optional[str] = None
    next_experiment_idea: Optional[str] = None


class ExperimentStatusRequest(BaseModel):
    user_id: int
    status: str


class ScheduleActivityRequest(BaseModel):
    user_id: int
    title: str
    scheduled_for: datetime
    category: str = "general"
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_pleasure_activity: bool = True
    is_mastery_activity: bool = False


class CompleteActivityRequest(BaseModel):
    user_id: int
    pleasure_rating: Optional[float] = None
    mastery_rating: Optional[float] = None
    energy_after: Optional[float] = None
    notes: Optional[str] = None


class SkipActivityRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None


class CoreBeliefRequest(BaseModel):
    user_id: int
    statement: str
    category: Optional[str] = None
    valence: str = "negative"
    alternative_belief: Optional[str] = None


class UpdateCoreBeliefRequest(BaseModel):
    user_id: int
    statement: Optional[str] = None
    category: Optional[str] = None
    alternative_belief: Optional[str] = None
    is_active: Optional[bool] = None


class RateBeliefRequest(BaseModel):
    user_id: int
    strength: float
    alternative_strength: Optional[float] = None
    note: Optional[str] = None


class ReframerRequest(BaseModel):
    automatic_thought: str
    situation: Optional[str] = None
    primary_emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    distortion_keys: Optional[List[str]] = None
    use_llm: bool = True


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

@router.post("/init")
def init_tables() -> Dict[str, object]:
    return init_cbt_models()


# ---------------------------------------------------------------------------
# Thought records
# ---------------------------------------------------------------------------

@router.post("/thought-records")
def create_record(req: CreateThoughtRecordRequest) -> Dict:
    payload = req.model_dump(exclude={"auto_detect_distortions"})
    try:
        record = thought_record_service.create_record(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if req.auto_detect_distortions:
        try:
            cbt_distortion_analyzer.auto_tag_record(record["id"], req.automatic_thought)
            record = thought_record_service.get_record(req.user_id, record["id"]) or record
        except Exception:
            pass
    return {"record": record}


@router.post("/thought-records/{record_id}/complete")
def complete_record(record_id: int, req: CompleteThoughtRecordRequest) -> Dict:
    payload = req.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        return {
            "record": thought_record_service.complete_record(
                user_id=req.user_id, record_id=record_id, **payload
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Thought record not found")


@router.patch("/thought-records/{record_id}")
def update_record(record_id: int, req: UpdateThoughtRecordRequest) -> Dict:
    payload = req.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        return {
            "record": thought_record_service.update_record(
                user_id=req.user_id, record_id=record_id, **payload
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Thought record not found")


@router.delete("/thought-records/{record_id}")
def delete_record(record_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not thought_record_service.delete_record(user_id=user_id, record_id=record_id):
        raise HTTPException(status_code=404, detail="Thought record not found")
    return {"deleted": True}


@router.get("/thought-records/{record_id}")
def get_record(record_id: int, user_id: int = Query(...)) -> Dict:
    record = thought_record_service.get_record(user_id=user_id, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Thought record not found")
    return {"record": record}


@router.get("/thought-records")
def list_records(
    user_id: int = Query(...),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_complete: Optional[bool] = Query(None),
    primary_emotion: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
) -> Dict:
    return {
        "records": thought_record_service.list_records(
            user_id=user_id,
            limit=limit,
            offset=offset,
            is_complete=is_complete,
            primary_emotion=primary_emotion,
            start_date=start_date,
            end_date=end_date,
        )
    }


@router.get("/thought-records/search/q")
def search_records(user_id: int = Query(...), q: str = Query(...)) -> Dict:
    return {"records": thought_record_service.search_records(user_id=user_id, query=q)}


# ---------------------------------------------------------------------------
# Distortions
# ---------------------------------------------------------------------------

@router.get("/distortions/catalog")
def list_catalog() -> Dict:
    return {"distortions": thought_record_service.list_distortion_catalog()}


@router.post("/distortions/detect")
def detect(req: DetectDistortionsRequest) -> Dict:
    return {"detected": cbt_distortion_analyzer.detect_for_thought(req.text, top_n=req.top_n)}


@router.post("/thought-records/{record_id}/distortions")
def attach_distortion(record_id: int, req: AttachDistortionRequest) -> Dict:
    try:
        return {
            "link": thought_record_service.attach_distortion(
                user_id=req.user_id,
                record_id=record_id,
                distortion_id=req.distortion_id,
                confidence=req.confidence,
                auto_detected=req.auto_detected,
            )
        }
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/thought-records/{record_id}/distortions/{distortion_id}")
def detach_distortion(record_id: int, distortion_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    ok = thought_record_service.detach_distortion(
        user_id=user_id, record_id=record_id, distortion_id=distortion_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"detached": True}


@router.get("/thought-records/{record_id}/distortions")
def list_record_distortions(record_id: int) -> Dict:
    return {"distortions": thought_record_service.list_distortions_for_record(record_id)}


# ---------------------------------------------------------------------------
# Worry trees
# ---------------------------------------------------------------------------

@router.post("/worries")
def create_worry(req: CreateWorryRequest) -> Dict:
    try:
        return {"worry": cbt_worksheets.create_worry(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/worries/{worry_id}/classify")
def classify_worry(worry_id: int, req: ClassifyWorryRequest) -> Dict:
    try:
        return {
            "worry": cbt_worksheets.classify_worry(
                user_id=req.user_id,
                worry_id=worry_id,
                is_solvable=req.is_solvable,
                classification_reasoning=req.classification_reasoning,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Worry not found")


@router.post("/worries/{worry_id}/plan")
def plan_worry(worry_id: int, req: PlanWorryRequest) -> Dict:
    try:
        if req.action_step is not None or req.when_to_act is not None or req.obstacle_plan is not None:
            row = cbt_worksheets.plan_solvable_branch(
                user_id=req.user_id,
                worry_id=worry_id,
                action_step=req.action_step or "",
                when_to_act=req.when_to_act,
                obstacle_plan=req.obstacle_plan,
            )
            return {"worry": row}
        if req.let_go_strategy:
            row = cbt_worksheets.plan_unsolvable_branch(
                user_id=req.user_id,
                worry_id=worry_id,
                let_go_strategy=req.let_go_strategy,
                accept_reframe=req.accept_reframe,
                self_soothing_plan=req.self_soothing_plan,
            )
            return {"worry": row}
        raise HTTPException(status_code=400, detail="Provide either an action plan or a let-go strategy.")
    except LookupError:
        raise HTTPException(status_code=404, detail="Worry not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/worries/{worry_id}/finish")
def finish_worry(worry_id: int, req: FinishWorryRequest) -> Dict:
    try:
        return {
            "worry": cbt_worksheets.finish_worry(
                user_id=req.user_id,
                worry_id=worry_id,
                worry_intensity_after=req.worry_intensity_after,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Worry not found")


@router.get("/worries")
def list_worries(
    user_id: int = Query(...),
    limit: int = Query(30, ge=1, le=200),
    only_open: bool = Query(False),
) -> Dict:
    return {"worries": cbt_worksheets.list_worries(user_id=user_id, limit=limit, only_open=only_open)}


@router.get("/worries/{worry_id}")
def get_worry(worry_id: int, user_id: int = Query(...)) -> Dict:
    worry = cbt_worksheets.get_worry(user_id=user_id, worry_id=worry_id)
    if not worry:
        raise HTTPException(status_code=404, detail="Worry not found")
    return {"worry": worry}


@router.delete("/worries/{worry_id}")
def delete_worry(worry_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not cbt_worksheets.delete_worry(user_id=user_id, worry_id=worry_id):
        raise HTTPException(status_code=404, detail="Worry not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Behavioral experiments
# ---------------------------------------------------------------------------

@router.post("/experiments")
def create_experiment(req: CreateExperimentRequest) -> Dict:
    try:
        return {"experiment": cbt_worksheets.create_experiment(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/experiments/{experiment_id}/outcome")
def record_outcome(experiment_id: int, req: RecordExperimentOutcomeRequest) -> Dict:
    try:
        return {
            "experiment": cbt_worksheets.record_experiment_outcome(
                user_id=req.user_id,
                experiment_id=experiment_id,
                actual_outcome=req.actual_outcome,
                surprise_factor=req.surprise_factor,
                belief_strength_after=req.belief_strength_after,
                learning_summary=req.learning_summary,
                next_experiment_idea=req.next_experiment_idea,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/experiments/{experiment_id}/status")
def set_experiment_status(experiment_id: int, req: ExperimentStatusRequest) -> Dict:
    try:
        return {
            "experiment": cbt_worksheets.update_experiment_status(
                user_id=req.user_id, experiment_id=experiment_id, status=req.status
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Experiment not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/experiments")
def list_experiments(
    user_id: int = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
) -> Dict:
    return {
        "experiments": cbt_worksheets.list_experiments(
            user_id=user_id, status=status, limit=limit
        )
    }


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, user_id: int = Query(...)) -> Dict:
    exp = cbt_worksheets.get_experiment(user_id=user_id, experiment_id=experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"experiment": exp}


@router.delete("/experiments/{experiment_id}")
def delete_experiment(experiment_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not cbt_worksheets.delete_experiment(user_id=user_id, experiment_id=experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Activity scheduling
# ---------------------------------------------------------------------------

@router.post("/activities")
def schedule_activity(req: ScheduleActivityRequest) -> Dict:
    try:
        return {"activity": cbt_worksheets.schedule_activity(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/activities/{activity_id}/complete")
def complete_activity(activity_id: int, req: CompleteActivityRequest) -> Dict:
    try:
        return {
            "activity": cbt_worksheets.complete_activity(
                user_id=req.user_id,
                activity_id=activity_id,
                pleasure_rating=req.pleasure_rating,
                mastery_rating=req.mastery_rating,
                energy_after=req.energy_after,
                notes=req.notes,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Activity not found")


@router.post("/activities/{activity_id}/skip")
def skip_activity(activity_id: int, req: SkipActivityRequest) -> Dict:
    try:
        return {
            "activity": cbt_worksheets.skip_activity(
                user_id=req.user_id, activity_id=activity_id, reason=req.reason
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Activity not found")


@router.get("/activities")
def list_activities(
    user_id: int = Query(...),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    completed: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> Dict:
    return {
        "activities": cbt_worksheets.list_activities(
            user_id=user_id,
            start=start,
            end=end,
            completed=completed,
            category=category,
            limit=limit,
        )
    }


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not cbt_worksheets.delete_activity(user_id=user_id, activity_id=activity_id):
        raise HTTPException(status_code=404, detail="Activity not found")
    return {"deleted": True}


@router.get("/activities/suggest/from-history")
def activity_suggestions(
    user_id: int = Query(...),
    mood_score: Optional[float] = Query(None),
    limit: int = Query(5, ge=1, le=20),
) -> Dict:
    return {
        "suggestions": cbt_worksheets.suggest_activities(
            user_id=user_id, mood_score=mood_score, limit=limit
        )
    }


# ---------------------------------------------------------------------------
# Core beliefs
# ---------------------------------------------------------------------------

@router.post("/core-beliefs")
def add_belief(req: CoreBeliefRequest) -> Dict:
    try:
        return {"belief": cbt_worksheets.add_core_belief(**req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/core-beliefs/{belief_id}")
def update_belief(belief_id: int, req: UpdateCoreBeliefRequest) -> Dict:
    payload = req.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        return {
            "belief": cbt_worksheets.update_core_belief(
                user_id=req.user_id, belief_id=belief_id, **payload
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Belief not found")


@router.post("/core-beliefs/{belief_id}/rate")
def rate_belief(belief_id: int, req: RateBeliefRequest) -> Dict:
    try:
        return {
            "rating": cbt_worksheets.rate_core_belief(
                user_id=req.user_id,
                belief_id=belief_id,
                strength=req.strength,
                alternative_strength=req.alternative_strength,
                note=req.note,
            )
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="Belief not found")


@router.get("/core-beliefs")
def list_beliefs(
    user_id: int = Query(...), include_inactive: bool = Query(False)
) -> Dict:
    return {
        "beliefs": cbt_worksheets.list_core_beliefs(
            user_id=user_id, include_inactive=include_inactive
        )
    }


@router.get("/core-beliefs/{belief_id}/history")
def belief_history(belief_id: int, user_id: int = Query(...)) -> Dict:
    return {
        "ratings": cbt_worksheets.belief_history(user_id=user_id, belief_id=belief_id)
    }


@router.delete("/core-beliefs/{belief_id}")
def delete_belief(belief_id: int, user_id: int = Query(...)) -> Dict[str, bool]:
    if not cbt_worksheets.delete_core_belief(user_id=user_id, belief_id=belief_id):
        raise HTTPException(status_code=404, detail="Belief not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Worksheet templates
# ---------------------------------------------------------------------------

@router.get("/worksheets")
def list_worksheets(category: Optional[str] = Query(None)) -> Dict:
    return {"templates": cbt_worksheets.list_worksheet_templates(category=category)}


@router.get("/worksheets/{key}")
def get_worksheet(key: str) -> Dict:
    tpl = cbt_worksheets.get_worksheet_template(key)
    if not tpl:
        raise HTTPException(status_code=404, detail="Worksheet not found")
    return {"template": tpl}


# ---------------------------------------------------------------------------
# Reframer
# ---------------------------------------------------------------------------

@router.post("/reframer")
def reframer(req: ReframerRequest) -> Dict:
    return {"suggestions": cbt_reframer.suggest_reframes(**req.model_dump())}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/distortions")
def analytics_distortions(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return {"leaderboard": cbt_analytics.distortion_leaderboard(user_id=user_id, days=days)}


@router.get("/analytics/reframe-success")
def analytics_reframe(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return cbt_analytics.reframe_success(user_id=user_id, days=days)


@router.get("/analytics/worry")
def analytics_worry(user_id: int = Query(...), days: int = Query(60, ge=7, le=365)) -> Dict:
    return cbt_analytics.worry_split(user_id=user_id, days=days)


@router.get("/analytics/experiments")
def analytics_experiments(user_id: int = Query(...), days: int = Query(90, ge=7, le=365)) -> Dict:
    return cbt_analytics.experiment_summary(user_id=user_id, days=days)


@router.get("/analytics/activity")
def analytics_activity(user_id: int = Query(...), days: int = Query(30, ge=7, le=365)) -> Dict:
    return cbt_analytics.activity_balance(user_id=user_id, days=days)


@router.get("/analytics/belief-drift")
def analytics_drift(user_id: int = Query(...), days: int = Query(180, ge=14, le=730)) -> Dict:
    return {"beliefs": cbt_analytics.belief_drift(user_id=user_id, days=days)}


@router.get("/analytics/engagement")
def analytics_engagement(user_id: int = Query(...), days: int = Query(30, ge=7, le=365)) -> Dict:
    score = cbt_analytics.engagement_score(user_id=user_id, days=days)
    return {
        "score": score.score,
        "label": score.label,
        "components": score.components,
        "window_days": score.window_days,
    }


@router.get("/analytics/master-summary")
def analytics_master(user_id: int = Query(...), days: int = Query(30, ge=7, le=365)) -> Dict:
    return cbt_analytics.master_summary(user_id=user_id, days=days)
