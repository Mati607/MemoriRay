"""
Cognitive distortion analyzer.

Given a piece of text (typically an automatic thought), score each
distortion in the catalog based on keyword and regex hits. Used to:
  - suggest distortions when the user is writing a thought record
  - auto-tag a new record with high-confidence matches
  - inform the reframer / AI coach

A pure-Python heuristic by design — the LLM-based reframer in
cbt_reframer.py is the deeper path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from database import SessionLocal
from cbt_models import CognitiveDistortion


@dataclass
class DistortionScore:
    distortion_id: int
    key: str
    name: str
    score: float            # 0..1 normalized
    keyword_hits: int
    pattern_hits: int
    matched_terms: List[str]
    reframe_guidance: Optional[str]


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def analyze_text(text: str, threshold: float = 0.0) -> List[DistortionScore]:
    """Score each distortion against the text. Returns sorted desc by score.

    `threshold` filters out very weak matches (0..1).
    """
    if not text or not text.strip():
        return []
    cleaned = text.lower()
    db = SessionLocal()
    try:
        distortions = db.query(CognitiveDistortion).all()
        if not distortions:
            return []

        scores: List[DistortionScore] = []
        for d in distortions:
            score = _score_distortion(cleaned, d)
            if score.score >= threshold:
                scores.append(score)
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores
    finally:
        db.close()


def auto_tag_record(record_id: int, text: str, min_score: float = 0.35) -> List[Dict[str, object]]:
    """Analyze and persist links between record and detected distortions."""
    from thought_record_service import attach_distortion, get_record

    record = _get_record_user(record_id)
    if not record:
        return []

    detected = analyze_text(text, threshold=min_score)
    out: List[Dict[str, object]] = []
    for score in detected:
        link = attach_distortion(
            user_id=record["user_id"],
            record_id=record_id,
            distortion_id=score.distortion_id,
            confidence=score.score,
            auto_detected=True,
        )
        out.append({**link, "score": score.score, "matched_terms": score.matched_terms})
    return out


def detect_for_thought(thought_text: str, top_n: int = 5) -> List[Dict[str, object]]:
    """Convenience wrapper used by the API / UI."""
    scores = analyze_text(thought_text, threshold=0.15)
    return [
        {
            "distortion_id": s.distortion_id,
            "key": s.key,
            "name": s.name,
            "score": round(s.score, 3),
            "keyword_hits": s.keyword_hits,
            "pattern_hits": s.pattern_hits,
            "matched_terms": s.matched_terms,
            "reframe_guidance": s.reframe_guidance,
        }
        for s in scores[:top_n]
    ]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z']+")


def _score_distortion(text_lower: str, distortion: CognitiveDistortion) -> DistortionScore:
    keywords = [
        k.strip().lower()
        for k in (distortion.detection_keywords or "").split(",")
        if k.strip()
    ]
    matched_terms: List[str] = []
    keyword_hits = 0
    for kw in keywords:
        if kw and kw in text_lower:
            keyword_hits += 1
            matched_terms.append(kw)

    pattern_hits = 0
    if distortion.detection_patterns:
        try:
            pattern = re.compile(distortion.detection_patterns, re.IGNORECASE)
            for m in pattern.finditer(text_lower):
                pattern_hits += 1
                matched_terms.append(m.group(0))
        except re.error:
            # Bad regex in catalog — skip rather than crash.
            pattern_hits = 0

    # Normalize to [0, 1]: keyword hits saturate at 3, pattern hits at 2.
    keyword_weight = min(keyword_hits, 3) / 3.0
    pattern_weight = min(pattern_hits, 2) / 2.0
    raw = (0.55 * keyword_weight) + (0.45 * pattern_weight)
    severity = float(distortion.severity_weight or 1.0)
    score = max(0.0, min(1.0, raw * severity))

    return DistortionScore(
        distortion_id=distortion.id,
        key=distortion.key,
        name=distortion.name,
        score=score,
        keyword_hits=keyword_hits,
        pattern_hits=pattern_hits,
        matched_terms=list(dict.fromkeys(matched_terms))[:10],
        reframe_guidance=distortion.reframe_guidance,
    )


def _get_record_user(record_id: int) -> Optional[Dict[str, object]]:
    from cbt_models import ThoughtRecord
    db = SessionLocal()
    try:
        row = db.query(ThoughtRecord).filter(ThoughtRecord.id == record_id).first()
        if not row:
            return None
        return {"user_id": row.user_id, "record_id": row.id}
    finally:
        db.close()
