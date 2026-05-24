"""
AI-assisted reframer for CBT thought records.

Given an automatic thought (and optional context: situation, emotion,
detected distortions), produce 2-4 candidate reframes plus questions
that might unstick the user. Uses Gemini when a key is set, with a
deterministic rule-based fallback so the feature works offline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from cbt_distortion_analyzer import detect_for_thought


@dataclass
class ReframeSuggestion:
    balanced_thought: str
    evidence_against: List[str]
    questions: List[str]
    rationale: str
    confidence: float


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def suggest_reframes(
    automatic_thought: str,
    situation: Optional[str] = None,
    primary_emotion: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    distortion_keys: Optional[List[str]] = None,
    use_llm: bool = True,
) -> List[Dict[str, object]]:
    """Return a ranked list of candidate reframes."""
    if not automatic_thought or not automatic_thought.strip():
        return []

    detected = detect_for_thought(automatic_thought, top_n=4)
    keys = distortion_keys or [d["key"] for d in detected]

    suggestions: List[ReframeSuggestion] = []
    if use_llm and _has_genai_key():
        try:
            suggestions = _generate_with_llm(
                automatic_thought=automatic_thought,
                situation=situation,
                primary_emotion=primary_emotion,
                emotion_intensity=emotion_intensity,
                detected_distortions=detected,
            )
        except Exception:
            suggestions = []
    if not suggestions:
        suggestions = _generate_with_rules(
            automatic_thought=automatic_thought,
            primary_emotion=primary_emotion,
            distortion_keys=keys,
        )

    return [
        {
            "balanced_thought": s.balanced_thought,
            "evidence_against": s.evidence_against,
            "questions": s.questions,
            "rationale": s.rationale,
            "confidence": s.confidence,
        }
        for s in suggestions
    ]


# ---------------------------------------------------------------------------
# Rule-based path
# ---------------------------------------------------------------------------

_QUESTION_BANK = {
    "all_or_nothing": [
        "What would 'good enough' look like here?",
        "Where on the 0-100 spectrum does this really sit?",
    ],
    "catastrophizing": [
        "If the worst happened, how would you cope a week later?",
        "What's the most realistic outcome — not the worst, not the best?",
    ],
    "mind_reading": [
        "What other explanations could account for their behavior?",
        "If you asked directly, what would you ask?",
    ],
    "fortune_telling": [
        "What's your evidence that this is what will happen?",
        "How often have similar predictions been right?",
    ],
    "emotional_reasoning": [
        "What does the evidence say, separate from how you feel?",
        "Is it possible to feel something strongly and still be mistaken?",
    ],
    "should_statements": [
        "Whose rule is this — yours, or one you've inherited?",
        "What would change if you replaced 'should' with 'I'd prefer'?",
    ],
    "labeling": [
        "Is this a behavior you can describe, rather than an identity?",
        "Would you label a friend this way after one situation?",
    ],
    "personalization": [
        "What other factors influenced this outcome?",
        "What part of this is genuinely within your control?",
    ],
    "mental_filter": [
        "What else happened that you're filtering out?",
        "If you described the day to a friend, what positives would you include?",
    ],
    "discounting_positive": [
        "If a friend got this same feedback, would you dismiss it?",
        "What would it mean to let this count?",
    ],
    "magnification_minimization": [
        "Are you using the same yardstick for the negative and the positive?",
        "If a friend told you this story, how big would you say each thing is?",
    ],
    "overgeneralization": [
        "Is one event evidence of a permanent rule?",
        "What counter-examples exist, even small ones?",
    ],
}


def _generate_with_rules(
    automatic_thought: str,
    primary_emotion: Optional[str],
    distortion_keys: List[str],
) -> List[ReframeSuggestion]:
    thought = automatic_thought.strip()
    suggestions: List[ReframeSuggestion] = []

    # Suggestion 1: soften absolutes
    softened = _soften_absolutes(thought)
    if softened and softened.lower() != thought.lower():
        suggestions.append(
            ReframeSuggestion(
                balanced_thought=softened,
                evidence_against=["The original framing uses absolute language that rarely matches reality."],
                questions=_questions_for(distortion_keys, fallback="What would a more measured version of this sound like?"),
                rationale="Replaces absolutes (always/never/completely) with measured language.",
                confidence=0.55,
            )
        )

    # Suggestion 2: third-person reframe
    third_person = _to_third_person(thought)
    if third_person:
        suggestions.append(
            ReframeSuggestion(
                balanced_thought=third_person,
                evidence_against=[
                    "Seeing the thought from outside makes it easier to notice the rough edges.",
                ],
                questions=[
                    "If a close friend had this thought, what would you say to them?",
                    "What part of this would change if you wrote it as a third person?",
                ],
                rationale="Externalizes the thought to reduce fusion.",
                confidence=0.5,
            )
        )

    # Suggestion 3: balanced thought
    balanced = _balanced_thought(thought, primary_emotion)
    suggestions.append(
        ReframeSuggestion(
            balanced_thought=balanced,
            evidence_against=[
                "Notice what's true *and* what's not — both can coexist.",
            ],
            questions=_questions_for(distortion_keys, fallback="What's a version of this thought that's both honest and kinder?"),
            rationale="A both/and framing rather than either/or.",
            confidence=0.6,
        )
    )

    return suggestions[:3]


def _soften_absolutes(thought: str) -> str:
    replacements = [
        (r"\balways\b", "often"),
        (r"\bnever\b", "rarely"),
        (r"\bcompletely\b", "largely"),
        (r"\bperfectly\b", "well enough"),
        (r"\bnothing\b", "very little"),
        (r"\beverything\b", "a lot"),
        (r"\bevery (single )?time\b", "many times"),
    ]
    out = thought
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def _to_third_person(thought: str) -> str:
    if " I " not in f" {thought} " and not thought.lower().startswith("i "):
        return ""
    swapped = re.sub(r"\bI\b", "they", thought)
    swapped = re.sub(r"\bI'm\b", "they're", swapped, flags=re.IGNORECASE)
    swapped = re.sub(r"\bme\b", "them", swapped, flags=re.IGNORECASE)
    swapped = re.sub(r"\bmy\b", "their", swapped, flags=re.IGNORECASE)
    return f"From outside, I might say: '{swapped}'"


def _balanced_thought(thought: str, primary_emotion: Optional[str]) -> str:
    base = thought.strip().rstrip(".")
    if primary_emotion:
        return (
            f"Even though I'm feeling {primary_emotion} and I'm noticing the thought "
            f"'{base}', I can hold space for the possibility that it isn't the whole picture."
        )
    return (
        f"I'm noticing the thought '{base}'. It might be partly true, and it's also "
        "probably not the whole story — both can be true at once."
    )


def _questions_for(distortion_keys: List[str], fallback: str) -> List[str]:
    out: List[str] = []
    for key in distortion_keys[:2]:
        for q in _QUESTION_BANK.get(key, []):
            out.append(q)
            if len(out) >= 4:
                break
    if not out:
        out.append(fallback)
        out.append("What would you tell a close friend who shared this thought?")
    return out


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------

def _has_genai_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _generate_with_llm(
    automatic_thought: str,
    situation: Optional[str],
    primary_emotion: Optional[str],
    emotion_intensity: Optional[float],
    detected_distortions: List[Dict[str, object]],
) -> List[ReframeSuggestion]:
    from google import genai

    prompt = _build_prompt(
        automatic_thought=automatic_thought,
        situation=situation,
        primary_emotion=primary_emotion,
        emotion_intensity=emotion_intensity,
        detected_distortions=detected_distortions,
    )

    client = genai.Client()
    model_name = os.getenv("MEMORIRAY_CBT_MODEL", "gemini-2.0-flash-exp")
    response = client.models.generate_content(model=model_name, contents=prompt)
    text = getattr(response, "text", "") or ""
    parsed = _parse_response(text)

    out: List[ReframeSuggestion] = []
    for item in parsed.get("suggestions", []) or []:
        balanced = item.get("balanced_thought") or ""
        if not balanced:
            continue
        out.append(
            ReframeSuggestion(
                balanced_thought=balanced,
                evidence_against=list(item.get("evidence_against", []) or []),
                questions=list(item.get("questions", []) or []),
                rationale=item.get("rationale", "") or "",
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return out


def _build_prompt(
    automatic_thought: str,
    situation: Optional[str],
    primary_emotion: Optional[str],
    emotion_intensity: Optional[float],
    detected_distortions: List[Dict[str, object]],
) -> str:
    detected_list = "\n".join(
        f"- {d['name']} (score {d['score']:.2f})" for d in detected_distortions[:4]
    )
    return f"""You are a kind, evidence-based CBT companion.
Generate 2-4 candidate reframes for the user's automatic thought.

Respond ONLY with JSON, no prose, no code fences. Schema:
{{
  "suggestions": [
    {{
      "balanced_thought": "a kind, honest, more measured version of the thought",
      "evidence_against": ["short bullet point", "..."],
      "questions": ["one open question that could unstick the user", "..."],
      "rationale": "one sentence explaining what shifted",
      "confidence": 0.7
    }}
  ]
}}

Situation: {situation or "(unspecified)"}
Primary emotion: {primary_emotion or "(unspecified)"} (intensity {emotion_intensity if emotion_intensity is not None else "?"})
Automatic thought: {automatic_thought}

Detected distortions (rule-based heuristic, may be wrong):
{detected_list or "(none detected)"}
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
