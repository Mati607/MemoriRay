# Habit Loop & Behavior Tracker

A habit-formation and behavior-tracking layer for MEMORIRAY. Models the
mechanics of habit loops (cue → action → reward), supports several
cadences, tracks streaks even when habits aren't strictly daily, captures
sleep / hydration / exercise / screen time and similar behavior events,
and produces both rule-based and Gemini-generated coaching notes.

## Modules

### `habit_models.py`
- `Habit`, `HabitCheckIn`, `HabitStreak` — habit definitions, per-day
  check-ins (`done` / `partial` / `skipped`), and a materialized streak
  row updated on every check-in
- `HabitStack` + `HabitStackStep` — anchor a chain of habits to one trigger
- `Routine`, `RoutineStep`, `RoutineRun` — ordered multi-step protocols
  (morning anchor, evening wind-down, hard-day reset, etc.) and per-run
  completion logs
- `BehaviorEvent` — generic event log with payload fields for sleep,
  exercise, hydration, meals, screen, caffeine, alcohol, outdoor, social,
  reading, creative, stretching, steps; each type has a `good_min`/`good_max`
- `HabitCoachNote` — persisted coach output (dismissible)
- 12 seeded habit templates + 5 seeded routine templates

### `habit_service.py`
- CRUD with cadence validation (`daily`, `weekdays`, `weekends`,
  `weekly_n` + `frequency_per_week`, `every_n_days` + `interval_days`)
- Cadence-aware "is this habit due today" logic
- Streak recomputation:
  - consecutive-day streaks (with weekday/weekend gap awareness)
  - weekly-N streaks measured in ISO weeks that hit the frequency target
- Habit stacks: anchor + ordered follow-ups
- Routines: create, update (steps replace), record run with completion ratio

### `behavior_tracker.py`
- Log/list/delete generic events with per-type unit defaults
- Daily totals per type, averages with in-good-range %
- `sleep_summary` (avg hours, quality, awakenings, sleep debt vs 8h)
- `dream_log` — only events with `dream_summary` set
- `daily_snapshot` — all of today's events grouped by type

### `habit_analytics.py`
- `completion_grid` — per-habit per-day matrix suitable for a heatmap
- `weekly_compliance` — hits-vs-target ratio per ISO week per habit
- `habit_health` — composite 0–100 score (completion + streak + diversity)
- `best_check_in_window` — morning / afternoon / evening / late-night
- `habit_vs_mood_correlation` — Pearson r between habit-done days and
  journal mood scores
- `routine_adherence` — per-routine average completion across recent runs
- `behavior_alignment` — % of behavior events landing inside their good range

### `habit_coach.py`
- Rule-based engine producing six categories of notes:
  - `starter` — onboarding when the user has no habits
  - `celebration` — long current streak
  - `recovery` — broken-but-previously-strong streak
  - `nudge` — habits in the list but never checked in
  - `behavior` — sleep debt, low hydration, etc.
  - `keystone` — keystone habit doing well; suggest stacking
  - `timing` — morning vs evening preference
- Gemini path uses the same prompt → JSON pattern as the journal
  reflection generator, with the same graceful fallback

### `habit_api.py`
55 endpoints under `/habits/*`. Highlights:

| Surface | Endpoints |
| --- | --- |
| Init / catalog | `POST /init`, `POST /seed-defaults`, `GET /catalog/...` |
| Habit CRUD | `POST /`, `PATCH /{id}`, `DELETE /{id}`, archive, get, list |
| Today | `GET /due/today` |
| Check-ins | `POST/GET/DELETE /check-ins[...]` |
| Stacks | `POST/GET/DELETE /stacks[...]` |
| Routines | `POST/GET/PATCH/DELETE /routines[...]` and `/routines/runs` |
| Behavior | events CRUD, sleep summary + dreams, totals, averages, snapshot |
| Analytics | health, grid, weekly-compliance, window, correlation, routines, alignment |
| Coach | generate, list, dismiss, delete |

The router is mounted from `bot.py` via `app.include_router(habit_router)`.
`init_habit_models()` is also called from `lifespan`, alongside the
existing journal init.

### `pages/6_habit_loop.py`
Streamlit page with six tabs: **Today**, **Habits**, **Routines & Stacks**,
**Behavior**, **Analytics**, **Coach**. Includes a one-click "Seed defaults"
button that loads the 12 habit and 5 routine templates.

## Smoke test (no LLM key needed)

```bash
poetry run uvicorn bot:app --reload
curl -X POST 'http://localhost:8000/habits/seed-defaults?user_id=1'
curl 'http://localhost:8000/habits/due/today?user_id=1'
curl -X POST http://localhost:8000/habits/check-ins \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"habit_id":1,"status":"done","quality":4}'
curl -X POST http://localhost:8000/habits/coach/generate \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"use_llm":false,"persist":false}'
```
