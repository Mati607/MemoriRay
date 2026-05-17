# Analytics & Therapy Exercises Feature

A comprehensive mental health analytics and therapy exercises system added to MemoriRay, featuring mood pattern analysis, evidence-based exercises, and personalized insights.

## Overview

This feature adds:
- **Mood Analytics Dashboard**: Track mood trends, patterns, triggers, and volatility
- **Therapy Exercise Library**: Evidence-based CBT/DBT exercises with progress tracking
- **AI Insights Generator**: Automatic analysis of mood data with personalized recommendations
- **Weekly Reports**: Comprehensive summaries of emotional patterns and progress
- **Mood Journaling**: Structured emotion tracking with trigger identification

## Architecture

### New Database Tables

1. **TherapyExercise** - Log completed exercises with effectiveness ratings
2. **ExerciseTemplate** - Store reusable exercise definitions
3. **MoodInsight** - Store AI-generated insights about mood patterns
4. **WeeklyReport** - Store comprehensive weekly mental health summaries
5. **MoodEntry extensions** - Added emotion_category, intensity, triggers fields

### Services (analytics_service.py)

**MoodAnalytics Class**
- `get_mood_statistics()`: Calculate avg, min, max mood and volatility
- `identify_mood_patterns()`: Detect daily patterns and dominant emotions
- `detect_mood_triggers()`: Identify which situations affect mood
- `generate_weekly_summary()`: Create comprehensive weekly snapshot
- `generate_improvement_suggestions()`: Personalized recommendations based on patterns

**TherapyRecommender Class**
- Pre-built exercise database with 8 core exercises
- `recommend_exercises()`: Match exercises to user's dominant emotions
- Category-based recommendations (anxiety, depression, stress, shame)

**InsightGenerator Class**
- `generate_all_insights()`: Create 5 different insight types
- Mood alerts, positive trends, emotion patterns, triggers, volatility analysis
- Confidence scoring for each insight

### API Endpoints (bot.py)

**Analytics Endpoints**
- `POST /analytics/mood_stats` - Get mood statistics
- `POST /analytics/patterns` - Identify mood patterns
- `POST /analytics/triggers` - Detect mood triggers
- `POST /analytics/weekly_summary` - Generate weekly summary
- `POST /analytics/suggestions` - Get improvement suggestions
- `POST /analytics/insights` - Get AI-generated insights
- `POST /analytics/insight_history` - Retrieve past insights
- `POST /analytics/latest_report` - Get latest weekly report
- `POST /analytics/generate_report` - Create new weekly report
- `POST /mood/data` - Get mood data for charting
- `POST /mood/record` - Record detailed mood entry

**Therapy Endpoints**
- `POST /therapy/recommend` - Get exercise recommendations
- `POST /therapy/complete_exercise` - Log completed exercise
- `POST /therapy/history` - Get exercise history
- `GET /therapy/templates` - List available exercises

## Streamlit Pages

### 1. analytics.py - Mood Analytics Dashboard
- **Charts & Metrics**
  - Mood trend line chart with 30-day view
  - Daily mood averages by day of week
  - Emotion distribution pie chart
  - Volatility and stability metrics
  - Best/worst day identification

- **Insights**
  - AI-generated insights with confidence scores
  - Mood alerts and positive trends
  - Trigger awareness alerts
  - Actionable recommendations

- **Weekly Summary**
  - Average mood, exercises completed
  - Dominant emotions
  - Improvement suggestions
  - Generate button for comprehensive reports

### 2. therapy_exercises.py - Exercise Library
- **Personalized Recommendations**
  - 3 exercises matched to dominant emotions
  - Explanation of why recommended

- **Browse All**
  - Filter by category (anxiety, depression, stress, etc.)
  - Difficulty levels (beginner, intermediate, advanced)
  - Estimated duration
  - Detailed instructions

- **Progress Tracking**
  - Exercise history with dates
  - Effectiveness ratings (1-5 stars)
  - Duration tracking
  - Personal notes

### 3. mood_journal.py - Mood Journaling
- **Structured Entry Form**
  - Mood rating (0-10 scale)
  - Emotion selection (16 options)
  - Intensity rating (1-10)
  - Multi-select trigger identification
  - Free-form text journal
  - Self-care activities tracking

- **Validation**
  - Requires mood reflection text
  - Tracks all metadata

## Core Exercises Included

8 evidence-based exercises across 4 categories:

**Anxiety Management**
- Box Breathing (5 min)
- 5-4-3-2-1 Grounding (10 min)

**Stress Relief**
- Progressive Body Scan (15 min)
- Emotion Journal (20 min)

**Depression Support**
- Gratitude Reflection (10 min)
- Thought Challenge / Cognitive Reframing (15 min)
- Movement Break (10 min)

**Shame/Self-Esteem**
- Self-Compassion Practice (5 min)

## Data Flow Example

1. **User Records Mood**
   - Fills journal form with mood score 5/10, emotion "anxious", trigger "work meeting"
   - Data saved to MoodEntry table

2. **Analytics Generate**
   - Query last 30 days of mood entries
   - Calculate statistics (avg: 5.2, volatility: 1.8)
   - Detect patterns (anxiety peaks on Mondays)
   - Find triggers (work meetings: 3x, sleep issues: 2x)

3. **Insights Generated**
   - "Work meetings are a significant trigger"
   - "Consider mindfulness exercises"
   - Insights saved to MoodInsight table

4. **Recommendations**
   - Match anxious emotion to exercises
   - Suggest Box Breathing, Grounding, Journaling
   - Display on exercises page

5. **Weekly Report**
   - Aggregate statistics
   - Generate improvement suggestions
   - Save to WeeklyReport table

## Implementation Details

### Mood Scoring Algorithm
- Sentiment keywords mapped to numeric scores (0-10)
- Positive words: happy (8.0), joyful (9.0), etc.
- Negative words: sad (3.0), depressed (1.5), etc.
- Default to 5.0 if no keywords found

### Volatility Calculation
- Standard deviation of mood scores
- High volatility (>2.5) → suggests need for stability exercises
- Low volatility (<1.0) → consistent mood patterns

### Trigger Detection
- Identify moods below 4/10
- Extract triggers from most recent entries
- Count frequency
- Impact classification: high (≥3), medium (≥2), low

### Pattern Identification
- Group mood scores by day of week
- Calculate daily averages
- Find best/worst performing days
- Analyze emotion distribution

## API Request Examples

### Record a Mood Entry
```json
POST /mood/record
{
  "user_id": 1,
  "mood_score": 6.5,
  "sentiment_text": "Had a good day at work, feeling accomplished",
  "emotion_category": "happy",
  "intensity": 7.0,
  "triggers": "work achievement",
  "message_snippet": "Had a good day at work..."
}
```

### Get Mood Statistics
```json
POST /analytics/mood_stats
{
  "user_id": 1,
  "days": 30
}

Response:
{
  "avg_mood": 5.4,
  "min_mood": 2.0,
  "max_mood": 8.5,
  "volatility": 1.8,
  "total_entries": 24
}
```

### Get Exercise Recommendations
```json
POST /therapy/recommend
{
  "user_id": 1,
  "days": 30
}

Response:
{
  "recommendations": [
    {
      "exercise_type": "breathing",
      "name": "Box Breathing",
      "description": "Calming breathing technique",
      "reason": "Helpful for managing anxiety"
    },
    ...
  ]
}
```

### Log Completed Exercise
```json
POST /therapy/complete_exercise
{
  "user_id": 1,
  "exercise_type": "breathing",
  "name": "Box Breathing",
  "description": "Calming breathing technique",
  "category": "anxiety",
  "duration_minutes": 5,
  "effectiveness_rating": 4.0,
  "notes": "Felt more calm after, helped before meeting"
}
```

## Statistics

### Code Added
- **analytics_service.py**: ~400 lines - Core analytics logic
- **database.py**: ~180 lines added - Schema extensions and helpers
- **bot.py**: ~400 lines added - API endpoints and models
- **pages/1_analytics.py**: ~300 lines - Analytics dashboard UI
- **pages/2_therapy_exercises.py**: ~300 lines - Exercises UI
- **pages/3_mood_journal.py**: ~250 lines - Journaling UI

**Total**: ~1,820 lines of new feature code

## Security & Privacy

- All data associated with user_id for per-user isolation
- Mood data stored in authenticated sessions
- No external API calls for mood analysis (all local)
- Exercise templates are static/read-only

## Future Enhancements

1. **Export Reports**: PDF/CSV downloads of analytics
2. **Goal Tracking**: Set mood improvement goals
3. **Medication Log**: Track medication effects
4. **Social Features**: Share progress with trusted contacts
5. **Therapist Integration**: Export reports for therapy sessions
6. **ML Insights**: Predictive mood forecasting
7. **Biometric Integration**: Heart rate, sleep data
8. **Push Notifications**: Daily mood check-ins
9. **Wearable Support**: Apple Health, Fitbit integration
10. **Video Guides**: Exercise demonstration videos

## Testing

The feature includes:
- Database schema validation on startup
- API error handling and validation
- Form validation in Streamlit UI
- Graceful fallbacks for missing data
- Error messages for failed operations

## Usage Flow

1. **Start on Main Chat Page**: Standard MemoriRay chat
2. **Navigate to Analytics**: View mood dashboard and trends
3. **Check Recommendations**: See exercise suggestions
4. **Log Exercise**: Complete an exercise and rate effectiveness
5. **Record Mood**: Use mood journal to track feelings
6. **View Weekly Report**: Understand patterns and progress
7. **Iterate**: Repeat and adjust based on insights
