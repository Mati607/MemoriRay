"""
Streamlit page: Habit Loop & Behavior Tracker.

Tabs:
  - Today (habits due, check-ins)
  - Habits (create, list, archive, delete)
  - Routines & Stacks (multi-step protocols + habit chains)
  - Behavior (sleep, hydration, exercise, etc. log)
  - Analytics (heatmap-style grid, weekly compliance, health score)
  - Coach (AI/rule-based coaching notes)
"""

import streamlit as st
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000"


def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()


check_authentication()


st.set_page_config(page_title="Habit Loop", page_icon="🌀", layout="wide")

st.markdown(
    """
    <style>
        :root {
            --hl-bg: #FFFBEB;
            --hl-card: #FFF7D6;
            --hl-ink: #3F3D2E;
            --hl-accent: #F4D06F;
            --hl-accent-2: #9ED2C6;
            --hl-accent-3: #C7E9B0;
            --hl-muted: #918C76;
        }
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: var(--hl-bg) !important;
            color: var(--hl-ink) !important;
        }
        .hl-card { background: var(--hl-card); border-radius: 14px; padding: 18px 20px; margin-bottom: 14px; border: 1px solid rgba(63,61,46,0.08); }
        .hl-pill { display: inline-block; background: var(--hl-accent-3); border-radius: 999px; padding: 2px 10px; margin-right: 6px; font-size: 0.78rem; color: var(--hl-ink); }
        .hl-pill.warn { background: #F8A8A8; }
        .hl-pill.go { background: var(--hl-accent); }
        .hl-stat { font-size: 1.8rem; font-weight: 700; }
        .hl-grid-row { display: flex; gap: 4px; flex-wrap: wrap; }
        .hl-cell { width: 16px; height: 16px; border-radius: 3px; background: #efe4b8; display: inline-block; }
        .hl-cell.done { background: #6BBF85; }
        .hl-cell.partial { background: #E9C26B; }
        .hl-cell.skipped { background: #C77B7B; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌀 Habit Loop")
st.markdown("Build the small, repeatable shapes of your days.")

user_id = st.session_state.user_id


def _get(path, **params):
    try:
        params = {k: v for k, v in params.items() if v is not None}
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}")
    except Exception as exc:
        st.error(f"GET {path} failed: {exc}")
    return None


def _post(path, body):
    try:
        resp = requests.post(f"{API_BASE}{path}", json=body, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        st.error(f"POST {path} failed: {exc}")
    return None


def _patch(path, body):
    try:
        resp = requests.patch(f"{API_BASE}{path}", json=body, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}")
    except Exception as exc:
        st.error(f"PATCH {path} failed: {exc}")
    return None


def _delete(path, **params):
    try:
        params = {k: v for k, v in params.items() if v is not None}
        resp = requests.delete(f"{API_BASE}{path}", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}")
    except Exception as exc:
        st.error(f"DELETE {path} failed: {exc}")
    return None


tabs = st.tabs([
    "📅 Today",
    "🌱 Habits",
    "🧩 Routines & Stacks",
    "💧 Behavior",
    "📊 Analytics",
    "🧭 Coach",
])


# ---------------------------------------------------------------------------
# Tab 1: Today
# ---------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Habits due today")

    if st.button("✨ Seed default habits + routines", help="Adds 12 starter habits and 5 routines"):
        res = _post(f"/habits/seed-defaults?user_id={user_id}", body={})
        if res:
            st.success(f"Added {res.get('habits_seeded',0)} habits and {res.get('routines_seeded',0)} routines.")
            st.rerun()

    data = _get("/habits/due/today", user_id=user_id) or {}
    items = data.get("habits", [])
    if not items:
        st.info("No habits set up yet. Seed defaults or create your first habit in the Habits tab.")
    else:
        for h in items:
            streak = h.get("streak", {})
            status_pill = {
                "done": "<span class='hl-pill go'>done</span>",
                "partial": "<span class='hl-pill'>partial</span>",
                "skipped": "<span class='hl-pill warn'>skipped</span>",
                "pending": "<span class='hl-pill'>pending</span>",
            }.get(h.get("today_status", "pending"), "")
            st.markdown(
                f"<div class='hl-card'><b>{h['name']}</b> "
                f"<span class='hl-pill'>{h['category']}</span>"
                f"<span class='hl-pill'>{h['cadence']}</span>"
                f"<span class='hl-pill'>streak {streak.get('current',0)}</span>"
                f"{status_pill}"
                + (f"<br><span class='hl-pill'>cue: {h['cue']}</span>" if h.get('cue') else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            cols = st.columns([1, 1, 1, 5])
            with cols[0]:
                if st.button("✅ Done", key=f"done-{h['id']}"):
                    _post(
                        "/habits/check-ins",
                        {"user_id": user_id, "habit_id": h["id"], "status": "done"},
                    )
                    st.rerun()
            with cols[1]:
                if st.button("◐ Partial", key=f"part-{h['id']}"):
                    _post(
                        "/habits/check-ins",
                        {"user_id": user_id, "habit_id": h["id"], "status": "partial"},
                    )
                    st.rerun()
            with cols[2]:
                if st.button("✖️ Skip", key=f"skip-{h['id']}"):
                    _post(
                        "/habits/check-ins",
                        {"user_id": user_id, "habit_id": h["id"], "status": "skipped"},
                    )
                    st.rerun()


# ---------------------------------------------------------------------------
# Tab 2: Habits
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Add a habit")
    with st.form("new_habit"):
        nh1, nh2 = st.columns(2)
        with nh1:
            name = st.text_input("Name", "")
            category = st.selectbox(
                "Category",
                ["movement", "mind", "sleep", "nutrition", "hydration", "social",
                 "creative", "work", "learning", "finance", "home", "digital",
                 "spiritual", "general"],
            )
            cadence = st.selectbox(
                "Cadence",
                ["daily", "weekdays", "weekends", "weekly_n", "every_n_days"],
            )
            freq = st.number_input("Times per week (weekly_n only)", min_value=1, max_value=7, value=3)
            interval = st.number_input("Interval days (every_n_days only)", min_value=1, max_value=30, value=2)
        with nh2:
            difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"])
            target_minutes = st.number_input("Target minutes (optional)", min_value=0, value=0)
            target_streak = st.number_input("Target streak (optional)", min_value=0, value=0)
            cue = st.text_input("Cue (when/where)")
            reward = st.text_input("Reward")
            is_keystone = st.toggle("Keystone habit", value=False)

        motivation = st.text_area("Motivation (why this matters)", height=80)
        submitted = st.form_submit_button("Create habit", type="primary")
        if submitted:
            if not name.strip():
                st.warning("Name is required.")
            else:
                payload = {
                    "user_id": user_id,
                    "name": name,
                    "category": category,
                    "cadence": cadence,
                    "difficulty": difficulty,
                    "frequency_per_week": int(freq) if cadence == "weekly_n" else None,
                    "interval_days": int(interval) if cadence == "every_n_days" else None,
                    "target_minutes": int(target_minutes) or None,
                    "target_streak": int(target_streak) or None,
                    "cue": cue or None,
                    "reward": reward or None,
                    "is_keystone": is_keystone,
                    "motivation": motivation or None,
                }
                res = _post("/habits", payload)
                if res:
                    st.success("Created.")
                    st.rerun()

    st.subheader("Your habits")
    show_archived = st.toggle("Show archived", key="show_arch")
    data = _get("/habits", user_id=user_id, include_archived=show_archived) or {}
    for h in data.get("habits", []):
        streak = h.get("streak", {})
        keystone = "🌟" if h.get("is_keystone") else ""
        archived = "📦" if h.get("is_archived") else ""
        st.markdown(
            f"<div class='hl-card'><b>{keystone} {h['name']} {archived}</b>"
            f"<span class='hl-pill'>{h['category']}</span>"
            f"<span class='hl-pill'>{h['cadence']}</span>"
            f"<span class='hl-pill'>current streak: {streak.get('current',0)}</span>"
            f"<span class='hl-pill'>longest: {streak.get('longest',0)}</span>"
            + (f"<br><i>{h.get('description','')}</i>" if h.get('description') else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns([1, 1, 1, 6])
        with c1:
            if st.button("✅ Check in", key=f"chk-{h['id']}"):
                _post("/habits/check-ins", {"user_id": user_id, "habit_id": h["id"], "status": "done"})
                st.rerun()
        with c2:
            label = "Unarchive" if h.get("is_archived") else "Archive"
            if st.button(label, key=f"arch-{h['id']}"):
                _post(f"/habits/{h['id']}/archive?user_id={user_id}&archived={'false' if h.get('is_archived') else 'true'}", body={})
                st.rerun()
        with c3:
            if st.button("🗑️", key=f"del-{h['id']}"):
                _delete(f"/habits/{h['id']}", user_id=user_id)
                st.rerun()


# ---------------------------------------------------------------------------
# Tab 3: Routines & Stacks
# ---------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Routines")
    routines = (_get("/habits/routines", user_id=user_id) or {}).get("routines", [])
    for r in routines:
        st.markdown(
            f"<div class='hl-card'><b>{r['name']}</b>"
            + (f" <span class='hl-pill'>{r['when_to_run']}</span>" if r.get('when_to_run') else "")
            + (f" <span class='hl-pill'>{r.get('estimated_minutes', 0)} min</span>" if r.get('estimated_minutes') else "")
            + "<ol>"
            + "".join(f"<li>{step['text']}</li>" for step in r.get("steps", []))
            + "</ol></div>",
            unsafe_allow_html=True,
        )
        run_cols = st.columns([2, 1, 1, 4])
        with run_cols[0]:
            completed = st.slider(f"Completed steps for {r['name']}", 0, len(r.get("steps") or []) or 1, 0, key=f"comp-{r['id']}")
        with run_cols[1]:
            if st.button("Log run", key=f"run-{r['id']}"):
                _post(
                    "/habits/routines/runs",
                    {"user_id": user_id, "routine_id": r["id"], "completed_steps": completed},
                )
                st.rerun()
        with run_cols[2]:
            if st.button("Delete", key=f"rdel-{r['id']}"):
                _delete(f"/habits/routines/{r['id']}", user_id=user_id)
                st.rerun()

    st.subheader("Create a routine")
    with st.form("new_routine"):
        rname = st.text_input("Routine name")
        rwhen = st.text_input("When to run (e.g. 'within 30 minutes of waking')")
        rmin = st.number_input("Estimated minutes", min_value=1, max_value=180, value=15)
        rsteps = st.text_area("Steps (one per line)", height=150)
        if st.form_submit_button("Create routine"):
            steps = [{"text": line.strip()} for line in rsteps.split("\n") if line.strip()]
            if not rname.strip() or not steps:
                st.warning("Routine needs a name and at least one step.")
            else:
                _post(
                    "/habits/routines",
                    {
                        "user_id": user_id,
                        "name": rname,
                        "when_to_run": rwhen or None,
                        "estimated_minutes": rmin,
                        "steps": steps,
                    },
                )
                st.rerun()

    st.subheader("Habit stacks")
    stacks = (_get("/habits/stacks", user_id=user_id) or {}).get("stacks", [])
    for s in stacks:
        st.markdown(
            f"<div class='hl-card'><b>{s['name']}</b> <span class='hl-pill'>anchor #{s['anchor_habit_id']}</span>"
            + (f"<br>{s.get('description','')}" if s.get('description') else "")
            + f"<br>follow-ups: {[step['habit_id'] for step in s.get('steps', [])]}"
            + "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Delete stack", key=f"sdel-{s['id']}"):
            _delete(f"/habits/stacks/{s['id']}", user_id=user_id)
            st.rerun()

    habits_for_stack = (_get("/habits", user_id=user_id) or {}).get("habits", [])
    if habits_for_stack:
        with st.form("new_stack"):
            stname = st.text_input("Stack name")
            anchor = st.selectbox(
                "Anchor habit",
                options=[h["id"] for h in habits_for_stack],
                format_func=lambda hid: next((h["name"] for h in habits_for_stack if h["id"] == hid), str(hid)),
            )
            follow_ups = st.multiselect(
                "Follow-up habits (in order)",
                options=[h["id"] for h in habits_for_stack],
                format_func=lambda hid: next((h["name"] for h in habits_for_stack if h["id"] == hid), str(hid)),
            )
            if st.form_submit_button("Create stack"):
                if stname.strip() and follow_ups:
                    _post(
                        "/habits/stacks",
                        {
                            "user_id": user_id,
                            "name": stname,
                            "anchor_habit_id": anchor,
                            "follow_up_habit_ids": follow_ups,
                        },
                    )
                    st.rerun()


# ---------------------------------------------------------------------------
# Tab 4: Behavior
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Log a behavior event")
    catalog = _get("/habits/catalog/event-types") or {"event_types": {}}
    event_types = list(catalog.get("event_types", {}).keys())
    bcol = st.columns(3)
    with bcol[0]:
        evt_type = st.selectbox("Type", event_types)
    with bcol[1]:
        value = st.number_input("Value", min_value=0.0, value=0.0, step=0.5)
    with bcol[2]:
        quality = st.slider("Quality", 0.0, 5.0, 3.0, 0.5)
    notes = st.text_input("Notes (optional)")
    if st.button("Log event", type="primary"):
        _post(
            "/habits/behavior/events",
            {
                "user_id": user_id,
                "event_type": evt_type,
                "value": value,
                "quality": quality,
                "notes": notes or None,
            },
        )
        st.rerun()

    st.subheader("Sleep")
    sleep = _get("/habits/behavior/sleep/summary", user_id=user_id, days=14) or {}
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Avg hours", sleep.get("average_hours") or "—")
    sc2.metric("Avg quality", sleep.get("average_quality") or "—")
    sc3.metric("Sleep debt", f"{sleep.get('sleep_debt_hours', 0)} h")
    sc4.metric("Samples", sleep.get("samples", 0))

    st.subheader("Recent events")
    events = (_get("/habits/behavior/events", user_id=user_id, days=14) or {}).get("events", [])
    for e in events[:30]:
        st.markdown(
            f"<div class='hl-card'><b>{e['event_type']}</b>"
            f"<span class='hl-pill'>{e.get('value', '—')} {e.get('value_unit') or ''}</span>"
            + (f"<span class='hl-pill'>quality {e['quality']}</span>" if e.get('quality') is not None else "")
            + f" <span class='hl-pill'>{e['occurred_at'][:10]}</span>"
            + (f"<br><i>{e['notes']}</i>" if e.get('notes') else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Averages")
    avg = (_get("/habits/behavior/averages", user_id=user_id, days=14) or {}).get("averages", {})
    if avg:
        cols = st.columns(min(4, len(avg)))
        for i, (typ, cfg) in enumerate(avg.items()):
            cols[i % len(cols)].metric(
                typ,
                f"{cfg['average']} {cfg.get('unit') or ''}",
                help=f"In good range {cfg['in_range_pct']}% of the time",
            )


# ---------------------------------------------------------------------------
# Tab 5: Analytics
# ---------------------------------------------------------------------------
with tabs[4]:
    health = _get("/habits/analytics/health", user_id=user_id, days=14)
    if health:
        h1, h2 = st.columns([1, 2])
        with h1:
            st.markdown(
                f"<div class='hl-card'><div class='hl-stat'>{health['score']}</div>"
                f"habit health — <i>{health['label']}</i></div>",
                unsafe_allow_html=True,
            )
        with h2:
            st.bar_chart(health["components"])

    st.subheader("30-day completion grid")
    grid = _get("/habits/analytics/grid", user_id=user_id, days=30) or {}
    for row in grid.get("habits", []):
        cells = "".join(
            f"<span class='hl-cell {d['status'] if d['status'] in ('done','partial','skipped') else ''}' title='{d['date']}: {d['status']}'></span>"
            for d in row["days"]
        )
        st.markdown(
            f"<div class='hl-card'><b>{row['name']}</b> "
            f"<span class='hl-pill'>{row['cadence']}</span>"
            f"<div class='hl-grid-row'>{cells}</div></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Weekly compliance")
    weekly = _get("/habits/analytics/weekly-compliance", user_id=user_id, weeks=8) or {}
    for h in weekly.get("compliance", []):
        weeks = h.get("weeks", [])
        chart_data = {f"W{w['iso_week']}": w["ratio"] for w in weeks}
        st.markdown(f"**{h['name']}** ({len(weeks)} weeks)")
        st.bar_chart(chart_data)

    st.subheader("Best check-in window")
    window = _get("/habits/analytics/window", user_id=user_id, days=60) or {}
    if window.get("buckets"):
        st.write(f"Best window: **{window.get('best_window', '—')}**")
        st.bar_chart(window["buckets"])

    st.subheader("Routine adherence")
    routines = (_get("/habits/analytics/routines", user_id=user_id, days=30) or {}).get("routines", [])
    if routines:
        for r in routines:
            st.write(f"• **{r['name']}** — avg {int(r['avg_completion']*100)}% over {r['runs']} runs")


# ---------------------------------------------------------------------------
# Tab 6: Coach
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Coach notes")
    c1, c2 = st.columns([1, 3])
    with c1:
        use_llm = st.toggle("Use AI (Gemini)", value=True, key="coach_llm")
    with c2:
        if st.button("🧭 Generate new notes", type="primary"):
            res = _post("/habits/coach/generate", {"user_id": user_id, "use_llm": use_llm, "persist": True})
            if res:
                st.success(f"Generated {len(res.get('notes', []))} notes.")
                st.rerun()

    notes = (_get("/habits/coach/notes", user_id=user_id) or {}).get("notes", [])
    if not notes:
        st.info("No coaching notes yet. Generate some — the rule-based coach works without an LLM.")
    for n in notes:
        st.markdown(
            f"<div class='hl-card'><b>{n['title']}</b>"
            f" <span class='hl-pill'>{n['note_type']}</span>"
            + (f" <span class='hl-pill'>confidence {n.get('confidence', 0):.1f}</span>" if n.get('confidence') else "")
            + f"<p>{n['body']}</p></div>",
            unsafe_allow_html=True,
        )
        ncols = st.columns([1, 1, 6])
        with ncols[0]:
            if st.button("Dismiss", key=f"dismiss-{n['id']}"):
                _post(f"/habits/coach/notes/{n['id']}/dismiss?user_id={user_id}", body={})
                st.rerun()
        with ncols[1]:
            if st.button("Delete", key=f"cdel-{n['id']}"):
                _delete(f"/habits/coach/notes/{n['id']}", user_id=user_id)
                st.rerun()
