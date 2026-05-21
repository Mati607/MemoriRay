"""
Streamlit page: Mindful Journal & Reflection System.

Tabs:
  - New Entry (prompts + free-form writing)
  - Library (search/filter past entries)
  - Gratitude
  - Mindfulness (technique library + session recorder)
  - Reflections (AI/rule-based weekly summaries)
  - Insights (wellbeing score, heatmap, correlations)
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


st.set_page_config(page_title="Mindful Journal", page_icon="📓", layout="wide")

st.markdown(
    """
    <style>
        :root {
            --mh-bg: #FFFBEB;
            --mh-card: #FFF7D6;
            --mh-ink: #3F3D2E;
            --mh-accent: #F4D06F;
            --mh-accent-2: #9ED2C6;
            --mh-accent-3: #C7E9B0;
            --mh-muted: #918C76;
        }
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: var(--mh-bg) !important;
            color: var(--mh-ink) !important;
        }
        .mj-card {
            background: var(--mh-card);
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 14px;
            border: 1px solid rgba(63,61,46,0.08);
        }
        .mj-pill {
            display: inline-block;
            background: var(--mh-accent-3);
            border-radius: 999px;
            padding: 2px 10px;
            margin-right: 6px;
            font-size: 0.78rem;
            color: var(--mh-ink);
        }
        .mj-pill.mood {
            background: var(--mh-accent);
        }
        .mj-quote {
            font-style: italic;
            color: var(--mh-muted);
        }
        .mj-stat {
            font-size: 2rem;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📓 Mindful Journal")
st.markdown("Write, reflect, and notice patterns over time.")

user_id = st.session_state.user_id


def _api_get(path: str, **params):
    try:
        params = {k: v for k, v in params.items() if v is not None}
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} returned {resp.status_code}")
    except Exception as exc:
        st.error(f"Request to {path} failed: {exc}")
    return None


def _api_post(path: str, body: dict):
    try:
        resp = requests.post(f"{API_BASE}{path}", json=body, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        st.error(f"Request to {path} failed: {exc}")
    return None


def _api_delete(path: str, **params):
    try:
        params = {k: v for k, v in params.items() if v is not None}
        resp = requests.delete(f"{API_BASE}{path}", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"{path} returned {resp.status_code}")
    except Exception as exc:
        st.error(f"Request to {path} failed: {exc}")
    return None


tabs = st.tabs([
    "✍️ New Entry",
    "📚 Library",
    "🙏 Gratitude",
    "🧘 Mindfulness",
    "🪞 Reflections",
    "📈 Insights",
])


# ---------------------------------------------------------------------------
# Tab 1: New Entry
# ---------------------------------------------------------------------------
with tabs[0]:
    col_left, col_right = st.columns([2, 1])

    with col_right:
        st.subheader("Need a starting point?")
        mood_for_prompt = st.slider(
            "How are you feeling right now?",
            min_value=0.0,
            max_value=10.0,
            value=5.0,
            step=0.5,
            key="prompt_mood",
        )
        if st.button("🎲 Get a prompt", use_container_width=True):
            prompt_data = _api_get("/journal/prompts/random", mood_score=mood_for_prompt)
            if prompt_data and prompt_data.get("prompt"):
                st.session_state["chosen_prompt"] = prompt_data["prompt"]

        chosen = st.session_state.get("chosen_prompt")
        if chosen:
            st.markdown(
                f"<div class='mj-card mj-quote'>“{chosen['text']}”<br>"
                f"<span class='mj-pill'>{chosen['category']}</span>"
                f"<span class='mj-pill'>{chosen['difficulty']}</span>"
                f"<span class='mj-pill'>~{chosen['estimated_minutes']} min</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.caption("Or browse all prompts")
        all_prompts = _api_get("/journal/prompts")
        if all_prompts:
            categories = sorted({p["category"] for p in all_prompts["prompts"]})
            chosen_cat = st.selectbox("Category", ["all"] + categories)
            filtered = (
                all_prompts["prompts"]
                if chosen_cat == "all"
                else [p for p in all_prompts["prompts"] if p["category"] == chosen_cat]
            )
            for p in filtered[:8]:
                if st.button(p["text"], key=f"pick-{p['id']}", use_container_width=True):
                    st.session_state["chosen_prompt"] = p
                    st.rerun()

    with col_left:
        st.subheader("Write")
        title = st.text_input("Title (optional)", key="entry_title")
        body = st.text_area(
            "What's on your mind?",
            height=320,
            key="entry_body",
            placeholder="Try writing without editing for a few minutes...",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            mood = st.slider("Mood", 0.0, 10.0, 5.0, 0.5, key="entry_mood")
        with c2:
            energy = st.slider("Energy", 0.0, 10.0, 5.0, 0.5, key="entry_energy")
        with c3:
            stress = st.slider("Stress", 0.0, 10.0, 5.0, 0.5, key="entry_stress")

        tags_str = st.text_input("Tags (comma separated)", key="entry_tags")
        save_draft = st.toggle("Save as draft", value=False, key="entry_draft")

        if st.button("💾 Save entry", type="primary", use_container_width=True):
            if not body.strip():
                st.warning("Add some text before saving.")
            else:
                payload = {
                    "user_id": user_id,
                    "title": title or None,
                    "body": body,
                    "mood_score": mood,
                    "energy_level": energy,
                    "stress_level": stress,
                    "tags": [t.strip() for t in tags_str.split(",") if t.strip()],
                    "is_draft": save_draft,
                    "prompt_id": (st.session_state.get("chosen_prompt") or {}).get("id"),
                }
                created = _api_post("/journal/entries", payload)
                if created:
                    st.success("Saved.")
                    st.session_state["entry_title"] = ""
                    st.session_state["entry_body"] = ""
                    st.session_state.pop("chosen_prompt", None)
                    st.rerun()


# ---------------------------------------------------------------------------
# Tab 2: Library
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Your journal")
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    with f1:
        search_q = st.text_input("Search", key="search_q")
    with f2:
        favorites_only = st.toggle("Favorites only", key="fav_only")
    with f3:
        include_archived = st.toggle("Include archived", key="incl_arch")
    with f4:
        limit = st.number_input("Limit", min_value=5, max_value=100, value=20)

    if search_q.strip():
        result = _api_get("/journal/entries/search/q", user_id=user_id, q=search_q.strip())
    else:
        result = _api_get(
            "/journal/entries",
            user_id=user_id,
            limit=int(limit),
            favorites_only=favorites_only,
            include_archived=include_archived,
        )

    entries = (result or {}).get("entries", [])
    if not entries:
        st.info("Nothing matches yet. Try clearing filters or writing your first entry.")
    else:
        st.caption(f"Showing {len(entries)} entries")
        for entry in entries:
            star = "⭐" if entry.get("is_favorite") else ""
            archived = "📦" if entry.get("is_archived") else ""
            tags_html = "".join(
                f"<span class='mj-pill'>{t}</span>" for t in entry.get("tags") or []
            )
            mood_html = (
                f"<span class='mj-pill mood'>mood {entry['mood_score']}</span>"
                if entry.get("mood_score") is not None
                else ""
            )
            st.markdown(
                f"<div class='mj-card'><b>{star} {entry.get('title') or 'Untitled'} {archived}</b>"
                f" <span class='mj-quote'>{entry['created_at'][:16].replace('T',' ')}</span>"
                f"<br>{mood_html} {tags_html}"
                f"<p>{entry.get('excerpt') or ''}</p></div>",
                unsafe_allow_html=True,
            )

            cols = st.columns([1, 1, 1, 4])
            with cols[0]:
                if st.button("Toggle ⭐", key=f"fav-{entry['id']}"):
                    _api_post(
                        f"/journal/entries/{entry['id']}",
                        body={"user_id": user_id, "is_favorite": not entry.get("is_favorite")},
                    )
                    st.rerun()
            with cols[1]:
                if st.button("Archive", key=f"arch-{entry['id']}"):
                    _api_post(
                        f"/journal/entries/{entry['id']}",
                        body={"user_id": user_id, "is_archived": not entry.get("is_archived")},
                    )
                    st.rerun()
            with cols[2]:
                if st.button("Delete", key=f"del-{entry['id']}"):
                    _api_delete(f"/journal/entries/{entry['id']}", user_id=user_id)
                    st.rerun()


# ---------------------------------------------------------------------------
# Tab 3: Gratitude
# ---------------------------------------------------------------------------
with tabs[2]:
    streak = _api_get("/journal/gratitude/streak", user_id=user_id) or {}
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"<div class='mj-card'><div class='mj-stat'>{streak.get('current_streak', 0)}🔥</div>current streak</div>", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"<div class='mj-card'><div class='mj-stat'>{streak.get('longest_streak', 0)}</div>longest streak</div>", unsafe_allow_html=True)
    with sc3:
        st.markdown(f"<div class='mj-card'><div class='mj-stat'>{streak.get('total_entries', 0)}</div>total entries</div>", unsafe_allow_html=True)

    st.subheader("Add gratitude")
    g_content = st.text_area("I'm grateful for...", height=80, key="grat_content")
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        g_category = st.selectbox(
            "Category",
            ["people", "experiences", "self", "body", "work", "nature", "creativity", "small_joys", "growth", "comfort", "other"],
        )
    with gc2:
        g_intensity = st.slider("Intensity", 1.0, 5.0, 3.0, 0.5)
    with gc3:
        g_person = st.text_input("Related person (optional)")

    if st.button("Add gratitude", type="primary"):
        if g_content.strip():
            res = _api_post(
                "/journal/gratitude",
                {
                    "user_id": user_id,
                    "content": g_content,
                    "category": g_category,
                    "intensity": g_intensity,
                    "related_person": g_person or None,
                },
            )
            if res:
                st.success("Saved.")
                st.rerun()
        else:
            st.warning("Add some text first.")

    st.subheader("Recent gratitudes")
    recent = _api_get("/journal/gratitude", user_id=user_id, limit=30) or {}
    for g in recent.get("entries", []):
        st.markdown(
            f"<div class='mj-card'>{g['content']}<br>"
            f"<span class='mj-pill'>{g.get('category') or 'other'}</span>"
            f"<span class='mj-pill mood'>intensity {g.get('intensity', 3)}</span>"
            f" <span class='mj-quote'>{g['created_at'][:10]}</span></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Distribution")
    breakdown = _api_get("/journal/gratitude/breakdown", user_id=user_id, days=30)
    if breakdown and breakdown.get("total"):
        st.bar_chart(breakdown["categories"])
    else:
        st.caption("Log a few more gratitudes to see your distribution.")


# ---------------------------------------------------------------------------
# Tab 4: Mindfulness
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Find a technique")
    rc1, rc2 = st.columns(2)
    with rc1:
        rec_mood = st.slider("Current mood", 0.0, 10.0, 5.0, 0.5, key="rec_mood")
    with rc2:
        rec_minutes = st.slider("Minutes available", 1, 30, 5, key="rec_minutes")

    recommended = _api_get(
        "/journal/mindfulness/recommend",
        user_id=user_id,
        mood_score=rec_mood,
        available_minutes=rec_minutes,
    )
    if recommended and recommended.get("technique"):
        t = recommended["technique"]
        st.markdown(
            f"<div class='mj-card'><b>Recommended: {t['name']}</b><br>"
            f"<span class='mj-pill'>{t['category']}</span>"
            f"<span class='mj-pill'>{t['difficulty']}</span>"
            f"<span class='mj-pill mood'>{t['typical_duration']} min</span>"
            f"<p>{t['description']}</p>"
            f"<details><summary>Guided script</summary><pre>{t.get('guided_script') or ''}</pre></details></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Log a session")
    techniques_res = _api_get("/journal/mindfulness/techniques") or {}
    techniques = techniques_res.get("techniques", [])
    technique_map = {t["name"]: t["key"] for t in techniques}
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        tech_name = st.selectbox("Technique", list(technique_map.keys()) if technique_map else ["box_breathing_4_4_4_4"])
    with tcol2:
        duration_min = st.number_input("Duration (minutes)", min_value=1, max_value=120, value=5)
    with tcol3:
        bg_sound = st.selectbox("Background sound", ["none", "rain", "ocean", "white_noise", "silence"])

    pre, post, calm = st.columns(3)
    with pre:
        pre_mood = st.slider("Pre-session mood", 0.0, 10.0, 5.0, 0.5, key="pre_mood_inp")
    with post:
        post_mood = st.slider("Post-session mood", 0.0, 10.0, 5.0, 0.5, key="post_mood_inp")
    with calm:
        perceived = st.slider("Perceived calm", 0.0, 5.0, 3.0, 0.5, key="calm_inp")

    notes = st.text_area("Notes (optional)", height=80)

    if st.button("Log session", type="primary"):
        chosen_key = technique_map.get(tech_name, tech_name)
        res = _api_post(
            "/journal/mindfulness/sessions",
            {
                "user_id": user_id,
                "technique": chosen_key,
                "duration_seconds": int(duration_min) * 60,
                "pre_mood": pre_mood,
                "post_mood": post_mood,
                "perceived_calm": perceived,
                "notes": notes or None,
                "background_sound": None if bg_sound == "none" else bg_sound,
            },
        )
        if res:
            st.success("Session logged.")
            st.rerun()

    st.subheader("Practice summary (last 30 days)")
    summary = _api_get("/journal/mindfulness/summary", user_id=user_id, days=30) or {}
    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("Sessions", summary.get("total_sessions", 0))
    sm2.metric("Minutes", summary.get("total_minutes", 0))
    sm3.metric("Avg calm", summary.get("average_calm") or "—")
    sm4.metric("Avg Δ mood", summary.get("average_mood_delta") or "—")

    st.subheader("Technique effectiveness")
    eff = _api_get("/journal/mindfulness/effectiveness", user_id=user_id)
    if eff and eff.get("techniques"):
        for row in eff["techniques"]:
            st.write(
                f"• **{row['technique']}** — avg mood delta {row['avg_mood_delta']} (n={row['samples']})"
            )
    else:
        st.caption("Log a few sessions with pre/post mood ratings to see what's working for you.")


# ---------------------------------------------------------------------------
# Tab 5: Reflections
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Reflections")
    rc1, rc2, rc3 = st.columns([1, 1, 2])
    with rc1:
        window_kind = st.selectbox("Window", ["daily", "weekly", "monthly"], index=1)
    with rc2:
        use_llm = st.toggle("Use AI (Gemini)", value=True)
    with rc3:
        if st.button("Generate new reflection", type="primary", use_container_width=True):
            res = _api_post(
                "/journal/reflections/generate",
                {"user_id": user_id, "window_kind": window_kind, "use_llm": use_llm},
            )
            if res and res.get("reflection"):
                st.success("Generated.")
                st.rerun()

    history = _api_get("/journal/reflections", user_id=user_id, limit=10) or {}
    for ref in history.get("reflections", []):
        st.markdown(
            f"<div class='mj-card'><b>{ref['window_kind'].title()} — {ref['generated_at'][:10]}</b>"
            f" <span class='mj-pill'>{ref.get('mood_trend','unknown')}</span>"
            f"<p>{ref['summary']}</p>"
            + (
                f"<p><b>Themes:</b> {', '.join(ref.get('dominant_themes') or []) or '—'}</p>"
            )
            + (
                "<p><b>Growth signals:</b></p><ul>"
                + "".join(f"<li>{g}</li>" for g in ref.get("growth_signals") or [])
                + "</ul>"
            )
            + (
                "<p><b>Suggested focus:</b></p><ul>"
                + "".join(f"<li>{g}</li>" for g in ref.get("suggested_focus") or [])
                + "</ul>"
            )
            + "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Tab 6: Insights
# ---------------------------------------------------------------------------
with tabs[5]:
    wb = _api_get("/journal/analytics/wellbeing", user_id=user_id, days=14)
    if wb:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(
                f"<div class='mj-card'><div class='mj-stat'>{wb['score']}</div>"
                f"wellbeing — <i>{wb['label']}</i></div>",
                unsafe_allow_html=True,
            )
        with col_b:
            st.bar_chart(wb["components"])

    st.subheader("Writing consistency")
    cons = _api_get("/journal/analytics/consistency", user_id=user_id, days=30)
    if cons:
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Active days", cons["active_days"])
        cc2.metric("Consistency", f"{cons['consistency_ratio']*100:.0f}%")
        cc3.metric("Avg gap (days)", cons["average_gap_days"] or "—")

    st.subheader("Mood ↔ practice correlation")
    corr = _api_get("/journal/analytics/correlation", user_id=user_id, days=60)
    if corr:
        st.caption(corr.get("interpretation", ""))
        if corr.get("pearson_r") is not None:
            st.metric("Pearson r", corr["pearson_r"])

    st.subheader("Activity heatmap (last 60 days)")
    heat = _api_get("/journal/analytics/heatmap", user_id=user_id, days=60)
    if heat:
        st.line_chart(
            {
                "journal": heat.get("journal", {}),
                "gratitude": heat.get("gratitude", {}),
                "mindfulness": heat.get("mindfulness", {}),
            }
        )
    else:
        st.caption("Use the app for a week or two and your heatmap will fill in.")

    st.subheader("Today")
    digest = _api_get("/journal/analytics/daily", user_id=user_id)
    if digest:
        d1, d2, d3 = st.columns(3)
        d1.metric("Entries today", len(digest.get("entries") or []))
        d2.metric("Gratitudes today", len(digest.get("gratitudes") or []))
        d3.metric("Sessions today", len(digest.get("sessions") or []))
