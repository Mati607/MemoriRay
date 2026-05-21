"""
AI / rule-based habit coach.

Generates short, specific coaching notes (nudges, celebrations, friction
diagnoses) based on the user's habit history, behavior events, and
recent check-ins. Uses Gemini when a key is set; otherwise falls back
to a deterministic ruleset.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional

from database import SessionLocal
from habit_models import (
    Habit, HabitCheckIn, HabitStreak,
    BehaviorEvent, HabitCoachNote, BEHAVIOR_EVENT_TYPES,
)
import habit_analytics


@dataclass
class CoachNote:
    note_type: str
    title: str
    body: str
    related_habit_id: Optional[int]
    confidence: float


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def generate_coaching(user_id: int, use_llm: bool = True, persist: bool = True) -> List[Dict[str, object]]:
    """Produce a set of coaching notes for the user."""
    context = _gather_context(user_id)

    notes: List[CoachNote] = []
    if use_llm and _has_genai_key():
        try:
            notes = _generate_with_llm(context)
        except Exception:
            notes = []
    if not notes:
        notes = _generate_with_rules(context)

    if persist:
        return [_persist(user_id, n) for n in notes]
    return [_to_dict(n) for n in notes]


def list_coach_notes(user_id: int, include_dismissed: bool = False, limit: int = 30) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(HabitCoachNote).filter(HabitCoachNote.user_id == user_id)
        if not include_dismissed:
            q = q.filter(HabitCoachNote.is_dismissed.is_(False))
        rows = q.order_by(HabitCoachNote.created_at.desc()).limit(limit).all()
        return [_serialize_note(r) for r in rows]
    finally:
        db.close()


def dismiss_coach_note(user_id: int, note_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(HabitCoachNote)
            .filter(HabitCoachNote.id == note_id, HabitCoachNote.user_id == user_id)
            .first()
        )
        if not row:
            return False
        row.is_dismissed = True
        db.commit()
        return True
    finally:
        db.close()


def delete_coach_note(user_id: int, note_id: int) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(HabitCoachNote)
            .filter(HabitCoachNote.id == note_id, HabitCoachNote.user_id == user_id)
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
# Context gathering
# ---------------------------------------------------------------------------

def _gather_context(user_id: int) -> Dict[str, object]:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=21)
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_archived.is_(False))
            .all()
        )
        check_ins = (
            db.query(HabitCheckIn)
            .filter(
                HabitCheckIn.user_id == user_id,
                HabitCheckIn.occurred_on >= cutoff,
            )
            .all()
        )
        streaks = (
            db.query(HabitStreak)
            .filter(HabitStreak.user_id == user_id)
            .all()
        )
        events = (
            db.query(BehaviorEvent)
            .filter(
                BehaviorEvent.user_id == user_id,
                BehaviorEvent.occurred_at >= cutoff,
            )
            .all()
        )

        return {
            "habits": [
                {
                    "id": h.id,
                    "name": h.name,
                    "category": h.category,
                    "cadence": h.cadence,
                    "cue": h.cue,
                    "reward": h.reward,
                    "is_keystone": h.is_keystone,
                    "difficulty": h.difficulty,
                }
                for h in habits
            ],
            "streaks": [
                {
                    "habit_id": s.habit_id,
                    "current": s.current_streak,
                    "longest": s.longest_streak,
                    "total": s.total_check_ins,
                    "skips": s.total_skips,
                    "last": s.last_check_in.isoformat() if s.last_check_in else None,
                }
                for s in streaks
            ],
            "check_ins": [
                {
                    "habit_id": c.habit_id,
                    "occurred_on": c.occurred_on.isoformat(),
                    "status": c.status,
                    "quality": c.quality,
                }
                for c in check_ins
            ],
            "events": [
                {
                    "event_type": e.event_type,
                    "value": e.value,
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in events
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Rule-based coach
# ---------------------------------------------------------------------------

def _generate_with_rules(context: Dict[str, object]) -> List[CoachNote]:
    habits: List[Dict[str, object]] = context["habits"]
    streaks: List[Dict[str, object]] = context["streaks"]
    check_ins: List[Dict[str, object]] = context["check_ins"]
    events: List[Dict[str, object]] = context["events"]

    streak_by_habit = {s["habit_id"]: s for s in streaks}
    notes: List[CoachNote] = []

    if not habits:
        notes.append(
            CoachNote(
                note_type="starter",
                title="Start with one tiny habit",
                body=(
                    "You don't have any habits set up yet. Pick the smallest possible "
                    "version of a habit you want — five minutes of walking, one glass "
                    "of water on waking, two pages of reading. Tiny beats motivated."
                ),
                related_habit_id=None,
                confidence=0.95,
            )
        )
        return notes

    # Celebrate the longest streak.
    longest_now = max(streaks, key=lambda s: s["current"] or 0, default=None)
    if longest_now and (longest_now["current"] or 0) >= 5:
        habit_name = next(
            (h["name"] for h in habits if h["id"] == longest_now["habit_id"]), "your habit"
        )
        notes.append(
            CoachNote(
                note_type="celebration",
                title=f"{longest_now['current']}-day streak on {habit_name}",
                body=(
                    f"Streaks compound — name what's working so you can repeat it. "
                    f"Was it the cue, the time of day, pairing it with another habit?"
                ),
                related_habit_id=longest_now["habit_id"],
                confidence=0.9,
            )
        )

    # Diagnose broken streaks.
    for h in habits:
        s = streak_by_habit.get(h["id"])
        if not s:
            continue
        if (s["longest"] or 0) >= 5 and (s["current"] or 0) == 0:
            notes.append(
                CoachNote(
                    note_type="recovery",
                    title=f"Restart {h['name']}",
                    body=(
                        "You had a streak of "
                        f"{s['longest']} days here before. Missing a day isn't failure "
                        "— missing two in a row is what to avoid. Do the smallest "
                        "possible version today, even for 30 seconds."
                    ),
                    related_habit_id=h["id"],
                    confidence=0.85,
                )
            )

    # Habits never checked in.
    seen_habits = {c["habit_id"] for c in check_ins}
    for h in habits:
        if h["id"] not in seen_habits:
            notes.append(
                CoachNote(
                    note_type="nudge",
                    title=f"Try {h['name']} once",
                    body=(
                        "This habit is on your list but you haven't checked it in yet. "
                        "Do a 2-minute version of it today — proof-of-concept beats perfection."
                    ),
                    related_habit_id=h["id"],
                    confidence=0.7,
                )
            )

    # Behavior events: flag sleep debt.
    sleep_values = [e["value"] for e in events if e["event_type"] == "sleep" and e["value"] is not None]
    if sleep_values:
        avg_sleep = sum(sleep_values) / len(sleep_values)
        if avg_sleep < 6.5:
            notes.append(
                CoachNote(
                    note_type="behavior",
                    title="Your sleep is running low",
                    body=(
                        f"Average of about {avg_sleep:.1f}h in recent nights. "
                        "Consider shifting bedtime 15 minutes earlier rather than waking later — "
                        "the first move that pays back fastest is consistent lights-out."
                    ),
                    related_habit_id=None,
                    confidence=0.8,
                )
            )

    # Behavior events: hydration low?
    hydration_values = [e["value"] for e in events if e["event_type"] == "hydration" and e["value"] is not None]
    if hydration_values:
        avg_h = sum(hydration_values) / len(hydration_values)
        if avg_h < 4:
            notes.append(
                CoachNote(
                    note_type="behavior",
                    title="Hydration is light",
                    body=(
                        "Recent logs average under 4 glasses. Pair drinking water with a habit you "
                        "already do (coffee refill, bathroom break) — the cue is more reliable than the alarm."
                    ),
                    related_habit_id=None,
                    confidence=0.7,
                )
            )

    # Identify a keystone habit doing well.
    keystone_habits = [h for h in habits if h.get("is_keystone")]
    for kh in keystone_habits:
        s = streak_by_habit.get(kh["id"])
        if s and (s["current"] or 0) >= 7:
            notes.append(
                CoachNote(
                    note_type="keystone",
                    title=f"{kh['name']} is paying compound interest",
                    body=(
                        "Keystone habits drive others. Now is a good moment to stack one more "
                        "tiny habit *immediately after* this one — anchor the new habit to the existing "
                        "trigger and reward."
                    ),
                    related_habit_id=kh["id"],
                    confidence=0.85,
                )
            )

    # Time-of-day insight — bucket directly from check_ins we already have.
    if check_ins:
        morning = sum(1 for c in check_ins if 6 <= datetime.fromisoformat(c["occurred_on"]).hour < 12)
        evening = sum(1 for c in check_ins if 17 <= datetime.fromisoformat(c["occurred_on"]).hour < 22)
        total = morning + evening
        if total > 5:
            preferred = "morning" if morning > evening else "evening"
            notes.append(
                CoachNote(
                    note_type="timing",
                    title=f"You're a {preferred}-person",
                    body=(
                        f"Most of your check-ins land in the {preferred}. Schedule new habits "
                        f"at the same time to ride the same context."
                    ),
                    related_habit_id=None,
                    confidence=0.7,
                )
            )

    if not notes:
        notes.append(
            CoachNote(
                note_type="reflection",
                title="Steady — keep observing",
                body=(
                    "Nothing alarming, nothing screaming for attention. The work right now is "
                    "noticing what's working and protecting the rituals that already exist."
                ),
                related_habit_id=None,
                confidence=0.6,
            )
        )
    return notes[:6]


# ---------------------------------------------------------------------------
# LLM coach
# ---------------------------------------------------------------------------

def _has_genai_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _generate_with_llm(context: Dict[str, object]) -> List[CoachNote]:
    from google import genai

    prompt = _build_prompt(context)

    client = genai.Client()
    model_name = os.getenv("MEMORIRAY_COACH_MODEL", "gemini-2.0-flash-exp")
    response = client.models.generate_content(model=model_name, contents=prompt)
    text = getattr(response, "text", "") or ""
    parsed = _parse_response(text)

    notes: List[CoachNote] = []
    for item in parsed.get("notes", []) or []:
        body = item.get("body") or ""
        title = item.get("title") or ""
        if not body or not title:
            continue
        notes.append(
            CoachNote(
                note_type=item.get("note_type", "nudge"),
                title=title[:200],
                body=body,
                related_habit_id=item.get("related_habit_id"),
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return notes


def _build_prompt(context: Dict[str, object]) -> str:
    habit_summary = "\n".join(
        f"- id={h['id']} {h['name']} ({h['category']}, {h['cadence']})"
        + (" — keystone" if h.get("is_keystone") else "")
        for h in context["habits"][:30]
    )
    streak_summary = "\n".join(
        f"- habit_id={s['habit_id']} current={s['current']} longest={s['longest']}"
        for s in context["streaks"][:30]
    )
    event_summary = "\n".join(
        f"- {e['event_type']}={e['value']} on {e['occurred_at'][:10]}"
        for e in context["events"][:30]
    )

    return f"""You are a kind, evidence-based behavior coach.
Given the user's habit and behavior data, write 3-5 short coaching notes.

Respond ONLY with JSON, no prose, no code fences. Schema:
{{
  "notes": [
    {{
      "note_type": "nudge|celebration|recovery|behavior|keystone|timing|reflection",
      "title": "short specific title",
      "body": "2-4 sentences, kind and concrete, no diagnoses",
      "related_habit_id": <int or null>,
      "confidence": 0.6
    }}
  ]
}}

Habits:
{habit_summary or "(none)"}

Streaks:
{streak_summary or "(none)"}

Recent behavior events:
{event_summary or "(none)"}
"""


def _parse_response(text: str) -> Dict[str, object]:
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _persist(user_id: int, note: CoachNote) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = HabitCoachNote(
            user_id=user_id,
            note_type=note.note_type,
            title=note.title,
            body=note.body,
            related_habit_id=note.related_habit_id,
            confidence=note.confidence,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_note(row)
    finally:
        db.close()


def _serialize_note(row: HabitCoachNote) -> Dict[str, object]:
    return {
        "id": row.id,
        "note_type": row.note_type,
        "title": row.title,
        "body": row.body,
        "related_habit_id": row.related_habit_id,
        "confidence": row.confidence,
        "is_dismissed": row.is_dismissed,
        "created_at": row.created_at.isoformat(),
    }


def _to_dict(note: CoachNote) -> Dict[str, object]:
    return {
        "note_type": note.note_type,
        "title": note.title,
        "body": note.body,
        "related_habit_id": note.related_habit_id,
        "confidence": note.confidence,
    }
