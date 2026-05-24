"""
Database models for the CBT Workbook & Cognitive Restructuring System.

Provides the data layer for:
  - Thought records (situation → automatic thought → emotion → evidence
    for/against → balanced thought → new emotion rating)
  - Cognitive distortion catalog + per-record tagging
  - Worry trees (worry → solvable/unsolvable branch → action / let-go plan)
  - Behavioral experiments (predict → test → observe → review)
  - Activity-scheduling entries (planned + completed + pleasure/mastery)
  - Core belief tracking with strength ratings over time
  - Workbook templates the user can pick from
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text

from database import Base, SessionLocal


# ---------------------------------------------------------------------------
# Thought records
# ---------------------------------------------------------------------------

class ThoughtRecord(Base):
    """A single CBT thought record."""
    __tablename__ = "cbt_thought_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    situation = Column(Text, nullable=False)
    automatic_thought = Column(Text, nullable=False)
    hot_thought = Column(Text, nullable=True)

    primary_emotion = Column(String(80), nullable=True, index=True)
    emotion_intensity = Column(Float, nullable=True)
    secondary_emotions = Column(String(500), nullable=True)

    body_sensations = Column(String(1000), nullable=True)
    behavior_response = Column(String(1000), nullable=True)

    evidence_for = Column(Text, nullable=True)
    evidence_against = Column(Text, nullable=True)
    alternative_view = Column(Text, nullable=True)

    balanced_thought = Column(Text, nullable=True)
    new_emotion_intensity = Column(Float, nullable=True)
    new_behavior_plan = Column(Text, nullable=True)

    belief_in_original_thought = Column(Float, nullable=True)  # 0-100 %
    belief_in_balanced_thought = Column(Float, nullable=True)  # 0-100 %

    is_complete = Column(Boolean, default=False, index=True)
    confidence_in_reframe = Column(Float, nullable=True)

    occurred_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CognitiveDistortion(Base):
    """Catalog of cognitive distortions (all-or-nothing, mind reading, etc.)."""
    __tablename__ = "cbt_distortions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(80), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    short_description = Column(String(500), nullable=False)
    example = Column(String(1000), nullable=True)
    detection_keywords = Column(String(1000), nullable=True)
    detection_patterns = Column(String(2000), nullable=True)
    reframe_guidance = Column(Text, nullable=True)
    severity_weight = Column(Float, default=1.0)


class ThoughtRecordDistortion(Base):
    """Many-to-many link: which distortions appear in which records."""
    __tablename__ = "cbt_thought_record_distortions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, nullable=False, index=True)
    distortion_id = Column(Integer, nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    auto_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Worry trees
# ---------------------------------------------------------------------------

class WorryTree(Base):
    """A worry-tree exercise: surface the worry, classify, plan."""
    __tablename__ = "cbt_worry_trees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    worry = Column(Text, nullable=False)
    what_am_i_worried_about = Column(Text, nullable=True)

    is_solvable = Column(Boolean, nullable=True)
    classification_reasoning = Column(Text, nullable=True)

    # Solvable branch
    action_step = Column(Text, nullable=True)
    when_to_act = Column(String(255), nullable=True)
    obstacle_plan = Column(Text, nullable=True)

    # Unsolvable / hypothetical branch
    let_go_strategy = Column(String(500), nullable=True)
    accept_reframe = Column(Text, nullable=True)
    self_soothing_plan = Column(Text, nullable=True)

    worry_intensity_before = Column(Float, nullable=True)
    worry_intensity_after = Column(Float, nullable=True)

    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Behavioral experiments
# ---------------------------------------------------------------------------

class BehavioralExperiment(Base):
    """A behavioral experiment to test a cognition."""
    __tablename__ = "cbt_behavioral_experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    target_belief = Column(Text, nullable=False)
    belief_strength_before = Column(Float, nullable=True)  # 0-100 %
    prediction = Column(Text, nullable=False)
    prediction_confidence = Column(Float, nullable=True)

    experiment_design = Column(Text, nullable=False)
    safety_behaviors_to_drop = Column(Text, nullable=True)
    coping_plan_if_distressing = Column(Text, nullable=True)

    scheduled_for = Column(DateTime, nullable=True)
    conducted_at = Column(DateTime, nullable=True)

    actual_outcome = Column(Text, nullable=True)
    surprise_factor = Column(Float, nullable=True)  # 0-10
    belief_strength_after = Column(Float, nullable=True)
    learning_summary = Column(Text, nullable=True)
    next_experiment_idea = Column(Text, nullable=True)

    status = Column(String(40), default="planned", index=True)  # planned/conducted/reviewed/abandoned
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Activity scheduling (Behavioral Activation)
# ---------------------------------------------------------------------------

class ActivitySchedule(Base):
    """A planned/completed activity for behavioral activation."""
    __tablename__ = "cbt_activity_schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(80), nullable=False, default="general")

    scheduled_for = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=True)

    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    pleasure_rating = Column(Float, nullable=True)  # 0-10
    mastery_rating = Column(Float, nullable=True)   # 0-10
    energy_after = Column(Float, nullable=True)
    notes = Column(String(1000), nullable=True)

    skipped_reason = Column(String(500), nullable=True)
    is_pleasure_activity = Column(Boolean, default=True)
    is_mastery_activity = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Core beliefs
# ---------------------------------------------------------------------------

class CoreBelief(Base):
    """A core belief the user is examining over time."""
    __tablename__ = "cbt_core_beliefs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    statement = Column(String(500), nullable=False)
    category = Column(String(80), nullable=True)  # self / others / world / future
    valence = Column(String(20), nullable=True)   # negative / positive
    is_active = Column(Boolean, default=True)
    alternative_belief = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CoreBeliefRating(Base):
    """A snapshot of how strongly the user holds a core belief."""
    __tablename__ = "cbt_core_belief_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    belief_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    strength = Column(Float, nullable=False)  # 0-100 %
    alternative_strength = Column(Float, nullable=True)
    note = Column(String(1000), nullable=True)
    rated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ---------------------------------------------------------------------------
# Worksheet templates
# ---------------------------------------------------------------------------

class WorksheetTemplate(Base):
    """A reusable CBT worksheet template (e.g. 'Decatastrophizing')."""
    __tablename__ = "cbt_worksheet_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(80), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)
    estimated_minutes = Column(Integer, default=10)
    category = Column(String(80), nullable=False)  # anxiety/depression/anger/grief/general
    difficulty = Column(String(40), default="beginner")


# ---------------------------------------------------------------------------
# Catalog defaults
# ---------------------------------------------------------------------------

DEFAULT_DISTORTIONS: List[Dict[str, object]] = [
    {
        "key": "all_or_nothing",
        "name": "All-or-Nothing Thinking",
        "short_description": (
            "Viewing situations in absolute, black-and-white categories — "
            "if it's not perfect, it's a failure."
        ),
        "example": "I made one mistake, so the whole project is ruined.",
        "detection_keywords": "always,never,completely,totally,perfect,ruined,worthless,useless,nothing,everything",
        "detection_patterns": r"\balways\b|\bnever\b|\bcompletely\b|\bperfect(ly)?\b|\b(no|every)thing\b",
        "reframe_guidance": "Where on the spectrum between 0 and 100 does this actually sit?",
        "severity_weight": 1.2,
    },
    {
        "key": "catastrophizing",
        "name": "Catastrophizing",
        "short_description": "Expecting disaster; blowing the importance of an event out of proportion.",
        "example": "If I fail this interview, my career is over.",
        "detection_keywords": "disaster,ruined,end of the world,terrible,unbearable,never recover,catastrophe",
        "detection_patterns": r"\bdisaster\b|\bruin(ed)?\b|\bend of (the )?world\b|\bcatastrophe\b|\bterrible\b",
        "reframe_guidance": "What's the most realistic outcome? How would you cope if the worst did happen?",
        "severity_weight": 1.3,
    },
    {
        "key": "mind_reading",
        "name": "Mind Reading",
        "short_description": "Assuming you know what others are thinking without evidence.",
        "example": "She didn't text back — she must be angry with me.",
        "detection_keywords": "they think,must think,obviously think,thinks I'm,thinks that I,knows I'm",
        "detection_patterns": r"\b(they|she|he|people) (must|probably|obviously) (think|hate|judge)\b",
        "reframe_guidance": "What other reasons could explain their behavior? Could you ask directly?",
        "severity_weight": 1.0,
    },
    {
        "key": "fortune_telling",
        "name": "Fortune Telling",
        "short_description": "Predicting the future negatively without basis.",
        "example": "I just know I'll mess up this presentation.",
        "detection_keywords": "i know i'll,i'll fail,i'll mess up,i'll never,it'll go wrong,won't work out",
        "detection_patterns": r"\bi(['']?ll| will) (never|fail|mess|definitely)\b|\bwon(['']?)t work out\b",
        "reframe_guidance": "What's your evidence? How often have such predictions been right in the past?",
        "severity_weight": 1.1,
    },
    {
        "key": "emotional_reasoning",
        "name": "Emotional Reasoning",
        "short_description": "Believing something is true because you feel it strongly.",
        "example": "I feel like a fraud, so I must be one.",
        "detection_keywords": "i feel like,it feels true,because i feel,so it must,must mean",
        "detection_patterns": r"\bi feel like (i('|')?m|i am) (a )?[a-z]+\b|\bbecause i feel\b",
        "reframe_guidance": "Feelings are information, not verdicts. What does the evidence say?",
        "severity_weight": 1.1,
    },
    {
        "key": "should_statements",
        "name": "Should Statements",
        "short_description": "Holding yourself or others to rigid rules ('should', 'must', 'have to').",
        "example": "I should be over this by now.",
        "detection_keywords": "should,shouldn't,must,ought to,have to,supposed to",
        "detection_patterns": r"\b(should(n't)?|must|ought to|have to|supposed to)\b",
        "reframe_guidance": "Replace 'should' with 'I'd prefer' or 'It would be helpful if'.",
        "severity_weight": 0.9,
    },
    {
        "key": "labeling",
        "name": "Labeling / Mislabeling",
        "short_description": "Assigning global, fixed labels to yourself or others.",
        "example": "I'm a loser. He's a jerk.",
        "detection_keywords": "i'm a,he's a,she's a,they're all,what a,total,absolute",
        "detection_patterns": r"\bi(['']?)m (a |an )?[a-z]+er\b|\b(loser|idiot|failure|fraud|jerk)\b",
        "reframe_guidance": "Replace the label with a description of behavior, not identity.",
        "severity_weight": 1.2,
    },
    {
        "key": "personalization",
        "name": "Personalization",
        "short_description": "Holding yourself responsible for events outside your control.",
        "example": "My team had a rough month — it's my fault.",
        "detection_keywords": "my fault,because of me,i caused,if i hadn't,blame myself,my responsibility",
        "detection_patterns": r"\b(my fault|because of me|i caused|i('|')?m to blame)\b",
        "reframe_guidance": "List the other factors involved. What share is actually within your control?",
        "severity_weight": 1.1,
    },
    {
        "key": "mental_filter",
        "name": "Mental Filter",
        "short_description": "Dwelling on a single negative detail to the exclusion of the positives.",
        "example": "One person didn't like my talk, so the whole talk was bad.",
        "detection_keywords": "all i can think about,can't stop thinking about,can't get past,only thing",
        "detection_patterns": r"\ball i can think (about|of)\b|\bcan(['']?)t (stop thinking|get past)\b",
        "reframe_guidance": "Widen the lens — what else happened in this situation?",
        "severity_weight": 1.0,
    },
    {
        "key": "discounting_positive",
        "name": "Discounting the Positive",
        "short_description": "Dismissing positive experiences as not counting.",
        "example": "They only complimented me to be polite.",
        "detection_keywords": "doesn't count,just being polite,just luck,anyone could,it was nothing,yeah but",
        "detection_patterns": r"\bdoesn(['']?)t count\b|\bjust (luck|polite|nice)\b|\byeah but\b",
        "reframe_guidance": "If a friend told you about this win, would you dismiss it?",
        "severity_weight": 1.0,
    },
    {
        "key": "magnification_minimization",
        "name": "Magnification / Minimization",
        "short_description": "Exaggerating negatives or shrinking positives.",
        "example": "My mistake is enormous; my success is no big deal.",
        "detection_keywords": "huge mistake,massive failure,minor success,small win,nothing special,big deal",
        "detection_patterns": r"\bhuge (mistake|failure|problem)\b|\bnothing special\b",
        "reframe_guidance": "Use the same scale for negatives and positives.",
        "severity_weight": 1.0,
    },
    {
        "key": "overgeneralization",
        "name": "Overgeneralization",
        "short_description": "Seeing a single negative event as a never-ending pattern.",
        "example": "I bombed one interview, I'll never get hired.",
        "detection_keywords": "always happens,never works,every time,no one ever,everything always",
        "detection_patterns": r"\balways happens\b|\bnever works\b|\bevery (single )?time\b|\bno one ever\b",
        "reframe_guidance": "Is one instance evidence of a permanent rule?",
        "severity_weight": 1.1,
    },
]


DEFAULT_WORKSHEETS: List[Dict[str, object]] = [
    {
        "key": "thought_record_basic",
        "name": "Basic Thought Record",
        "description": "Surface and reframe an automatic thought using a 7-column record.",
        "instructions": (
            "1. Describe the situation factually.\n"
            "2. Name the automatic thought.\n"
            "3. Rate the emotion and intensity (0-100).\n"
            "4. List evidence for the thought.\n"
            "5. List evidence against.\n"
            "6. Write a balanced thought.\n"
            "7. Rerate the emotion."
        ),
        "estimated_minutes": 15,
        "category": "general",
        "difficulty": "beginner",
    },
    {
        "key": "decatastrophizing",
        "name": "Decatastrophizing",
        "description": "Walk through worst / best / most realistic outcomes for a worry.",
        "instructions": (
            "1. State the feared outcome plainly.\n"
            "2. Worst case — and how would you cope?\n"
            "3. Best case — and what would it require?\n"
            "4. Most realistic case — what is the evidence?\n"
            "5. What can you influence in the next 48 hours?"
        ),
        "estimated_minutes": 12,
        "category": "anxiety",
        "difficulty": "beginner",
    },
    {
        "key": "worry_tree",
        "name": "Worry Tree",
        "description": "Decide if a worry is solvable; if so, plan an action — if not, choose a let-go strategy.",
        "instructions": (
            "1. Write down the worry.\n"
            "2. Is it about something you can act on?\n"
            "3. If yes: define one concrete action and a time to do it.\n"
            "4. If no: pick a let-go strategy (postpone, soothe, defuse, accept)."
        ),
        "estimated_minutes": 10,
        "category": "anxiety",
        "difficulty": "beginner",
    },
    {
        "key": "behavioral_experiment",
        "name": "Behavioral Experiment",
        "description": "Test a prediction in the real world rather than debating it in your head.",
        "instructions": (
            "1. State the belief and how strongly you believe it (0-100%).\n"
            "2. Predict what will happen.\n"
            "3. Design a small experiment that could prove you wrong.\n"
            "4. Conduct it; note what actually happened.\n"
            "5. Re-rate the belief and write one sentence of learning."
        ),
        "estimated_minutes": 20,
        "category": "general",
        "difficulty": "intermediate",
    },
    {
        "key": "behavioral_activation",
        "name": "Activity Scheduling (Behavioral Activation)",
        "description": "Schedule small pleasure and mastery activities to lift mood and momentum.",
        "instructions": (
            "1. Pick a 1-3 day window.\n"
            "2. Block in 3 pleasure activities (joy/comfort) and 2 mastery activities (small accomplishments).\n"
            "3. After each, rate pleasure (0-10) and mastery (0-10).\n"
            "4. Review which activities consistently lifted mood — repeat."
        ),
        "estimated_minutes": 25,
        "category": "depression",
        "difficulty": "beginner",
    },
    {
        "key": "core_belief_examination",
        "name": "Core Belief Examination",
        "description": "Identify a core belief, gather evidence against it, draft an alternative.",
        "instructions": (
            "1. Surface a recurring belief about yourself / others / the world / the future.\n"
            "2. Rate how much you believe it (0-100%).\n"
            "3. Find five pieces of evidence that don't fit it.\n"
            "4. Draft an alternative belief.\n"
            "5. Rate how much you believe the alternative."
        ),
        "estimated_minutes": 30,
        "category": "general",
        "difficulty": "advanced",
    },
    {
        "key": "self_compassion_letter",
        "name": "Self-Compassion Letter",
        "description": "Write to yourself the way a wise, kind friend would.",
        "instructions": (
            "1. Describe the difficulty briefly, without judging.\n"
            "2. Acknowledge that suffering is part of being human.\n"
            "3. Write 2-3 sentences as a kind friend would.\n"
            "4. Note one small kindness you can give yourself today."
        ),
        "estimated_minutes": 15,
        "category": "general",
        "difficulty": "beginner",
    },
    {
        "key": "anger_record",
        "name": "Anger Record",
        "description": "Slow down an anger response by surfacing the trigger, thought, and choice point.",
        "instructions": (
            "1. Trigger: what happened?\n"
            "2. Body sensation and intensity (0-10).\n"
            "3. The thought behind the anger.\n"
            "4. The unmet need or value.\n"
            "5. One adaptive response you can choose now."
        ),
        "estimated_minutes": 12,
        "category": "anger",
        "difficulty": "intermediate",
    },
]


def seed_distortions() -> int:
    """Insert default distortion catalog if missing."""
    db = SessionLocal()
    inserted = 0
    try:
        existing = {d.key for d in db.query(CognitiveDistortion).all()}
        for entry in DEFAULT_DISTORTIONS:
            if entry["key"] in existing:
                continue
            db.add(CognitiveDistortion(**entry))
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def seed_worksheets() -> int:
    db = SessionLocal()
    inserted = 0
    try:
        existing = {w.key for w in db.query(WorksheetTemplate).all()}
        for entry in DEFAULT_WORKSHEETS:
            if entry["key"] in existing:
                continue
            db.add(WorksheetTemplate(**entry))
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def init_cbt_models() -> Dict[str, int]:
    """Create CBT tables and seed catalogs. Safe to call repeatedly."""
    from database import engine
    Base.metadata.create_all(bind=engine)
    return {
        "distortions_seeded": seed_distortions(),
        "worksheets_seeded": seed_worksheets(),
    }
