"""
Reflection generator.

Aggregates journal entries, gratitude items, and mindfulness sessions over
a window (daily / weekly / monthly), then produces a structured reflection.
Uses Gemini via the project's existing google-genai client when available
and falls back to a deterministic rule-based summary otherwise.

The fallback is important: it lets the feature work offline, in tests, and
when the model key isn't set, while still surfacing useful patterns.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from database import SessionLocal
from journal_models import (
    JournalEntry,
    GratitudeEntry,
    MindfulnessSession,
    ReflectionSnapshot,
    ReflectionFeedback,
)


WINDOW_KINDS = {"daily", "weekly", "monthly"}


@dataclass
class ReflectionPayload:
    summary: str
    dominant_themes: List[str]
    mood_trend: str
    growth_signals: List[str]
    suggested_focus: List[str]
    entries_analyzed: int
    gratitudes_analyzed: int
    sessions_analyzed: int


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_reflection(
    user_id: int,
    window_kind: str = "weekly",
    use_llm: bool = True,
) -> Dict[str, object]:
    """Generate and persist a reflection for the requested window."""
    if window_kind not in WINDOW_KINDS:
        raise ValueError(f"Invalid window_kind: {window_kind}")

    window_start, window_end = _window_bounds(window_kind)
    data = _collect_window_data(user_id, window_start, window_end)

    payload: Optional[ReflectionPayload] = None
    if use_llm and _has_genai_key():
        try:
            payload = _generate_with_llm(data)
        except Exception:
            payload = None
    if payload is None:
        payload = _generate_with_rules(data)

    snapshot = _persist(user_id, window_start, window_end, window_kind, payload)
    return snapshot


def list_reflections(user_id: int, limit: int = 10, window_kind: Optional[str] = None) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(ReflectionSnapshot).filter(ReflectionSnapshot.user_id == user_id)
        if window_kind:
            q = q.filter(ReflectionSnapshot.window_kind == window_kind)
        rows = q.order_by(ReflectionSnapshot.generated_at.desc()).limit(limit).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


def get_reflection(user_id: int, snapshot_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        row = (
            db.query(ReflectionSnapshot)
            .filter(
                ReflectionSnapshot.id == snapshot_id,
                ReflectionSnapshot.user_id == user_id,
            )
            .first()
        )
        return _serialize(row) if row else None
    finally:
        db.close()


def record_feedback(
    user_id: int,
    snapshot_id: int,
    accuracy_rating: Optional[float] = None,
    helpfulness_rating: Optional[float] = None,
    comment: Optional[str] = None,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        fb = ReflectionFeedback(
            snapshot_id=snapshot_id,
            user_id=user_id,
            accuracy_rating=accuracy_rating,
            helpfulness_rating=helpfulness_rating,
            comment=(comment or "")[:2000] or None,
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)
        return {
            "id": fb.id,
            "snapshot_id": fb.snapshot_id,
            "accuracy_rating": fb.accuracy_rating,
            "helpfulness_rating": fb.helpfulness_rating,
            "comment": fb.comment,
            "created_at": fb.created_at.isoformat(),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _window_bounds(kind: str) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if kind == "daily":
        start = now - timedelta(days=1)
    elif kind == "weekly":
        start = now - timedelta(days=7)
    else:
        start = now - timedelta(days=30)
    return start, now


def _collect_window_data(user_id: int, start: datetime, end: datetime) -> Dict[str, object]:
    db = SessionLocal()
    try:
        entries = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= start,
                JournalEntry.created_at <= end,
                JournalEntry.is_archived.is_(False),
            )
            .order_by(JournalEntry.created_at.asc())
            .all()
        )
        gratitudes = (
            db.query(GratitudeEntry)
            .filter(
                GratitudeEntry.user_id == user_id,
                GratitudeEntry.created_at >= start,
                GratitudeEntry.created_at <= end,
            )
            .order_by(GratitudeEntry.created_at.asc())
            .all()
        )
        sessions = (
            db.query(MindfulnessSession)
            .filter(
                MindfulnessSession.user_id == user_id,
                MindfulnessSession.started_at >= start,
                MindfulnessSession.started_at <= end,
            )
            .order_by(MindfulnessSession.started_at.asc())
            .all()
        )

        return {
            "window_start": start,
            "window_end": end,
            "entries": [
                {
                    "title": e.title,
                    "body": e.body,
                    "mood_score": e.mood_score,
                    "energy_level": e.energy_level,
                    "stress_level": e.stress_level,
                    "created_at": e.created_at.isoformat(),
                    "word_count": e.word_count,
                }
                for e in entries
            ],
            "gratitudes": [
                {
                    "content": g.content,
                    "category": g.category,
                    "related_person": g.related_person,
                    "created_at": g.created_at.isoformat(),
                }
                for g in gratitudes
            ],
            "sessions": [
                {
                    "technique": s.technique,
                    "duration_minutes": round((s.duration_seconds or 0) / 60.0, 1),
                    "pre_mood": s.pre_mood,
                    "post_mood": s.post_mood,
                    "perceived_calm": s.perceived_calm,
                    "started_at": s.started_at.isoformat(),
                }
                for s in sessions
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

_THEME_KEYWORDS = {
    "work": ["work", "meeting", "deadline", "boss", "project", "office", "job", "client", "task"],
    "relationships": ["friend", "family", "partner", "mom", "dad", "brother", "sister", "love", "argument"],
    "self_doubt": ["doubt", "not enough", "imposter", "worthless", "failure", "stupid", "ashamed"],
    "growth": ["grew", "learned", "realized", "noticed", "tried", "stretch", "challenged"],
    "rest": ["tired", "rest", "sleep", "exhausted", "nap", "rest", "recover"],
    "body": ["body", "ache", "pain", "tense", "breath", "headache", "stomach"],
    "joy": ["laughed", "fun", "happy", "joy", "smile", "loved", "enjoyed"],
    "anxiety": ["anxious", "anxiety", "panic", "worry", "worried", "racing", "spiral", "scared"],
    "loneliness": ["alone", "lonely", "isolated", "disconnected", "miss"],
}


def _generate_with_rules(data: Dict[str, object]) -> ReflectionPayload:
    entries = data["entries"]
    gratitudes = data["gratitudes"]
    sessions = data["sessions"]

    text_corpus = " ".join((e.get("body") or "").lower() for e in entries)
    theme_hits: Counter = Counter()
    for theme, keywords in _THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in text_corpus:
                theme_hits[theme] += 1
    dominant_themes = [t for t, _ in theme_hits.most_common(4)]

    moods = [e["mood_score"] for e in entries if e.get("mood_score") is not None]
    mood_trend = _describe_mood_trend(moods)

    growth_signals = _detect_growth_signals(entries, sessions)
    suggested_focus = _suggest_focus(dominant_themes, mood_trend, sessions, gratitudes)

    summary = _compose_summary(entries, gratitudes, sessions, dominant_themes, mood_trend)

    return ReflectionPayload(
        summary=summary,
        dominant_themes=dominant_themes,
        mood_trend=mood_trend,
        growth_signals=growth_signals,
        suggested_focus=suggested_focus,
        entries_analyzed=len(entries),
        gratitudes_analyzed=len(gratitudes),
        sessions_analyzed=len(sessions),
    )


def _describe_mood_trend(moods: List[float]) -> str:
    if not moods:
        return "unknown"
    if len(moods) == 1:
        score = moods[0]
        if score >= 7:
            return "steady_positive"
        if score >= 5:
            return "steady_neutral"
        return "steady_low"

    first_half = moods[: max(1, len(moods) // 2)]
    second_half = moods[len(moods) // 2:]
    delta = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
    if delta > 0.7:
        return "rising"
    if delta < -0.7:
        return "declining"
    avg = sum(moods) / len(moods)
    if avg >= 7:
        return "steady_positive"
    if avg <= 4:
        return "steady_low"
    return "steady_neutral"


def _detect_growth_signals(entries: List[Dict[str, object]], sessions: List[Dict[str, object]]) -> List[str]:
    signals: List[str] = []
    if entries:
        word_counts = [int(e.get("word_count") or 0) for e in entries]
        if any(wc > 200 for wc in word_counts):
            signals.append("You're writing in depth — that tends to pay off in self-awareness.")
        if len({e.get("created_at", "")[:10] for e in entries}) >= 3:
            signals.append("You showed up to journal on multiple days, which builds momentum.")

    if sessions:
        positive_deltas = [
            (s["post_mood"] - s["pre_mood"])
            for s in sessions
            if s.get("pre_mood") is not None and s.get("post_mood") is not None
            and (s["post_mood"] - s["pre_mood"]) > 0.5
        ]
        if positive_deltas:
            signals.append(
                f"{len(positive_deltas)} mindfulness session(s) actually shifted your mood upward."
            )

    if not signals:
        signals.append("Showing up at all is the signal. Consistency compounds.")
    return signals


def _suggest_focus(
    themes: List[str],
    mood_trend: str,
    sessions: List[Dict[str, object]],
    gratitudes: List[Dict[str, object]],
) -> List[str]:
    focuses: List[str] = []
    if "anxiety" in themes or mood_trend == "declining":
        focuses.append("Try a daily 5-4-3-2-1 grounding practice this week.")
    if "self_doubt" in themes:
        focuses.append("Pair each negative self-judgment with a self-compassion break.")
    if "work" in themes and "rest" in themes:
        focuses.append("Schedule a non-negotiable rest block — your journal is asking for it.")
    if "loneliness" in themes:
        focuses.append("Reach out to one person you trust this week, even briefly.")
    if not sessions:
        focuses.append("Start with one short 4-7-8 breathing session — it pairs well with journaling.")
    if not gratitudes:
        focuses.append("Add one gratitude entry a day; the bar is low — three words is enough.")
    if mood_trend == "rising":
        focuses.append("Capture what's working. Name it explicitly so it's repeatable.")
    if not focuses:
        focuses.append("Stay with what you're doing — the pattern looks healthy.")
    return focuses[:4]


def _compose_summary(
    entries: List[Dict[str, object]],
    gratitudes: List[Dict[str, object]],
    sessions: List[Dict[str, object]],
    themes: List[str],
    mood_trend: str,
) -> str:
    parts: List[str] = []
    if not entries and not gratitudes and not sessions:
        return (
            "There isn't enough data in this window to reflect on yet. "
            "A single journal entry or gratitude is enough to seed the next reflection."
        )

    if entries:
        parts.append(
            f"You wrote {len(entries)} journal entr{'y' if len(entries) == 1 else 'ies'} "
            f"totaling {sum(int(e.get('word_count') or 0) for e in entries)} words."
        )
    if gratitudes:
        parts.append(
            f"You logged {len(gratitudes)} gratitude{'s' if len(gratitudes) != 1 else ''}, "
            f"often around {', '.join(_top_categories(gratitudes))}."
        )
    if sessions:
        minutes = sum(s.get("duration_minutes") or 0 for s in sessions)
        parts.append(
            f"You practiced mindfulness {len(sessions)} time(s) for about {round(minutes, 0)} minute(s) total."
        )

    if themes:
        parts.append(
            "Themes that came up: " + ", ".join(themes) + "."
        )
    mood_phrase = {
        "rising": "Your mood trended upward across the window.",
        "declining": "Your mood drifted downward across the window — worth a gentle check-in.",
        "steady_positive": "Your mood stayed positive throughout.",
        "steady_neutral": "Your mood held roughly steady, in the middle range.",
        "steady_low": "Your mood stayed on the low side. Be kind with yourself.",
        "unknown": "",
    }.get(mood_trend, "")
    if mood_phrase:
        parts.append(mood_phrase)
    return " ".join(parts)


def _top_categories(gratitudes: List[Dict[str, object]]) -> List[str]:
    counter: Counter = Counter()
    for g in gratitudes:
        counter[(g.get("category") or "other")] += 1
    return [name for name, _ in counter.most_common(3)]


# ---------------------------------------------------------------------------
# LLM-backed path
# ---------------------------------------------------------------------------

def _has_genai_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _generate_with_llm(data: Dict[str, object]) -> ReflectionPayload:
    """Use Gemini to draft a reflection. Falls back to rules on any failure."""
    from google import genai  # local import so the module loads without the key

    prompt = _build_llm_prompt(data)

    client = genai.Client()
    model_name = os.getenv("MEMORIRAY_REFLECTION_MODEL", "gemini-2.0-flash-exp")

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    text = getattr(response, "text", "") or ""
    parsed = _parse_llm_response(text)

    # Sanity: if the model produced nothing meaningful, fall back.
    if not parsed.get("summary"):
        return _generate_with_rules(data)

    return ReflectionPayload(
        summary=parsed["summary"],
        dominant_themes=parsed.get("dominant_themes", []) or [],
        mood_trend=parsed.get("mood_trend", "unknown") or "unknown",
        growth_signals=parsed.get("growth_signals", []) or [],
        suggested_focus=parsed.get("suggested_focus", []) or [],
        entries_analyzed=len(data["entries"]),
        gratitudes_analyzed=len(data["gratitudes"]),
        sessions_analyzed=len(data["sessions"]),
    )


def _build_llm_prompt(data: Dict[str, object]) -> str:
    snippets: List[str] = []
    for e in data["entries"][-10:]:
        title = (e.get("title") or "").strip()
        body = (e.get("body") or "").strip()
        mood = e.get("mood_score")
        prefix = f"[{e.get('created_at', '')[:10]}]"
        if title:
            prefix += f" {title} —"
        if mood is not None:
            prefix += f" (mood {mood})"
        snippets.append(prefix + " " + body[:500])

    grat_lines = [f"- {g.get('content','')}" for g in data["gratitudes"][-10:]]
    session_lines = [
        f"- {s.get('technique','')} for {s.get('duration_minutes',0)}m"
        for s in data["sessions"][-10:]
    ]

    return f"""You are a compassionate, evidence-aware journaling companion.
Write a thoughtful reflection on the user's recent practice.
Be specific, gentle, and avoid generic platitudes. Do not diagnose.
Respond ONLY with a JSON object — no prose outside the JSON, no code fences.

Schema:
{{
  "summary": "2-4 sentences summarizing what you observe",
  "dominant_themes": ["list", "of", "short", "phrases"],
  "mood_trend": "one of: rising, declining, steady_positive, steady_neutral, steady_low, unknown",
  "growth_signals": ["specific observations of growth"],
  "suggested_focus": ["1-3 concrete suggestions for the next week"]
}}

Recent journal snippets:
{chr(10).join(snippets) if snippets else "(none)"}

Recent gratitudes:
{chr(10).join(grat_lines) if grat_lines else "(none)"}

Recent mindfulness practice:
{chr(10).join(session_lines) if session_lines else "(none)"}
"""


def _parse_llm_response(text: str) -> Dict[str, object]:
    """Tolerant JSON extraction — strip code fences, find the first object."""
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

def _persist(
    user_id: int,
    window_start: datetime,
    window_end: datetime,
    window_kind: str,
    payload: ReflectionPayload,
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        row = ReflectionSnapshot(
            user_id=user_id,
            window_start=window_start,
            window_end=window_end,
            window_kind=window_kind,
            summary=payload.summary,
            dominant_themes=", ".join(payload.dominant_themes)[:1000],
            mood_trend=payload.mood_trend,
            growth_signals="\n".join(payload.growth_signals),
            suggested_focus="\n".join(payload.suggested_focus),
            entries_analyzed=payload.entries_analyzed,
            gratitudes_analyzed=payload.gratitudes_analyzed,
            sessions_analyzed=payload.sessions_analyzed,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize(row)
    finally:
        db.close()


def _serialize(row: Optional[ReflectionSnapshot]) -> Optional[Dict[str, object]]:
    if not row:
        return None
    return {
        "id": row.id,
        "window_start": row.window_start.isoformat(),
        "window_end": row.window_end.isoformat(),
        "window_kind": row.window_kind,
        "summary": row.summary,
        "dominant_themes": [t.strip() for t in (row.dominant_themes or "").split(",") if t.strip()],
        "mood_trend": row.mood_trend,
        "growth_signals": [s for s in (row.growth_signals or "").split("\n") if s.strip()],
        "suggested_focus": [s for s in (row.suggested_focus or "").split("\n") if s.strip()],
        "entries_analyzed": row.entries_analyzed,
        "gratitudes_analyzed": row.gratitudes_analyzed,
        "sessions_analyzed": row.sessions_analyzed,
        "generated_at": row.generated_at.isoformat(),
    }
