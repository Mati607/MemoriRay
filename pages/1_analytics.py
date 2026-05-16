import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

API_BASE = "http://localhost:8000"

def check_authentication():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.error("Please log in first via the main chat page.")
        st.stop()

check_authentication()

st.set_page_config(page_title="Mood Analytics", page_icon="📊", layout="wide")

st.markdown("""
<style>
    :root {
        --mh-bg: #FFFBEB;
        --mh-card: #FFF7D6;
        --mh-ink: #3F3D2E;
        --mh-accent: #F4D06F;
        --mh-accent-2: #9ED2C6;
    }
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--mh-bg) !important;
        color: var(--mh-ink) !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Mood Analytics Dashboard")
st.markdown("Track your emotional patterns, identify triggers, and understand your mental health trends.")

user_id = st.session_state.user_id
days_range = st.sidebar.slider("Analysis Period (days):", 7, 90, 30)

col1, col2, col3, col4 = st.columns(4)

try:
    with st.spinner("Loading statistics..."):
        stats_resp = requests.post(
            f"{API_BASE}/analytics/mood_stats",
            json={"user_id": user_id, "days": days_range}
        )
        stats = stats_resp.json() if stats_resp.status_code == 200 else {}

    with col1:
        avg_mood = stats.get("avg_mood")
        if avg_mood is not None:
            st.metric("Average Mood", f"{avg_mood:.1f}/10",
                     delta="📈 Positive" if avg_mood >= 5 else "📉 Needs support")
        else:
            st.info("No mood data yet")

    with col2:
        mood_range = stats.get("max_mood")
        if mood_range is not None and stats.get("min_mood") is not None:
            st.metric("Mood Range", f"{stats['min_mood']:.1f} - {mood_range:.1f}")

    with col3:
        volatility = stats.get("volatility")
        if volatility is not None:
            st.metric("Stability", f"σ = {volatility:.2f}",
                     delta="⚠️ High" if volatility > 2.5 else "✅ Good")
        else:
            st.info("Calculating...")

    with col4:
        entries = stats.get("total_entries", 0)
        st.metric("Entries", entries, delta=f"last {days_range} days")

except Exception as e:
    st.error(f"Error loading statistics: {e}")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📈 Trends", "😊 Patterns", "⚠️ Triggers", "💡 Insights"])

with tab1:
    st.subheader("Mood Over Time")
    try:
        mood_data_resp = requests.post(
            f"{API_BASE}/mood/data",
            json={"user_id": user_id, "days": days_range}
        )
        if mood_data_resp.status_code == 200:
            mood_data = mood_data_resp.json()
            if mood_data.get("scores"):
                df = pd.DataFrame({
                    "Date": pd.to_datetime(mood_data["dates"]),
                    "Mood Score": mood_data["scores"],
                    "Emotion": mood_data["emotions"],
                })

                fig = px.line(df, x="Date", y="Mood Score",
                             hover_data=["Emotion"],
                             title="Mood Trend",
                             markers=True,
                             color_discrete_sequence=["#9ED2C6"])
                fig.add_hline(y=5, line_dash="dash", line_color="gray", annotation_text="Neutral")
                fig.update_layout(hovermode="x unified", template="plotly_light")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No mood data available yet")
        else:
            st.error("Failed to load mood data")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("Mood Patterns")
    try:
        patterns_resp = requests.post(
            f"{API_BASE}/analytics/patterns",
            json={"user_id": user_id, "days": days_range}
        )
        if patterns_resp.status_code == 200:
            patterns = patterns_resp.json()

            col1, col2 = st.columns(2)

            with col1:
                if patterns.get("daily_averages"):
                    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    daily_data = {k: patterns["daily_averages"].get(k, 0) for k in days_order
                                 if k in patterns["daily_averages"]}

                    if daily_data:
                        fig = px.bar(x=list(daily_data.keys()), y=list(daily_data.values()),
                                    title="Average Mood by Day of Week",
                                    labels={"x": "Day", "y": "Average Mood"},
                                    color_discrete_sequence=["#F4D06F"])
                        st.plotly_chart(fig, use_container_width=True)

            with col2:
                if patterns.get("emotion_distribution"):
                    emotions = patterns["emotion_distribution"]
                    fig = px.pie(values=list(emotions.values()), names=list(emotions.keys()),
                                title="Emotion Distribution",
                                color_discrete_sequence=px.colors.qualitative.Set3)
                    st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.success(f"✅ Best Day: {patterns.get('best_day', 'N/A')}")
            with col2:
                st.warning(f"⚠️ Worst Day: {patterns.get('worst_day', 'N/A')}")

            st.info(f"Dominant Emotions: {', '.join(patterns.get('dominant_emotions', []))}")
        else:
            st.error("Failed to load patterns")
    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.subheader("Mood Triggers")
    try:
        triggers_resp = requests.post(
            f"{API_BASE}/analytics/triggers",
            json={"user_id": user_id, "days": days_range}
        )
        if triggers_resp.status_code == 200:
            triggers = triggers_resp.json()
            if triggers:
                for trigger in triggers:
                    with st.container():
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.write(f"**{trigger['trigger']}**")
                        with col2:
                            st.metric("Frequency", trigger['frequency'])
                        with col3:
                            impact_color = "🔴" if trigger['impact'] == "high" else "🟡" if trigger['impact'] == "medium" else "🟢"
                            st.write(f"{impact_color} {trigger['impact'].title()}")
            else:
                st.info("No clear triggers identified yet. Keep tracking!")
        else:
            st.error("Failed to load triggers")
    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.subheader("AI-Generated Insights")
    try:
        insights_resp = requests.post(
            f"{API_BASE}/analytics/insights",
            json={"user_id": user_id, "days": days_range}
        )
        if insights_resp.status_code == 200:
            insights_data = insights_resp.json()
            insights = insights_data.get("insights", [])

            if insights:
                for insight in insights:
                    insight_type = insight.get("type", "insight")

                    if insight_type == "mood_alert":
                        st.error(f"🚨 {insight['title']}")
                    elif insight_type == "positive_trend":
                        st.success(f"✨ {insight['title']}")
                    elif insight_type == "volatility_alert":
                        st.warning(f"⚠️ {insight['title']}")
                    else:
                        st.info(f"ℹ️ {insight['title']}")

                    st.write(insight['description'])
                    st.caption(f"Confidence: {insight['confidence']*100:.0f}%")
                    st.divider()
            else:
                st.info("Not enough data to generate insights yet")
        else:
            st.error("Failed to load insights")
    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 Weekly Summary")
    try:
        summary_resp = requests.post(
            f"{API_BASE}/analytics/weekly_summary",
            json={"user_id": user_id, "days": 7}
        )
        if summary_resp.status_code == 200:
            summary = summary_resp.json()

            st.metric("Weekly Average", f"{summary.get('avg_mood_score', 0):.1f}/10")
            st.metric("Exercises", summary.get('exercises_completed', 0))
            st.metric("Entries", summary.get('total_entries', 0))

            if summary.get("dominant_emotions"):
                st.caption(f"Emotions: {summary['dominant_emotions']}")
    except Exception as e:
        st.error(f"Error: {e}")

with col2:
    st.subheader("💡 Improvement Ideas")
    try:
        suggestions_resp = requests.post(
            f"{API_BASE}/analytics/suggestions",
            json={"user_id": user_id, "days": 30}
        )
        if suggestions_resp.status_code == 200:
            suggestions = suggestions_resp.json().get("suggestions", [])
            for i, suggestion in enumerate(suggestions[:3], 1):
                st.write(f"{i}. {suggestion}")
    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("---")

if st.button("🔄 Generate Weekly Report", use_container_width=True):
    try:
        with st.spinner("Generating comprehensive report..."):
            report_resp = requests.post(
                f"{API_BASE}/analytics/generate_report",
                json={"user_id": user_id}
            )
            if report_resp.status_code == 200:
                st.success("✅ Weekly report generated and saved!")
                st.balloons()
            else:
                st.error("Failed to generate report")
    except Exception as e:
        st.error(f"Error: {e}")
