# Mindful Journal & Reflection System

A multi-surface journaling feature on top of MEMORIRAY's existing FastAPI +
Streamlit + SQLAlchemy stack. Adds long-form journaling, gratitude practice,
mindfulness session tracking, and AI-augmented reflections — with a
deterministic fallback so the feature degrades gracefully without an LLM key.

## What's included

### Data layer (`journal_models.py`)
- `JournalEntry`, `JournalTag`, `JournalEntryTag`, `JournalPrompt`, `JournalAttachment`
- `GratitudeEntry`, `GratitudeStreak`
- `MindfulnessSession`, `MindfulnessTechnique`
- `ReflectionSnapshot`, `ReflectionFeedback`
- 20 seeded journal prompts across 7 categories (reflection, mindfulness,
  growth, self-compassion, emotion, relationships, joy)
- 10 seeded mindfulness techniques (breathing, body scan, grounding,
  compassion, awareness, movement, joy)

### Services
- `journal_service.py` — CRUD, search, tagging, prompt suggestion by mood,
  attachments, lightweight text analysis (keywords, word counts, readability)
- `gratitude_service.py` — gratitude entries, streak bookkeeping with
  recompute-on-delete, category breakdown, suggested under-used categories
- `mindfulness_service.py` — session recording, technique recommendation by
  mood and available time, practice summary, day streaks, technique
  effectiveness ranking, best time-of-day analysis
- `reflection_generator.py` — generates weekly/daily/monthly reflections
  with Gemini (`google-genai`) when a key is present, otherwise a rule-based
  fallback covering themes, mood trend, growth signals, and suggested focus
- `journal_analytics.py` — composite 0–100 wellbeing score, activity
  heatmap, mood-vs-practice Pearson correlation, daily and weekly digests,
  writing consistency metrics

### API layer (`journal_api.py`)
44 new endpoints under `/journal/...`:

| Surface | Endpoints |
| --- | --- |
| Entries | `POST/GET/PATCH/DELETE /journal/entries[...]`, search, stats |
| Tags | list, rename, delete |
| Prompts | list / suggest / random |
| Gratitude | add, batch, list, delete, streak, breakdown, suggested categories, today |
| Mindfulness sessions | record, list, get, delete, feedback |
| Mindfulness techniques | list, get, recommend |
| Mindfulness summary | summary, streak, effectiveness, best-time |
| Reflections | generate, list, get, feedback |
| Analytics | wellbeing, heatmap, correlation, daily/weekly digest, consistency |

The router is mounted from `bot.py` via `app.include_router(journal_router)`
without touching existing endpoints.

### UI (`pages/5_mindful_journal.py`)
Streamlit page with six tabs:
1. **New Entry** — prompt browser/random picker, free-form writing with
   mood/energy/stress sliders, tags, drafts
2. **Library** — search, favorites, archive toggle, delete
3. **Gratitude** — streak hero, add form with categories, distribution chart
4. **Mindfulness** — technique recommender, session recorder, summary stats,
   per-technique effectiveness
5. **Reflections** — generate weekly/daily/monthly summaries, view history
6. **Insights** — wellbeing score, consistency, mood-vs-practice correlation,
   heatmap, today's digest

## Why a fallback?

The reflection generator uses Gemini when `GOOGLE_API_KEY` or
`GEMINI_API_KEY` is set, but the same code path produces a useful summary
without it. This keeps the feature working in tests, offline demos, and
when an LLM call fails for any reason — the user always gets a reflection.

## Quick smoke test

```bash
poetry run uvicorn bot:app --reload
# Generate prompts and a reflection without the LLM:
curl http://localhost:8000/journal/prompts/random?mood_score=4
curl -X POST http://localhost:8000/journal/entries \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "body": "Today felt okay.", "mood_score": 6}'
curl -X POST http://localhost:8000/journal/reflections/generate \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "window_kind": "weekly", "use_llm": false}'
```

## Schema notes

All new tables use the shared `Base` from `database.py`, so
`init_journal_models()` (called automatically from `lifespan`) creates them
alongside the existing user/mood/exercise tables. The function is
idempotent — safe to run on every startup.
