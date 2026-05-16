import streamlit as st
import requests
from datetime import datetime

API_BASE = "http://localhost:8000"

def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()

check_authentication()

st.set_page_config(page_title="Mood Journal", page_icon="📔", layout="centered")

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
    .stApp [data-testid="stAppViewContainer"] {
        max-width: 800px;
        margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

st.title("📔 Mood Journal")
st.markdown("Record your mood and emotions to track patterns and gain insights about your mental health.")

user_id = st.session_state.user_id

with st.form("mood_entry_form"):
    st.markdown("### How are you feeling right now?")

    mood_score = st.slider(
        "Mood Rating (0 = Very Low, 10 = Excellent)",
        min_value=0,
        max_value=10,
        value=5,
        step=1
    )

    st.markdown("---")

    st.markdown("### What emotion are you experiencing?")

    emotions = [
        "Happy 😊", "Sad 😢", "Anxious 😰", "Angry 😠",
        "Calm 😌", "Excited 🤩", "Tired 😴", "Stressed 😫",
        "Hopeful 🌅", "Hopeless 😞", "Grateful 🙏", "Confused 😕",
        "Lonely 😔", "Connected 🤝", "Peaceful 😇", "Overwhelmed 😵"
    ]

    emotion_choice = st.selectbox(
        "Primary emotion:",
        emotions,
        label_visibility="collapsed"
    )

    emotion_category = emotion_choice.split()[0].lower()

    intensity = st.slider(
        "Intensity of this emotion (1 = Mild, 10 = Overwhelming)",
        min_value=1,
        max_value=10,
        value=5,
        step=1
    )

    st.markdown("---")

    st.markdown("### What triggered this feeling?")

    trigger_options = [
        "Work/School stress",
        "Relationship issue",
        "Health concern",
        "Financial worry",
        "Social situation",
        "Family matter",
        "Personal achievement",
        "Loss or grief",
        "Physical pain/discomfort",
        "Sleep deprivation",
        "Other"
    ]

    selected_triggers = st.multiselect(
        "Select any triggers (or leave blank):",
        trigger_options,
        label_visibility="collapsed"
    )

    triggers_str = ", ".join(selected_triggers) if selected_triggers else ""

    st.markdown("---")

    st.markdown("### What would you like to share?")

    sentiment_text = st.text_area(
        "Write about what's on your mind:",
        placeholder="Share your thoughts and feelings...",
        height=150,
        label_visibility="collapsed"
    )

    message_snippet = sentiment_text[:300] if sentiment_text else ""

    st.markdown("---")

    st.markdown("### Self-Care Actions")

    self_care = st.multiselect(
        "What have you done for self-care today?",
        [
            "Exercise",
            "Meditation/Mindfulness",
            "Journaling",
            "Social time",
            "Creative activity",
            "Therapy/Counseling",
            "Time in nature",
            "Good sleep",
            "Healthy eating",
            "Rest/Relaxation"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")

    submitted = st.form_submit_button("💾 Save Mood Entry", use_container_width=True, type="primary")

    if submitted:
        if not sentiment_text.strip():
            st.warning("Please share something about how you're feeling.")
        else:
            try:
                with st.spinner("Saving mood entry..."):
                    record_resp = requests.post(
                        f"{API_BASE}/mood/record",
                        json={
                            "user_id": user_id,
                            "mood_score": mood_score,
                            "sentiment_text": sentiment_text,
                            "emotion_category": emotion_category,
                            "intensity": intensity,
                            "triggers": triggers_str,
                            "message_snippet": message_snippet,
                        }
                    )

                    if record_resp.status_code == 200:
                        st.success("✅ Mood entry saved successfully!")

                        col1, col2 = st.columns(2)

                        with col1:
                            st.metric("Mood Score", f"{mood_score}/10")

                        with col2:
                            st.metric("Emotion Intensity", f"{intensity}/10")

                        if self_care:
                            st.info(f"Great self-care practices today: {', '.join(self_care)}")

                        st.balloons()

                        st.markdown("---")
                        st.markdown("### Next Steps")
                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("📊 View Analytics", use_container_width=True):
                                st.switch_page("pages/1_analytics.py")

                        with col2:
                            if st.button("🧘 Try an Exercise", use_container_width=True):
                                st.switch_page("pages/2_therapy_exercises.py")

                    else:
                        st.error("Failed to save mood entry. Please try again.")

            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("---")

st.markdown("""
### 💡 Tips for Journaling

1. **Be honest** - There are no "right" or "wrong" feelings
2. **Be specific** - Note what happened and how it affected you
3. **Track patterns** - Over time, you'll notice what helps and what hinders
4. **Use it for growth** - Journaling is a tool for self-understanding
5. **Regular practice** - Daily entries help you notice trends

### Why Track Mood?

- Identify triggers and patterns
- Notice what helps you feel better
- Communicate more effectively with therapists
- Build awareness of your emotional health
- Celebrate improvements and progress
""")
