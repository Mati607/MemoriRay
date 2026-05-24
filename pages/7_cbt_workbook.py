"""
Streamlit page: CBT Workbook & Cognitive Restructuring.

Tabs:
  - Thought Records (the 7-column record + auto-detected distortions + reframer)
  - Worry Tree
  - Behavioral Experiments
  - Activity Scheduling (Behavioral Activation)
  - Core Beliefs (with strength-over-time chart)
  - Analytics (engagement, leaderboard, reframe success, etc.)
"""

import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

API_BASE = "http://localhost:8000"


def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()


check_authentication()

st.set_page_config(page_title="CBT Workbook", page_icon="🧠", layout="wide")

st.markdown(
    """
    <style>
        :root {
            --cw-bg: #FFFBEB;
            --cw-card: #FFF7D6;
            --cw-ink: #3F3D2E;
            --cw-accent: #F4D06F;
            --cw-accent-2: #9ED2C6;
            --cw-accent-3: #C7E9B0;
            --cw-warn: #F8A8A8;
            --cw-muted: #918C76;
        }
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: var(--cw-bg) !important;
            color: var(--cw-ink) !important;
        }
        .cw-card { background: var(--cw-card); border-radius: 14px; padding: 18px 20px; margin-bottom: 14px; border: 1px solid rgba(63,61,46,0.08); }
        .cw-pill { display: inline-block; background: var(--cw-accent-3); border-radius: 999px; padding: 2px 10px; margin-right: 6px; font-size: 0.78rem; }
        .cw-pill.warn { background: var(--cw-warn); }
        .cw-pill.mood { background: var(--cw-accent); }
        .cw-stat { font-size: 1.8rem; font-weight: 700; }
        .cw-quote { font-style: italic; color: var(--cw-muted); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧠 CBT Workbook")
st.markdown("Catch the thought, examine the evidence, design a better next step.")

user_id = st.session_state.user_id


def _get(path, **params):
    try:
        params = {k: v for k, v in params.items() if v is not None}
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}")
    except Exception as exc:
        st.error(f"GET {path} failed: {exc}")
    return None


def _post(path, body=None):
    try:
        resp = requests.post(f"{API_BASE}{path}", json=body or {}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} -> {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        st.error(f"POST {path} failed: {exc}")
    return None


def _patch(path, body=None):
    try:
        resp = requests.patch(f"{API_BASE}{path}", json=body or {}, timeout=20)
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
    "📝 Thought Records",
    "🌳 Worry Tree",
    "🧪 Experiments",
    "🎯 Activity Schedule",
    "🧱 Core Beliefs",
    "📊 Analytics",
])


# ---------------------------------------------------------------------------
# Tab 1: Thought Records
# ---------------------------------------------------------------------------
with tabs[0]:
    st.subheader("New thought record")

    with st.form("new_tr"):
        situation = st.text_area("Situation (what happened?)", height=80, key="tr_situation")
        thought = st.text_area("Automatic thought (what crossed your mind?)", height=100, key="tr_thought")
        c1, c2, c3 = st.columns(3)
        with c1:
            emotion = st.selectbox(
                "Primary emotion",
                ["", "anxious", "sad", "angry", "ashamed", "guilty", "lonely",
                 "hopeless", "frustrated", "afraid", "hurt", "disappointed",
                 "embarrassed", "overwhelmed", "numb", "envious", "worried"],
            )
        with c2:
            intensity = st.slider("Emotion intensity (0-100)", 0, 100, 60, key="tr_int")
        with c3:
            belief = st.slider("How much you believe the thought (0-100)", 0, 100, 70, key="tr_bel")

        submitted = st.form_submit_button("Save & detect distortions", type="primary")
        if submitted:
            if not situation.strip() or not thought.strip():
                st.warning("Situation and automatic thought are required.")
            else:
                payload = {
                    "user_id": user_id,
                    "situation": situation,
                    "automatic_thought": thought,
                    "primary_emotion": emotion or None,
                    "emotion_intensity": intensity,
                    "belief_in_original_thought": belief,
                    "auto_detect_distortions": True,
                }
                res = _post("/cbt/thought-records", payload)
                if res:
                    st.session_state["last_record_id"] = res["record"]["id"]
                    st.success("Saved. Distortions auto-detected below.")
                    st.rerun()

    last_id = st.session_state.get("last_record_id")
    if last_id:
        rec = (_get(f"/cbt/thought-records/{last_id}", user_id=user_id) or {}).get("record")
        if rec:
            st.markdown(f"<div class='cw-card'><b>Current record</b><br>"
                        f"<i>{rec['situation']}</i><br>"
                        f"<b>Thought:</b> {rec['automatic_thought']}<br>"
                        + "".join(f"<span class='cw-pill'>{d['name']} ({int((d.get('confidence') or 0)*100)}%)</span>" for d in rec.get("distortions") or [])
                        + "</div>", unsafe_allow_html=True)

            st.subheader("Ask the reframer")
            use_llm = st.toggle("Use AI (Gemini)", value=True, key="reframe_llm")
            if st.button("✨ Suggest reframes"):
                res = _post(
                    "/cbt/reframer",
                    {
                        "automatic_thought": rec["automatic_thought"],
                        "situation": rec.get("situation"),
                        "primary_emotion": rec.get("primary_emotion"),
                        "emotion_intensity": rec.get("emotion_intensity"),
                        "use_llm": use_llm,
                    },
                )
                st.session_state["last_reframes"] = (res or {}).get("suggestions", [])
            for r in st.session_state.get("last_reframes", []):
                st.markdown(
                    f"<div class='cw-card'><b>{r['balanced_thought']}</b>"
                    f"<br><i>{r['rationale']}</i>"
                    + ("<br><b>Questions:</b><ul>" + "".join(f"<li>{q}</li>" for q in r.get('questions') or []) + "</ul>")
                    + "</div>",
                    unsafe_allow_html=True,
                )

            st.subheader("Complete the record")
            with st.form("complete_tr"):
                ev_for = st.text_area("Evidence FOR the thought", height=80)
                ev_against = st.text_area("Evidence AGAINST the thought", height=80)
                balanced = st.text_area("Balanced thought", height=100)
                new_intensity = st.slider("New emotion intensity", 0, 100, max(0, int(rec.get("emotion_intensity") or 50) - 10))
                new_belief = st.slider("Belief in the balanced thought", 0, 100, 60)
                if st.form_submit_button("Save reframe", type="primary"):
                    res = _post(
                        f"/cbt/thought-records/{last_id}/complete",
                        {
                            "user_id": user_id,
                            "evidence_for": ev_for,
                            "evidence_against": ev_against,
                            "balanced_thought": balanced,
                            "new_emotion_intensity": new_intensity,
                            "belief_in_balanced_thought": new_belief,
                        },
                    )
                    if res:
                        st.success("Reframe saved.")
                        st.rerun()

    st.subheader("Recent records")
    recs = (_get("/cbt/thought-records", user_id=user_id, limit=10) or {}).get("records", [])
    for r in recs:
        st.markdown(
            f"<div class='cw-card'><b>{r.get('situation') or 'Untitled'}</b>"
            + f"<span class='cw-pill mood'>{r.get('primary_emotion') or '—'}</span>"
            + f"<span class='cw-pill'>before {r.get('emotion_intensity') or '—'}</span>"
            + f"<span class='cw-pill'>after {r.get('new_emotion_intensity') or '—'}</span>"
            + (" <span class='cw-pill'>complete</span>" if r.get('is_complete') else " <span class='cw-pill warn'>draft</span>")
            + f"<br>{r.get('automatic_thought','')[:180]}"
            + "</div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("Open", key=f"open-{r['id']}"):
                st.session_state["last_record_id"] = r["id"]
                st.rerun()


# ---------------------------------------------------------------------------
# Tab 2: Worry Tree
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("New worry")
    with st.form("new_worry"):
        worry_text = st.text_area("What's the worry?", height=80)
        intensity_before = st.slider("Intensity (0-100)", 0, 100, 60)
        if st.form_submit_button("Start worry tree", type="primary"):
            if worry_text.strip():
                res = _post(
                    "/cbt/worries",
                    {"user_id": user_id, "worry": worry_text, "worry_intensity_before": intensity_before},
                )
                if res:
                    st.session_state["current_worry"] = res["worry"]["id"]
                    st.rerun()

    current = st.session_state.get("current_worry")
    if current:
        w = (_get(f"/cbt/worries/{current}", user_id=user_id) or {}).get("worry")
        if w:
            st.markdown(f"<div class='cw-card'><b>{w['worry']}</b><br>"
                        + (f"<span class='cw-pill'>solvable</span>" if w.get("is_solvable") is True else "")
                        + (f"<span class='cw-pill warn'>unsolvable</span>" if w.get("is_solvable") is False else "")
                        + (f"<span class='cw-pill'>before {w.get('worry_intensity_before')}</span>" if w.get('worry_intensity_before') is not None else "")
                        + (f"<span class='cw-pill'>after {w.get('worry_intensity_after')}</span>" if w.get('worry_intensity_after') is not None else "")
                        + "</div>", unsafe_allow_html=True)

            if w.get("is_solvable") is None:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Can I act on it?  →  Solvable", use_container_width=True):
                        _post(f"/cbt/worries/{current}/classify", {"user_id": user_id, "is_solvable": True})
                        st.rerun()
                with col2:
                    if st.button("Out of my control →  Unsolvable", use_container_width=True):
                        _post(f"/cbt/worries/{current}/classify", {"user_id": user_id, "is_solvable": False})
                        st.rerun()

            if w.get("is_solvable") is True:
                with st.form("plan_solvable"):
                    action = st.text_input("One concrete action", value=w.get("action_step") or "")
                    when = st.text_input("When", value=w.get("when_to_act") or "")
                    obstacle = st.text_area("Likely obstacle and plan", value=w.get("obstacle_plan") or "", height=80)
                    if st.form_submit_button("Save plan"):
                        _post(
                            f"/cbt/worries/{current}/plan",
                            {"user_id": user_id, "action_step": action, "when_to_act": when, "obstacle_plan": obstacle},
                        )
                        st.rerun()

            if w.get("is_solvable") is False:
                with st.form("plan_unsolvable"):
                    strategy = st.selectbox(
                        "Let-go strategy",
                        ["postpone_worry", "self_soothe", "defuse", "accept", "distract", "ground"],
                    )
                    accept_text = st.text_area("Acceptance reframe", value=w.get("accept_reframe") or "", height=80)
                    soothing = st.text_area("Self-soothing plan", value=w.get("self_soothing_plan") or "", height=80)
                    if st.form_submit_button("Save plan"):
                        _post(
                            f"/cbt/worries/{current}/plan",
                            {"user_id": user_id, "let_go_strategy": strategy, "accept_reframe": accept_text, "self_soothing_plan": soothing},
                        )
                        st.rerun()

            if not w.get("is_complete"):
                intensity_after = st.slider("Re-rate intensity", 0, 100, int(w.get("worry_intensity_before") or 50) - 10)
                if st.button("Finish worry"):
                    _post(f"/cbt/worries/{current}/finish", {"user_id": user_id, "worry_intensity_after": intensity_after})
                    st.session_state.pop("current_worry", None)
                    st.rerun()

    st.subheader("Recent worries")
    worries = (_get("/cbt/worries", user_id=user_id, limit=10) or {}).get("worries", [])
    for w in worries:
        st.markdown(
            f"<div class='cw-card'>{w['worry']}<br>"
            + (f"<span class='cw-pill'>solvable</span>" if w.get('is_solvable') is True else (f"<span class='cw-pill warn'>unsolvable</span>" if w.get('is_solvable') is False else "<span class='cw-pill'>unclassified</span>"))
            + (" <span class='cw-pill'>complete</span>" if w.get('is_complete') else " <span class='cw-pill warn'>open</span>")
            + "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Tab 3: Behavioral Experiments
# ---------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Design an experiment")
    with st.form("new_exp"):
        target = st.text_area("Belief you want to test")
        strength_before = st.slider("How strongly you believe it (0-100)", 0, 100, 70)
        prediction = st.text_area("Prediction (what do you think will happen?)")
        confidence = st.slider("Confidence in the prediction (0-100)", 0, 100, 60)
        design = st.text_area("How you'll test it (small, concrete experiment)")
        safety = st.text_area("Safety behaviors to drop (optional)")
        coping = st.text_area("Coping plan if it's distressing")
        if st.form_submit_button("Plan it", type="primary"):
            if target.strip() and prediction.strip() and design.strip():
                _post(
                    "/cbt/experiments",
                    {
                        "user_id": user_id,
                        "target_belief": target,
                        "prediction": prediction,
                        "experiment_design": design,
                        "belief_strength_before": strength_before,
                        "prediction_confidence": confidence,
                        "safety_behaviors_to_drop": safety or None,
                        "coping_plan_if_distressing": coping or None,
                    },
                )
                st.rerun()
            else:
                st.warning("Belief, prediction, and design are required.")

    st.subheader("Active experiments")
    exps = (_get("/cbt/experiments", user_id=user_id) or {}).get("experiments", [])
    for e in exps:
        st.markdown(
            f"<div class='cw-card'><b>{e['target_belief']}</b>"
            + f"<span class='cw-pill'>{e['status']}</span>"
            + (f"<span class='cw-pill'>belief before {e.get('belief_strength_before')}</span>" if e.get('belief_strength_before') is not None else "")
            + (f"<span class='cw-pill mood'>belief after {e.get('belief_strength_after')}</span>" if e.get('belief_strength_after') is not None else "")
            + f"<br><b>Prediction:</b> {e['prediction']}"
            + f"<br><b>Design:</b> {e['experiment_design']}"
            + (f"<br><b>Outcome:</b> {e['actual_outcome']}" if e.get('actual_outcome') else "")
            + (f"<br><b>Learning:</b> {e['learning_summary']}" if e.get('learning_summary') else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        if e["status"] in ("planned",):
            with st.expander("Record outcome"):
                with st.form(f"outcome-{e['id']}"):
                    outcome = st.text_area("What actually happened?")
                    surprise = st.slider("Surprise factor (0-10)", 0.0, 10.0, 5.0)
                    new_strength = st.slider("Belief now (0-100)", 0, 100, int(e.get("belief_strength_before") or 50))
                    learning = st.text_area("One sentence of learning")
                    if st.form_submit_button("Save outcome"):
                        _post(
                            f"/cbt/experiments/{e['id']}/outcome",
                            {
                                "user_id": user_id,
                                "actual_outcome": outcome,
                                "surprise_factor": surprise,
                                "belief_strength_after": new_strength,
                                "learning_summary": learning,
                            },
                        )
                        st.rerun()


# ---------------------------------------------------------------------------
# Tab 4: Activity Scheduling
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Schedule an activity")
    with st.form("new_activity"):
        title = st.text_input("Title")
        category = st.selectbox(
            "Category",
            ["movement", "social", "creative", "rest", "nature",
             "learning", "self_care", "play", "achievement", "general"],
        )
        scheduled_date = st.date_input("Date", value=datetime.now().date())
        scheduled_time = st.time_input("Time", value=datetime.now().time())
        duration = st.number_input("Duration (minutes)", min_value=0, value=20)
        c1, c2 = st.columns(2)
        with c1:
            pleasure = st.toggle("Pleasure activity", value=True)
        with c2:
            mastery = st.toggle("Mastery activity", value=False)
        if st.form_submit_button("Schedule", type="primary"):
            if title.strip():
                dt = datetime.combine(scheduled_date, scheduled_time).replace(tzinfo=timezone.utc)
                _post(
                    "/cbt/activities",
                    {
                        "user_id": user_id,
                        "title": title,
                        "category": category,
                        "scheduled_for": dt.isoformat(),
                        "duration_minutes": duration or None,
                        "is_pleasure_activity": pleasure,
                        "is_mastery_activity": mastery,
                    },
                )
                st.rerun()

    st.subheader("Upcoming / past activities")
    activities = (_get("/cbt/activities", user_id=user_id, limit=30) or {}).get("activities", [])
    for a in activities:
        st.markdown(
            f"<div class='cw-card'><b>{a['title']}</b>"
            + f"<span class='cw-pill'>{a['category']}</span>"
            + (" <span class='cw-pill'>pleasure</span>" if a.get("is_pleasure_activity") else "")
            + (" <span class='cw-pill'>mastery</span>" if a.get("is_mastery_activity") else "")
            + (" <span class='cw-pill mood'>completed</span>" if a.get("is_completed") else " <span class='cw-pill'>scheduled</span>")
            + (f"<br>Pleasure {a.get('pleasure_rating')}/10 — Mastery {a.get('mastery_rating')}/10 — Energy {a.get('energy_after')}/10" if a.get('is_completed') else "")
            + f"<br><span class='cw-quote'>{a['scheduled_for'][:16].replace('T',' ')}</span>"
            + "</div>",
            unsafe_allow_html=True,
        )
        if not a.get("is_completed"):
            with st.expander(f"Complete: {a['title']}"):
                with st.form(f"comp-{a['id']}"):
                    pr = st.slider("Pleasure", 0.0, 10.0, 5.0, key=f"pr-{a['id']}")
                    mr = st.slider("Mastery", 0.0, 10.0, 5.0, key=f"mr-{a['id']}")
                    en = st.slider("Energy after", 0.0, 10.0, 5.0, key=f"en-{a['id']}")
                    nt = st.text_input("Notes", key=f"nt-{a['id']}")
                    if st.form_submit_button("Mark complete"):
                        _post(
                            f"/cbt/activities/{a['id']}/complete",
                            {
                                "user_id": user_id,
                                "pleasure_rating": pr,
                                "mastery_rating": mr,
                                "energy_after": en,
                                "notes": nt or None,
                            },
                        )
                        st.rerun()

    st.subheader("Suggestions (from your own history)")
    sug = (_get("/cbt/activities/suggest/from-history", user_id=user_id, limit=5) or {}).get("suggestions", [])
    for s in sug:
        st.write(f"• **{s.get('title','?')}** ({s.get('category','?')})")


# ---------------------------------------------------------------------------
# Tab 5: Core Beliefs
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Track a core belief over time")
    with st.form("new_belief"):
        statement = st.text_input("Belief statement", "")
        category = st.selectbox("Category", ["self", "others", "world", "future"])
        alternative = st.text_input("Alternative belief (optional)")
        if st.form_submit_button("Add belief", type="primary"):
            if statement.strip():
                _post(
                    "/cbt/core-beliefs",
                    {
                        "user_id": user_id,
                        "statement": statement,
                        "category": category,
                        "alternative_belief": alternative or None,
                    },
                )
                st.rerun()

    beliefs = (_get("/cbt/core-beliefs", user_id=user_id) or {}).get("beliefs", [])
    for b in beliefs:
        st.markdown(
            f"<div class='cw-card'><b>{b['statement']}</b>"
            + f"<span class='cw-pill'>{b.get('category') or '—'}</span>"
            + (f"<br><i>Alternative: {b['alternative_belief']}</i>" if b.get('alternative_belief') else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"Rate / history — {b['statement'][:60]}"):
            history = (_get(f"/cbt/core-beliefs/{b['id']}/history", user_id=user_id) or {}).get("ratings", [])
            if history:
                strengths = {r["rated_at"][:10]: r["strength"] for r in history}
                alts = {r["rated_at"][:10]: r.get("alternative_strength") for r in history if r.get("alternative_strength") is not None}
                if strengths:
                    st.line_chart({"core": strengths, "alternative": alts} if alts else {"core": strengths})
            with st.form(f"rate-{b['id']}"):
                sc1, sc2 = st.columns(2)
                with sc1:
                    strength = st.slider("Believe core (0-100)", 0, 100, 60, key=f"core-{b['id']}")
                with sc2:
                    alt_strength = st.slider("Believe alternative (0-100)", 0, 100, 40, key=f"alt-{b['id']}")
                note = st.text_input("Note (optional)", key=f"note-{b['id']}")
                if st.form_submit_button("Record rating"):
                    _post(
                        f"/cbt/core-beliefs/{b['id']}/rate",
                        {
                            "user_id": user_id,
                            "strength": strength,
                            "alternative_strength": alt_strength,
                            "note": note or None,
                        },
                    )
                    st.rerun()


# ---------------------------------------------------------------------------
# Tab 6: Analytics
# ---------------------------------------------------------------------------
with tabs[5]:
    eng = _get("/cbt/analytics/engagement", user_id=user_id, days=30)
    if eng:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(
                f"<div class='cw-card'><div class='cw-stat'>{eng['score']}</div>"
                f"CBT engagement — <i>{eng['label']}</i></div>",
                unsafe_allow_html=True,
            )
        with col_b:
            st.bar_chart(eng["components"])

    st.subheader("Reframe success")
    reframe = _get("/cbt/analytics/reframe-success", user_id=user_id, days=60) or {}
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Records", reframe.get("total_records", 0))
    rc2.metric("Completed", reframe.get("completed_records", 0))
    rc3.metric("Avg Δ intensity", reframe.get("avg_intensity_delta") or "—")
    rc4.metric("Shift success", f"{int((reframe.get('shift_success_rate') or 0)*100)}%")

    st.subheader("Distortion leaderboard")
    leader = (_get("/cbt/analytics/distortions", user_id=user_id, days=60) or {}).get("leaderboard", [])
    if leader:
        st.bar_chart({d["name"]: d["count"] for d in leader})

    st.subheader("Worry split")
    worry = _get("/cbt/analytics/worry", user_id=user_id, days=60) or {}
    if worry.get("total"):
        st.bar_chart({"solvable": worry.get("solvable", 0), "unsolvable": worry.get("unsolvable", 0), "unclassified": worry.get("unclassified", 0)})

    st.subheader("Activity balance")
    act = _get("/cbt/analytics/activity", user_id=user_id, days=30) or {}
    a1, a2, a3 = st.columns(3)
    a1.metric("Scheduled", act.get("scheduled", 0))
    a2.metric("Completed", act.get("completed", 0))
    a3.metric("Completion %", f"{int((act.get('completion_rate') or 0)*100)}%")
    if act.get("avg_pleasure") is not None or act.get("avg_mastery") is not None:
        st.bar_chart({"pleasure": act.get("avg_pleasure") or 0, "mastery": act.get("avg_mastery") or 0})

    st.subheader("Belief drift")
    drift = (_get("/cbt/analytics/belief-drift", user_id=user_id, days=180) or {}).get("beliefs", [])
    for b in drift[:5]:
        st.write(
            f"• **{b['statement']}** — first {b['first']:.0f}, last {b['last']:.0f} "
            f"(Δ {b['delta']:+.1f})"
        )
