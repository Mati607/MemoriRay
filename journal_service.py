"""
Service layer for journal entries.

Provides CRUD, search, tagging, prompt suggestions, and lightweight
text analysis (word count, top keywords, sentiment heuristics) without
depending on the LLM. Higher-level AI reflections live in
reflection_generator.py.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterable, List, Dict, Optional, Tuple

from sqlalchemy import or_, and_

from database import SessionLocal
from journal_models import (
    JournalEntry,
    JournalTag,
    JournalEntryTag,
    JournalPrompt,
    JournalAttachment,
)


# Stop words used by the keyword extractor. Kept intentionally small —
# we want surface-level keywords, not perfect linguistic analysis.
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "so", "if", "of", "in", "to", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "i", "me", "my",
    "mine", "we", "us", "our", "you", "your", "yours", "he", "she", "it",
    "they", "them", "their", "this", "that", "these", "those", "for",
    "from", "with", "without", "on", "off", "at", "by", "as", "than", "then",
    "so", "not", "no", "yes", "what", "which", "who", "whom", "whose",
    "where", "when", "why", "how", "just", "really", "very", "much", "more",
    "less", "some", "any", "all", "any", "each", "every", "such", "only",
    "own", "same", "too", "can", "cannot", "got", "get", "make", "made",
    "like", "feel", "felt", "today", "yesterday", "tomorrow", "thing", "things",
}

_WORD_RE = re.compile(r"[A-Za-z']+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    if not text:
        return 0
    return len(_WORD_RE.findall(text))


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [w.lower() for w in _WORD_RE.findall(text)]


def _extract_keywords(text: str, top_n: int = 8) -> List[str]:
    tokens = [t for t in _tokenize(text) if t not in _STOP_WORDS and len(t) > 2]
    if not tokens:
        return []
    counter = Counter(tokens)
    return [word for word, _ in counter.most_common(top_n)]


@dataclass
class EntryAnalysis:
    """Lightweight analysis of a single journal entry."""
    word_count: int
    keywords: List[str]
    mood_score: Optional[float]
    estimated_minutes: float
    readability: str


def analyze_text(text: str, mood_score: Optional[float] = None) -> EntryAnalysis:
    words = _count_words(text)
    keywords = _extract_keywords(text)
    minutes = round(words / 220.0, 2) if words else 0.0
    if words < 80:
        readability = "brief"
    elif words < 250:
        readability = "moderate"
    else:
        readability = "long"
    return EntryAnalysis(
        word_count=words,
        keywords=keywords,
        mood_score=mood_score,
        estimated_minutes=minutes,
        readability=readability,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_entry(
    user_id: int,
    body: str,
    title: Optional[str] = None,
    mood_score: Optional[float] = None,
    energy_level: Optional[float] = None,
    stress_level: Optional[float] = None,
    prompt_id: Optional[int] = None,
    entry_type: str = "free_form",
    location: Optional[str] = None,
    weather: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    is_draft: bool = False,
) -> Dict[str, object]:
    """Create a journal entry. Returns the serialized entry."""
    if not body or not body.strip():
        raise ValueError("Journal entry body cannot be empty.")

    word_count = _count_words(body)
    db = SessionLocal()
    try:
        entry = JournalEntry(
            user_id=user_id,
            title=(title or "").strip()[:255] or None,
            body=body.strip(),
            word_count=word_count,
            mood_score=mood_score,
            energy_level=energy_level,
            stress_level=stress_level,
            prompt_id=prompt_id,
            entry_type=entry_type,
            location=location,
            weather=weather,
            is_draft=is_draft,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        if tags:
            _attach_tags(db, user_id=user_id, entry_id=entry.id, tag_names=list(tags))
            db.commit()

        return _serialize_entry(entry, db=db)
    finally:
        db.close()


def update_entry(
    user_id: int,
    entry_id: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    mood_score: Optional[float] = None,
    energy_level: Optional[float] = None,
    stress_level: Optional[float] = None,
    is_favorite: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    is_draft: Optional[bool] = None,
    tags: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """Update an existing entry. Only provided fields change."""
    db = SessionLocal()
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
            .first()
        )
        if not entry:
            raise LookupError("Entry not found.")

        if title is not None:
            entry.title = title.strip()[:255] or None
        if body is not None:
            if not body.strip():
                raise ValueError("Body cannot be empty.")
            entry.body = body.strip()
            entry.word_count = _count_words(body)
        if mood_score is not None:
            entry.mood_score = mood_score
        if energy_level is not None:
            entry.energy_level = energy_level
        if stress_level is not None:
            entry.stress_level = stress_level
        if is_favorite is not None:
            entry.is_favorite = bool(is_favorite)
        if is_archived is not None:
            entry.is_archived = bool(is_archived)
        if is_draft is not None:
            entry.is_draft = bool(is_draft)

        entry.updated_at = datetime.now(timezone.utc)

        if tags is not None:
            _clear_entry_tags(db, entry.id)
            _attach_tags(db, user_id=user_id, entry_id=entry.id, tag_names=list(tags))

        db.commit()
        db.refresh(entry)
        return _serialize_entry(entry, db=db)
    finally:
        db.close()


def delete_entry(user_id: int, entry_id: int) -> bool:
    """Hard-delete an entry and its tag links."""
    db = SessionLocal()
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
            .first()
        )
        if not entry:
            return False
        _clear_entry_tags(db, entry.id)
        db.query(JournalAttachment).filter(JournalAttachment.entry_id == entry.id).delete()
        db.delete(entry)
        db.commit()
        return True
    finally:
        db.close()


def get_entry(user_id: int, entry_id: int) -> Optional[Dict[str, object]]:
    db = SessionLocal()
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
            .first()
        )
        if not entry:
            return None
        return _serialize_entry(entry, db=db, include_body=True)
    finally:
        db.close()


def list_entries(
    user_id: int,
    limit: int = 30,
    offset: int = 0,
    include_archived: bool = False,
    include_drafts: bool = True,
    tag: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    favorites_only: bool = False,
) -> List[Dict[str, object]]:
    """List entries with filters. Excludes archived by default."""
    db = SessionLocal()
    try:
        q = db.query(JournalEntry).filter(JournalEntry.user_id == user_id)
        if not include_archived:
            q = q.filter(JournalEntry.is_archived.is_(False))
        if not include_drafts:
            q = q.filter(JournalEntry.is_draft.is_(False))
        if favorites_only:
            q = q.filter(JournalEntry.is_favorite.is_(True))
        if start_date:
            q = q.filter(JournalEntry.created_at >= start_date)
        if end_date:
            q = q.filter(JournalEntry.created_at <= end_date)

        if tag:
            tag_row = (
                db.query(JournalTag)
                .filter(JournalTag.user_id == user_id, JournalTag.name == tag.lower())
                .first()
            )
            if not tag_row:
                return []
            entry_ids = [
                t.entry_id
                for t in db.query(JournalEntryTag)
                .filter(JournalEntryTag.tag_id == tag_row.id)
                .all()
            ]
            if not entry_ids:
                return []
            q = q.filter(JournalEntry.id.in_(entry_ids))

        q = q.order_by(JournalEntry.created_at.desc()).offset(offset).limit(limit)
        return [_serialize_entry(e, db=db) for e in q.all()]
    finally:
        db.close()


def search_entries(user_id: int, query: str, limit: int = 30) -> List[Dict[str, object]]:
    """Naive full-text search across title and body."""
    db = SessionLocal()
    try:
        if not query or not query.strip():
            return []
        like = f"%{query.strip()}%"
        rows = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                or_(JournalEntry.body.ilike(like), JournalEntry.title.ilike(like)),
            )
            .order_by(JournalEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_serialize_entry(e, db=db, include_body=True, highlight=query) for e in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def _attach_tags(db, user_id: int, entry_id: int, tag_names: Iterable[str]) -> None:
    for raw in tag_names:
        name = (raw or "").strip().lower()[:80]
        if not name:
            continue
        tag = (
            db.query(JournalTag)
            .filter(JournalTag.user_id == user_id, JournalTag.name == name)
            .first()
        )
        if not tag:
            tag = JournalTag(user_id=user_id, name=name)
            db.add(tag)
            db.flush()
        db.add(JournalEntryTag(entry_id=entry_id, tag_id=tag.id))


def _clear_entry_tags(db, entry_id: int) -> None:
    db.query(JournalEntryTag).filter(JournalEntryTag.entry_id == entry_id).delete()


def list_tags(user_id: int) -> List[Dict[str, object]]:
    """Return tags with usage counts."""
    db = SessionLocal()
    try:
        tags = db.query(JournalTag).filter(JournalTag.user_id == user_id).all()
        result: List[Dict[str, object]] = []
        for tag in tags:
            count = (
                db.query(JournalEntryTag)
                .filter(JournalEntryTag.tag_id == tag.id)
                .count()
            )
            result.append(
                {
                    "id": tag.id,
                    "name": tag.name,
                    "color": tag.color,
                    "description": tag.description,
                    "usage_count": count,
                }
            )
        result.sort(key=lambda r: r["usage_count"], reverse=True)
        return result
    finally:
        db.close()


def rename_tag(user_id: int, tag_id: int, new_name: str) -> bool:
    db = SessionLocal()
    try:
        tag = (
            db.query(JournalTag)
            .filter(JournalTag.id == tag_id, JournalTag.user_id == user_id)
            .first()
        )
        if not tag:
            return False
        tag.name = new_name.strip().lower()[:80]
        db.commit()
        return True
    finally:
        db.close()


def delete_tag(user_id: int, tag_id: int) -> bool:
    db = SessionLocal()
    try:
        tag = (
            db.query(JournalTag)
            .filter(JournalTag.id == tag_id, JournalTag.user_id == user_id)
            .first()
        )
        if not tag:
            return False
        db.query(JournalEntryTag).filter(JournalEntryTag.tag_id == tag.id).delete()
        db.delete(tag)
        db.commit()
        return True
    finally:
        db.close()


def get_entry_tags(entry_id: int) -> List[str]:
    db = SessionLocal()
    try:
        tag_ids = [
            r.tag_id
            for r in db.query(JournalEntryTag)
            .filter(JournalEntryTag.entry_id == entry_id)
            .all()
        ]
        if not tag_ids:
            return []
        names = [
            t.name
            for t in db.query(JournalTag).filter(JournalTag.id.in_(tag_ids)).all()
        ]
        return names
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def suggest_prompts(
    mood_score: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, object]]:
    """Suggest a few prompts based on mood and (optional) category.

    Heuristic: low mood -> self_compassion/joy; high mood -> growth/reflection;
    neutral -> mindfulness/reflection.
    """
    db = SessionLocal()
    try:
        q = db.query(JournalPrompt).filter(JournalPrompt.is_active.is_(True))
        if category:
            q = q.filter(JournalPrompt.category == category)
        else:
            preferred = _preferred_categories(mood_score)
            if preferred:
                q = q.filter(JournalPrompt.category.in_(preferred))
        prompts = q.limit(max(limit * 2, 10)).all()
        # Re-rank a touch by difficulty (favor easier for low moods).
        if mood_score is not None and mood_score < 4:
            prompts.sort(key=lambda p: {"easy": 0, "medium": 1, "hard": 2}.get(p.difficulty, 1))
        return [_serialize_prompt(p) for p in prompts[:limit]]
    finally:
        db.close()


def _preferred_categories(mood_score: Optional[float]) -> List[str]:
    if mood_score is None:
        return ["reflection", "mindfulness", "growth"]
    if mood_score < 4:
        return ["self_compassion", "joy", "mindfulness"]
    if mood_score < 6.5:
        return ["mindfulness", "reflection", "emotion"]
    return ["growth", "reflection", "relationships"]


def list_prompts(category: Optional[str] = None) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        q = db.query(JournalPrompt).filter(JournalPrompt.is_active.is_(True))
        if category:
            q = q.filter(JournalPrompt.category == category)
        return [_serialize_prompt(p) for p in q.order_by(JournalPrompt.category).all()]
    finally:
        db.close()


def random_prompt(mood_score: Optional[float] = None) -> Optional[Dict[str, object]]:
    """Pick a single prompt suited to the current mood."""
    import random
    suggestions = suggest_prompts(mood_score=mood_score, limit=15)
    if not suggestions:
        return None
    return random.choice(suggestions)


def _serialize_prompt(p: JournalPrompt) -> Dict[str, object]:
    return {
        "id": p.id,
        "text": p.text,
        "category": p.category,
        "difficulty": p.difficulty,
        "target_mood": p.target_mood,
        "estimated_minutes": p.estimated_minutes,
    }


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

def add_attachment(
    user_id: int, entry_id: int, kind: str, reference: str, caption: Optional[str] = None
) -> Dict[str, object]:
    db = SessionLocal()
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
            .first()
        )
        if not entry:
            raise LookupError("Entry not found.")
        att = JournalAttachment(
            entry_id=entry_id,
            user_id=user_id,
            kind=kind,
            reference=reference,
            caption=caption,
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        return {
            "id": att.id,
            "entry_id": att.entry_id,
            "kind": att.kind,
            "reference": att.reference,
            "caption": att.caption,
        }
    finally:
        db.close()


def list_attachments(entry_id: int) -> List[Dict[str, object]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(JournalAttachment)
            .filter(JournalAttachment.entry_id == entry_id)
            .all()
        )
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "reference": r.reference,
                "caption": r.caption,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def entry_stats(user_id: int, days: int = 30) -> Dict[str, object]:
    """Aggregate stats: counts, words, average mood, top keywords, longest streak."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_id,
                JournalEntry.created_at >= cutoff,
                JournalEntry.is_archived.is_(False),
            )
            .all()
        )
        if not rows:
            return {
                "window_days": days,
                "total_entries": 0,
                "total_words": 0,
                "average_words": 0,
                "average_mood": None,
                "active_days": 0,
                "longest_writing_streak": 0,
                "top_keywords": [],
            }

        total_words = sum(r.word_count or 0 for r in rows)
        avg_words = round(total_words / len(rows), 1)
        mood_scores = [r.mood_score for r in rows if r.mood_score is not None]
        avg_mood = round(sum(mood_scores) / len(mood_scores), 2) if mood_scores else None

        day_set = {r.created_at.date() for r in rows}
        longest_streak = _longest_consecutive(sorted(day_set))

        combined = " ".join(r.body for r in rows if r.body)
        keywords = _extract_keywords(combined, top_n=12)

        return {
            "window_days": days,
            "total_entries": len(rows),
            "total_words": total_words,
            "average_words": avg_words,
            "average_mood": avg_mood,
            "active_days": len(day_set),
            "longest_writing_streak": longest_streak,
            "top_keywords": keywords,
        }
    finally:
        db.close()


def _longest_consecutive(dates: List[object]) -> int:
    if not dates:
        return 0
    longest = current = 1
    for prev, curr in zip(dates, dates[1:]):
        delta = (curr - prev).days
        if delta == 1:
            current += 1
            longest = max(longest, current)
        elif delta == 0:
            continue
        else:
            current = 1
    return longest


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_entry(
    entry: JournalEntry,
    db,
    include_body: bool = False,
    highlight: Optional[str] = None,
) -> Dict[str, object]:
    tag_ids = [
        r.tag_id
        for r in db.query(JournalEntryTag)
        .filter(JournalEntryTag.entry_id == entry.id)
        .all()
    ]
    tags: List[str] = []
    if tag_ids:
        tags = [
            t.name
            for t in db.query(JournalTag).filter(JournalTag.id.in_(tag_ids)).all()
        ]

    body_excerpt = (entry.body or "")[:240]
    if include_body:
        body_field = entry.body
    else:
        body_field = body_excerpt

    return {
        "id": entry.id,
        "title": entry.title,
        "body": body_field,
        "excerpt": body_excerpt,
        "word_count": entry.word_count,
        "mood_score": entry.mood_score,
        "energy_level": entry.energy_level,
        "stress_level": entry.stress_level,
        "prompt_id": entry.prompt_id,
        "entry_type": entry.entry_type,
        "is_favorite": entry.is_favorite,
        "is_archived": entry.is_archived,
        "is_draft": entry.is_draft,
        "location": entry.location,
        "weather": entry.weather,
        "tags": tags,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }
