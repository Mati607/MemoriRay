import streamlit as st
import requests
from datetime import datetime

API_BASE = "http://localhost:8000"

def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()

check_authentication()

st.set_page_config(page_title="Therapy Exercises", page_icon="🧘", layout="wide")

st.markdown("""
<style>
    :root {
        --mh-bg: #FFFBEB;
        --mh-card: #FFF7D6;
        --mh-ink: #3F3D2E;
        --mh-accent: #F4D06F;
        --mh-accent-2: #9ED2C6;
        --mh-accent-3: #C7E9B0;
    }
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--mh-bg) !important;
        color: var(--mh-ink) !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧘 Therapy Exercises")
st.markdown("Discover and practice evidence-based mental health exercises tailored to your needs.")

user_id = st.session_state.user_id

tab1, tab2, tab3 = st.tabs(["🎯 Recommended", "📚 Browse All", "✅ My Progress"])

with tab1:
    st.subheader("Personalized Recommendations")
    st.markdown("Based on your mood patterns, here are exercises that may help you:")

    try:
        rec_resp = requests.post(
            f"{API_BASE}/therapy/recommend",
            json={"user_id": user_id, "days": 30}
        )
        if rec_resp.status_code == 200:
            recommendations = rec_resp.json().get("recommendations", [])

            if not recommendations:
                st.info("Complete more mood entries for personalized recommendations.")
            else:
                for i, rec in enumerate(recommendations, 1):
                    with st.container():
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.markdown(f"### {i}. {rec['name']}")
                            st.write(f"**Description:** {rec['description']}")
                            st.caption(f"💡 {rec['reason']}")

                        with col2:
                            if st.button("Start →", key=f"start_{rec['exercise_type']}", use_container_width=True):
                                st.session_state.selected_exercise = rec
                                st.rerun()

                        st.divider()
    except Exception as e:
        st.error(f"Error loading recommendations: {e}")

with tab2:
    st.subheader("Browse All Exercises")

    category_filter = st.selectbox(
        "Filter by category:",
        ["All", "anxiety", "depression", "stress", "shame", "trauma"]
    )

    try:
        templates_resp = requests.get(f"{API_BASE}/therapy/templates")
        if templates_resp.status_code == 200:
            templates_data = templates_resp.json()
            templates = templates_data.get("templates", [])

            if category_filter != "All":
                templates = [t for t in templates if t.get("category") == category_filter]

            if not templates:
                st.info("No exercises found for this category.")
            else:
                for template in templates:
                    with st.expander(f"{template['name']} ({template['difficulty_level'].title()}) - {template['estimated_duration']}min"):
                        st.markdown(f"**Category:** `{template['category']}`")
                        st.markdown(f"**Description:** {template['description']}")

                        st.markdown("**Instructions:**")
                        st.markdown(template['instructions'])

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            if st.button("✅ Mark as Done", key=f"mark_{template['id']}"):
                                st.session_state.exercise_to_log = template
                                st.rerun()

                        with col2:
                            st.write(f"⏱️ {template['estimated_duration']}min")

                        with col3:
                            difficulty_emoji = "🟢" if template['difficulty_level'] == "beginner" else "🟡" if template['difficulty_level'] == "intermediate" else "🔴"
                            st.write(f"{difficulty_emoji} {template['difficulty_level'].title()}")

    except Exception as e:
        st.error(f"Error loading exercise templates: {e}")

with tab3:
    st.subheader("Your Exercise History")

    try:
        history_resp = requests.post(
            f"{API_BASE}/therapy/history",
            json={"user_id": user_id, "days": 90}
        )
        if history_resp.status_code == 200:
            history_data = history_resp.json()
            exercises = history_data.get("exercises", [])
            total = history_data.get("total", 0)

            st.metric("Total Exercises Completed", total)

            if exercises:
                st.markdown("### Recent Activities")
                for exercise in exercises[:10]:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                    with col1:
                        st.write(f"**{exercise['name']}**")
                        if exercise.get('notes'):
                            st.caption(f"Notes: {exercise['notes']}")

                    with col2:
                        if exercise.get('duration_minutes'):
                            st.metric("Duration", f"{exercise['duration_minutes']}min", label_visibility="collapsed")

                    with col3:
                        if exercise.get('effectiveness_rating'):
                            effectiveness = exercise['effectiveness_rating']
                            emoji = "⭐" * int(effectiveness)
                            st.metric("Effectiveness", emoji, label_visibility="collapsed")

                    with col4:
                        date = datetime.fromisoformat(exercise['completed_at']).strftime("%m/%d/%y")
                        st.caption(date)

                    st.divider()
            else:
                st.info("No exercises logged yet. Start with a recommended exercise above!")

    except Exception as e:
        st.error(f"Error loading history: {e}")

st.markdown("---")

if "selected_exercise" in st.session_state and st.session_state.selected_exercise:
    st.markdown("### 🎯 Start Exercise")

    exercise = st.session_state.selected_exercise

    st.markdown(f"## {exercise['name']}")
    st.markdown(f"**{exercise['description']}**")

    st.markdown("### Instructions:")
    st.info("Step through this exercise at your own pace.")

    col1, col2 = st.columns(2)

    with col1:
        duration = st.number_input("Duration (minutes):", min_value=1, max_value=120, value=5)

    with col2:
        effectiveness = st.slider("How effective was this?", 0.0, 5.0, 3.0, step=0.5)

    notes = st.text_area("Notes (optional):", placeholder="How did you feel during this exercise?")

    if st.button("✅ Complete Exercise", use_container_width=True, type="primary"):
        try:
            complete_resp = requests.post(
                f"{API_BASE}/therapy/complete_exercise",
                json={
                    "user_id": user_id,
                    "exercise_type": exercise['exercise_type'],
                    "name": exercise['name'],
                    "description": exercise['description'],
                    "category": exercise.get('category', 'general'),
                    "duration_minutes": int(duration),
                    "effectiveness_rating": effectiveness,
                    "notes": notes,
                }
            )
            if complete_resp.status_code == 200:
                st.success("✅ Great job! Exercise logged to your history.")
                st.balloons()
                st.session_state.selected_exercise = None
                st.rerun()
            else:
                st.error("Failed to log exercise")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.button("Cancel"):
        st.session_state.selected_exercise = None
        st.rerun()

st.markdown("---")

st.markdown("""
### 📚 About These Exercises

These exercises are based on evidence-based therapeutic approaches:

- **Breathing exercises**: Help regulate your nervous system and reduce anxiety
- **Grounding techniques**: Keep you present and reduce dissociation or panic
- **Body scan**: Increases awareness and reduces physical tension
- **Gratitude practice**: Shifts focus to positive experiences
- **Journaling**: Processes emotions and clarifies thoughts
- **Cognitive reframing**: Challenges unhelpful thought patterns (CBT)
- **Physical activity**: Boosts mood through endorphin release
- **Self-compassion**: Counters self-criticism and shame

**Remember:** These exercises are tools for self-care. If you're in crisis or experiencing severe symptoms, please reach out to a mental health professional or crisis line.
""")
