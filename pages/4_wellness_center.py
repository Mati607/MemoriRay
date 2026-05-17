import streamlit as st
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000"

def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()

check_authentication()

st.set_page_config(page_title="Wellness Center", page_icon="🌟", layout="wide")

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

st.title("🌟 Wellness Center")
st.markdown("Comprehensive mental health support, personalized recommendations, and goal tracking.")

user_id = st.session_state.user_id

tab1, tab2, tab3, tab4 = st.tabs(["💡 Recommendations", "🎯 Goals", "🏆 Achievements", "🆘 Crisis Support"])

with tab1:
    st.subheader("Personalized Wellness Recommendations")
    st.markdown("Based on your mood patterns and mental health data, here are personalized recommendations:")

    try:
        recommendations_resp = requests.post(
            f"{API_BASE}/wellness/recommendations",
            json={"user_id": user_id}
        )

        if recommendations_resp.status_code == 200:
            recommendations = recommendations_resp.json().get("recommendations", [])

            if not recommendations:
                st.info("Complete more mood entries to receive personalized recommendations.")
            else:
                for rec in recommendations:
                    priority_color = {
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢",
                    }.get(rec.get("priority", "medium"), "🟡")

                    with st.container():
                        col1, col2 = st.columns([1, 4])

                        with col1:
                            st.write(f"{rec.get('emoji', '•')} {priority_color}")

                        with col2:
                            st.markdown(f"### {rec.get('title', 'Recommendation')}")
                            st.write(rec.get('description', ''))

                        st.markdown("**Recommended Actions:**")
                        for action in rec.get('actions', [])[:3]:
                            st.write(f"• {action}")

                        st.divider()
        else:
            st.error("Failed to load recommendations")
    except Exception as e:
        st.error(f"Error: {e}")

    st.markdown("---")

    if st.button("📋 Get Personalized 7-Day Action Plan", use_container_width=True):
        try:
            with st.spinner("Generating your action plan..."):
                plan_resp = requests.post(
                    f"{API_BASE}/wellness/action_plan",
                    json={"user_id": user_id, "days": 7}
                )
                if plan_resp.status_code == 200:
                    plan = plan_resp.json().get("plan", {})

                    st.success("✅ Your 7-Day Action Plan")

                    st.markdown("### Priority Actions")
                    priority_actions = plan.get("priority_actions", [])
                    for i, action in enumerate(priority_actions[:5], 1):
                        st.write(f"{i}. {action.get('action', '')}")

                    st.markdown("### Daily Schedule")
                    for day_schedule in plan.get("daily_schedule", []):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.caption(f"Day {day_schedule['day']}")
                            st.write(f"🌅 {day_schedule['morning']}")
                        with col2:
                            st.write(f"🌤️ {day_schedule['afternoon']}")
                        with col3:
                            st.write(f"🌙 {day_schedule['evening']}")
        except Exception as e:
            st.error(f"Error: {e}")

with tab2:
    st.subheader("Wellness Goals")

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["My Goals", "New Goal", "Goal Templates"])

    with sub_tab1:
        st.markdown("### Current Goals")
        try:
            goals_resp = requests.post(
                f"{API_BASE}/wellness/goals",
                json={"user_id": user_id}
            )

            if goals_resp.status_code == 200:
                goals = goals_resp.json().get("goals", [])

                if not goals:
                    st.info("No active goals yet. Create one to get started!")
                else:
                    for goal in goals:
                        progress = goal.get("progress_percent", 0)

                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.markdown(f"**{goal['title']}**")
                            st.write(f"{goal.get('description', '')}")

                            st.progress(min(progress / 100, 1.0))
                            st.caption(
                                f"{progress:.0f}% complete • "
                                f"{goal.get('current_value', 0):.1f}/{goal.get('target_value', 0)} {goal.get('unit', '')}"
                            )

                        with col2:
                            if goal.get("days_remaining"):
                                st.metric("Days Left", goal["days_remaining"])

                        with col3:
                            if st.button("✓ Update", key=f"goal_{goal['id']}"):
                                st.session_state.goal_to_update = goal['id']
                                st.rerun()

                        st.divider()
        except Exception as e:
            st.error(f"Error: {e}")

    with sub_tab2:
        st.markdown("### Create New Goal")

        goal_type = st.selectbox(
            "Goal Type:",
            {
                "mood_improvement": "Improve Mood",
                "exercise_frequency": "Exercise Regularly",
                "meditation_streak": "Meditation Streak",
                "mood_stability": "Stabilize Mood",
                "sleep_improvement": "Better Sleep",
                "stress_reduction": "Reduce Stress",
                "social_connection": "Social Connection",
                "therapy_attendance": "Therapy Attendance",
                "self_care": "Self-Care",
                "journaling": "Journaling",
            }
        )

        title = st.text_input("Goal Title:", placeholder="e.g., Meditate Daily")
        description = st.text_area("Description:", placeholder="Why is this goal important?")
        target_value = st.number_input("Target Value:", min_value=1.0, max_value=100.0, step=0.5)

        days_until_target = st.slider("Days to achieve goal:", 7, 365, 30)
        target_date = datetime.now() + timedelta(days=days_until_target)

        if st.button("Create Goal", use_container_width=True, type="primary"):
            try:
                create_resp = requests.post(
                    f"{API_BASE}/wellness/create_goal",
                    json={
                        "user_id": user_id,
                        "title": title,
                        "goal_type": goal_type,
                        "target_value": target_value,
                        "target_date": target_date.isoformat(),
                        "description": description,
                    }
                )

                if create_resp.status_code == 200:
                    st.success("✅ Goal created! Track your progress in the Goals tab.")
                    st.rerun()
                else:
                    st.error("Failed to create goal")
            except Exception as e:
                st.error(f"Error: {e}")

    with sub_tab3:
        st.markdown("### Suggested Goals")
        try:
            suggest_resp = requests.post(
                f"{API_BASE}/wellness/suggest_goals",
                json={"user_id": user_id}
            )

            if suggest_resp.status_code == 200:
                suggestions = suggest_resp.json().get("suggestions", [])

                for sugg in suggestions:
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(f"**{sugg['title']}**")
                        st.caption(f"Why: {sugg['reason']}")

                    with col2:
                        if st.button("Create →", key=f"sugg_{sugg['goal_type']}"):
                            st.session_state.create_from_template = sugg
                            st.rerun()

                    st.divider()
        except Exception as e:
            st.error(f"Error: {e}")

with tab3:
    st.subheader("Your Achievements 🏆")

    try:
        achievements_resp = requests.post(
            f"{API_BASE}/wellness/milestones",
            json={"user_id": user_id}
        )

        if achievements_resp.status_code == 200:
            achievements = achievements_resp.json().get("milestones", [])

            if not achievements:
                st.info("Start tracking to earn your first achievement!")
            else:
                cols = st.columns(min(3, len(achievements)))
                for i, achievement in enumerate(achievements):
                    with cols[i % len(cols)]:
                        st.metric(
                            achievement['icon'],
                            achievement['name'],
                            value=achievement['description'],
                        )

            st.markdown("---")
            st.markdown("### Unlocked Soon")
            st.info(
                """
                Continue tracking and practicing exercises to unlock:
                - 🔓 10 Exercises Completed
                - 🔓 100 Mood Entries
                - 🔓 Full Month Consistency
                - 🔓 Perfect Week (stable mood)
                """
            )
    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.subheader("🆘 Crisis Support Resources")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Immediate Help")
        st.error(
            """
            **If you're in crisis or having thoughts of self-harm:**

            🚨 **Call Emergency Services**: 911 (USA)

            📞 **988 Suicide & Crisis Lifeline**
            - Call: 988
            - Available 24/7

            💬 **Crisis Text Line**
            - Text HOME to 741741
            - Available 24/7
            """
        )

    with col2:
        st.markdown("### When to Seek Help")
        st.warning(
            """
            Consider professional support if you experience:

            ✓ Persistent hopelessness
            ✓ Loss of interest in activities
            ✓ Significant mood changes
            ✓ Thoughts of self-harm
            ✓ Withdrawal from others
            ✓ Inability to function daily
            ✓ Substance misuse
            ✓ Panic or extreme anxiety
            """
        )

    st.markdown("---")

    st.markdown("### Resources")
    st.info(
        """
        **Mental Health Resources:**
        - NAMI (National Alliance on Mental Illness): 1-800-950-NAMI
        - SAMHSA National Helpline: 1-800-662-4357
        - International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/

        **Therapy Options:**
        - Psychology Today Therapist Finder
        - BetterHelp (Online Therapy)
        - Talkspace (Online Counseling)
        - Local community mental health centers
        """
    )

st.markdown("---")

st.markdown("""
### 💪 Remember

You are taking important steps by tracking your mood and engaging with wellness practices.
Recovery is possible, and you don't have to do it alone.

If you're struggling, please reach out to someone you trust or a mental health professional.
""")
