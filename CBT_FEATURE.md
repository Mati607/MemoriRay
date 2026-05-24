# CBT Workbook & Cognitive Restructuring System

A full CBT workbook on top of MEMORIRAY: thought records, cognitive
distortion analysis, worry trees, behavioral experiments, activity
scheduling (BA for depression), and core-belief tracking — with an
AI-assisted reframer that falls back to deterministic rules.

## Modules

### `cbt_models.py`
- `ThoughtRecord` — the 7-column CBT record (situation → automatic
  thought → emotion + intensity → evidence for/against → balanced
  thought → new emotion + behavior plan, with belief-strength % before
  and after)
- `CognitiveDistortion` catalog + `ThoughtRecordDistortion` link table
- `WorryTree` — surfaces the worry, classifies solvable vs unsolvable,
  branches to action plan or let-go strategy
- `BehavioralExperiment` — target belief, prediction, design, outcome,
  surprise factor, belief drop, learning
- `ActivitySchedule` — Behavioral Activation entries with pleasure /
  mastery / energy-after ratings
- `CoreBelief` + `CoreBeliefRating` — track strength of a belief and an
  alternative belief over time
- `WorksheetTemplate` — catalog of reusable worksheets
- 12 seeded distortions with detection keywords, regex patterns,
  reframe guidance, and severity weights
- 8 seeded worksheet templates (thought record, decatastrophizing,
  worry tree, behavioral experiment, behavioral activation, core belief
  examination, self-compassion letter, anger record)

### Service layer
- `thought_record_service.py` — CRUD, draft → complete progression,
  distortion attach/detach with auto-detected flag, intensity & belief
  shift metrics, aggregate shift-success rate, emotion breakdown, search
- `cbt_distortion_analyzer.py` — keyword + regex heuristic scoring
  against the catalog; `auto_tag_record()` persists high-confidence
  matches as `auto_detected=True`
- `cbt_worksheets.py` — services for worry trees, behavioral
  experiments, activity scheduling, and core beliefs (with ratings
  history and history-aware activity suggestions)
- `cbt_analytics.py` — distortion leaderboard, reframe success,
  worry split, experiment learning rate, activity balance, core-belief
  drift, composite 0–100 engagement score, and `master_summary()`
- `cbt_reframer.py` — generates 2–4 candidate reframes with rationale
  and Socratic questions; Gemini when a key is set, deterministic
  fallback (soften absolutes, third-person view, both/and framing)

### API (`cbt_api.py`)
57 endpoints under `/cbt/*`:

| Surface | Endpoints |
| --- | --- |
| Init | `POST /init` |
| Thought records | CRUD, complete, search, list, get distortions |
| Distortions | catalog, `POST /distortions/detect`, attach/detach |
| Worry trees | create, classify, plan (solvable / unsolvable), finish |
| Experiments | create, record outcome, set status, list, get, delete |
| Activities | schedule, complete, skip, list, delete, suggest-from-history |
| Core beliefs | add, update, rate, list, history, delete |
| Worksheets | list, get by key |
| Reframer | `POST /reframer` |
| Analytics | distortions, reframe success, worry, experiments, activity, belief drift, engagement, master-summary |

The router is mounted from `bot.py` via `app.include_router(cbt_router)`
and `init_cbt_models()` is called from `lifespan` alongside the other
init hooks. No existing endpoints touched.

### UI (`pages/7_cbt_workbook.py`)
Six-tab Streamlit page:
1. **Thought Records** — write the record, auto-detect distortions,
   call the reframer, complete the reframe
2. **Worry Tree** — classify, plan branch, finish
3. **Experiments** — design, conduct, record outcome with surprise factor
4. **Activity Schedule** — schedule pleasure/mastery, mark complete with
   ratings, see suggestions
5. **Core Beliefs** — rate over time, line chart shows core vs alternative
6. **Analytics** — engagement score, reframe success metrics, distortion
   leaderboard, worry split, activity balance, belief drift

## Why the fallback?

The reframer and analyzer both work without an LLM key. The reframer's
rule-based path produces three candidates: a softened-absolutes version,
a third-person externalization, and a both/and balanced thought. This
keeps the feature useful in tests, demos, and when the model call fails.

## Quick smoke test (no key needed)

```bash
poetry run uvicorn bot:app --reload
curl -X POST http://localhost:8000/cbt/distortions/detect \
  -H 'Content-Type: application/json' \
  -d '{"text":"I always mess everything up","top_n":3}'
curl -X POST http://localhost:8000/cbt/thought-records \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"situation":"Job interview","automatic_thought":"They will never hire me","primary_emotion":"anxious","emotion_intensity":80,"belief_in_original_thought":75}'
curl -X POST http://localhost:8000/cbt/reframer \
  -H 'Content-Type: application/json' \
  -d '{"automatic_thought":"They will never hire me","primary_emotion":"anxious","use_llm":false}'
```
