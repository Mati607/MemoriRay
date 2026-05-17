"""
Data export service for generating reports in CSV and PDF formats.
Provides utilities for exporting mood data, analytics, and progress reports.
"""

import csv
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from io import StringIO, BytesIO

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from database import SessionLocal, MoodEntry, TherapyExercise, WeeklyReport
from analytics_service import MoodAnalytics


class MoodDataExporter:
    """Export mood data in various formats."""

    @staticmethod
    def export_to_csv(user_id: int, days: int = 30) -> str:
        """Export mood entries as CSV."""
        db = SessionLocal()
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            entries = (
                db.query(MoodEntry)
                .filter(MoodEntry.user_id == user_id, MoodEntry.timestamp >= cutoff)
                .order_by(MoodEntry.timestamp.asc())
                .all()
            )

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Date", "Time", "Mood Score", "Emotion", "Intensity",
                "Triggers", "Notes"
            ])

            for entry in entries:
                timestamp = entry.timestamp
                date_str = timestamp.strftime("%Y-%m-%d")
                time_str = timestamp.strftime("%H:%M")
                writer.writerow([
                    date_str,
                    time_str,
                    entry.mood_score or "",
                    entry.emotion_category or "",
                    entry.intensity or "",
                    entry.triggers or "",
                    entry.message_snippet or "",
                ])

            return output.getvalue()
        finally:
            db.close()

    @staticmethod
    def export_exercises_to_csv(user_id: int, days: int = 90) -> str:
        """Export exercise history as CSV."""
        db = SessionLocal()
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            exercises = (
                db.query(TherapyExercise)
                .filter(TherapyExercise.user_id == user_id, TherapyExercise.completed_at >= cutoff)
                .order_by(TherapyExercise.completed_at.asc())
                .all()
            )

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Date", "Exercise Name", "Category", "Duration (min)",
                "Effectiveness (1-5)", "Notes"
            ])

            for exercise in exercises:
                date_str = exercise.completed_at.strftime("%Y-%m-%d %H:%M")
                writer.writerow([
                    date_str,
                    exercise.name or "",
                    exercise.category or "",
                    exercise.duration_minutes or "",
                    exercise.effectiveness_rating or "",
                    exercise.notes or "",
                ])

            return output.getvalue()
        finally:
            db.close()

    @staticmethod
    def export_weekly_report_to_csv(user_id: int, weeks: int = 12) -> str:
        """Export weekly reports as CSV."""
        db = SessionLocal()
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
            reports = (
                db.query(WeeklyReport)
                .filter(WeeklyReport.user_id == user_id, WeeklyReport.week_start >= cutoff)
                .order_by(WeeklyReport.week_start.asc())
                .all()
            )

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Week Start", "Week End", "Avg Mood", "Volatility",
                "Best Day", "Worst Day", "Exercises", "Dominant Emotions"
            ])

            for report in reports:
                start_str = report.week_start.strftime("%Y-%m-%d")
                end_str = report.week_end.strftime("%Y-%m-%d")
                writer.writerow([
                    start_str,
                    end_str,
                    report.avg_mood_score or "",
                    report.mood_volatility or "",
                    report.best_day or "",
                    report.worst_day or "",
                    report.exercises_completed or "",
                    report.dominant_emotions or "",
                ])

            return output.getvalue()
        finally:
            db.close()


class ProgressReportGenerator:
    """Generate comprehensive progress reports."""

    @staticmethod
    def generate_monthly_report(user_id: int, month: int, year: int) -> Dict:
        """Generate a detailed monthly progress report."""
        from datetime import date, timedelta

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        db = SessionLocal()
        try:
            mood_entries = (
                db.query(MoodEntry)
                .filter(
                    MoodEntry.user_id == user_id,
                    MoodEntry.timestamp >= start_dt,
                    MoodEntry.timestamp <= end_dt,
                )
                .all()
            )

            exercises = (
                db.query(TherapyExercise)
                .filter(
                    TherapyExercise.user_id == user_id,
                    TherapyExercise.completed_at >= start_dt,
                    TherapyExercise.completed_at <= end_dt,
                )
                .all()
            )

            mood_scores = [e.mood_score for e in mood_entries if e.mood_score is not None]
            emotions = [e.emotion_category for e in mood_entries if e.emotion_category]

            if mood_scores:
                import statistics
                avg_mood = statistics.mean(mood_scores)
                min_mood = min(mood_scores)
                max_mood = max(mood_scores)
                volatility = statistics.stdev(mood_scores) if len(mood_scores) > 1 else 0
            else:
                avg_mood = min_mood = max_mood = volatility = None

            exercise_effectiveness = [
                e.effectiveness_rating for e in exercises if e.effectiveness_rating
            ]

            emotion_counts = {}
            for emotion in emotions:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

            return {
                "month": start_date.strftime("%B %Y"),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "mood_data": {
                    "average": round(avg_mood, 2) if avg_mood else None,
                    "minimum": min_mood,
                    "maximum": max_mood,
                    "volatility": round(volatility, 2) if volatility else None,
                    "total_entries": len(mood_entries),
                },
                "exercises": {
                    "completed": len(exercises),
                    "avg_effectiveness": round(
                        statistics.mean(exercise_effectiveness), 2
                    ) if exercise_effectiveness else None,
                    "total_minutes": sum(e.duration_minutes or 0 for e in exercises),
                },
                "emotions": {
                    "most_common": max(emotion_counts.items(), key=lambda x: x[1])[0]
                    if emotion_counts else None,
                    "distribution": emotion_counts,
                },
            }
        finally:
            db.close()

    @staticmethod
    def generate_quarterly_comparison(user_id: int, year: int) -> Dict:
        """Generate quarterly comparison report."""
        from datetime import date, timedelta

        quarters_data = {}

        for quarter in range(1, 5):
            start_month = (quarter - 1) * 3 + 1
            start_date = date(year, start_month, 1)

            if quarter == 4:
                end_date = date(year, 12, 31)
            else:
                end_date = date(year, start_month + 3, 1) - timedelta(days=1)

            start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

            db = SessionLocal()
            try:
                mood_entries = (
                    db.query(MoodEntry)
                    .filter(
                        MoodEntry.user_id == user_id,
                        MoodEntry.timestamp >= start_dt,
                        MoodEntry.timestamp <= end_dt,
                    )
                    .all()
                )

                exercises = (
                    db.query(TherapyExercise)
                    .filter(
                        TherapyExercise.user_id == user_id,
                        TherapyExercise.completed_at >= start_dt,
                        TherapyExercise.completed_at <= end_dt,
                    )
                    .all()
                )

                mood_scores = [e.mood_score for e in mood_entries if e.mood_score is not None]

                if mood_scores:
                    import statistics
                    avg_mood = statistics.mean(mood_scores)
                else:
                    avg_mood = None

                quarters_data[f"Q{quarter}"] = {
                    "avg_mood": round(avg_mood, 2) if avg_mood else None,
                    "entries": len(mood_entries),
                    "exercises": len(exercises),
                }
            finally:
                db.close()

        return {
            "year": year,
            "quarters": quarters_data,
            "trend": "improving" if (
                quarters_data.get("Q4", {}).get("avg_mood", 0) > quarters_data.get("Q1", {}).get("avg_mood", 0)
            ) else "stable" if (
                abs(quarters_data.get("Q4", {}).get("avg_mood", 0) - quarters_data.get("Q1", {}).get("avg_mood", 0)) < 1
            ) else "declining",
        }

    @staticmethod
    def generate_year_summary(user_id: int, year: int) -> Dict:
        """Generate annual summary."""
        from datetime import date
        import statistics

        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        db = SessionLocal()
        try:
            mood_entries = (
                db.query(MoodEntry)
                .filter(
                    MoodEntry.user_id == user_id,
                    MoodEntry.timestamp >= start_dt,
                    MoodEntry.timestamp <= end_dt,
                )
                .all()
            )

            exercises = (
                db.query(TherapyExercise)
                .filter(
                    TherapyExercise.user_id == user_id,
                    TherapyExercise.completed_at >= start_dt,
                    TherapyExercise.completed_at <= end_dt,
                )
                .all()
            )

            mood_scores = [e.mood_score for e in mood_entries if e.mood_score is not None]
            emotions = [e.emotion_category for e in mood_entries if e.emotion_category]

            if mood_scores:
                avg_mood = statistics.mean(mood_scores)
                min_mood = min(mood_scores)
                max_mood = max(mood_scores)
            else:
                avg_mood = min_mood = max_mood = None

            emotion_counts = {}
            for emotion in emotions:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

            return {
                "year": year,
                "mood": {
                    "average": round(avg_mood, 2) if avg_mood else None,
                    "best": max_mood,
                    "worst": min_mood,
                    "total_entries": len(mood_entries),
                },
                "exercises": {
                    "total_completed": len(exercises),
                    "total_minutes": sum(e.duration_minutes or 0 for e in exercises),
                    "most_used": self._get_most_used_exercise(exercises) if exercises else None,
                },
                "primary_emotions": emotion_counts,
                "improvement_trend": self._calculate_trend(mood_entries),
            }
        finally:
            db.close()

    @staticmethod
    def _get_most_used_exercise(exercises: List) -> str:
        """Get most frequently used exercise."""
        exercise_counts = {}
        for exercise in exercises:
            name = exercise.name
            exercise_counts[name] = exercise_counts.get(name, 0) + 1
        return max(exercise_counts.items(), key=lambda x: x[1])[0] if exercise_counts else None

    @staticmethod
    def _calculate_trend(entries: List) -> str:
        """Calculate improvement trend over time."""
        if len(entries) < 10:
            return "insufficient_data"

        mood_scores = [e.mood_score for e in entries if e.mood_score is not None]
        if len(mood_scores) < 10:
            return "insufficient_data"

        import statistics
        first_half = statistics.mean(mood_scores[:len(mood_scores)//2])
        second_half = statistics.mean(mood_scores[len(mood_scores)//2:])

        diff = second_half - first_half
        if diff > 1:
            return "improving"
        elif diff < -1:
            return "declining"
        else:
            return "stable"


class PDFReportGenerator:
    """Generate PDF reports (requires reportlab)."""

    @staticmethod
    def generate_progress_report_pdf(user_id: int, month: int, year: int) -> Optional[bytes]:
        """Generate a PDF progress report."""
        if not REPORTLAB_AVAILABLE:
            return None

        report_data = ProgressReportGenerator.generate_monthly_report(user_id, month, year)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#3F3D2E'),
            spaceAfter=30,
            alignment=1,
        )

        story.append(Paragraph(f"Mental Health Progress Report", title_style))
        story.append(Paragraph(f"<b>{report_data['month']}</b>", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        mood_data = report_data['mood_data']
        mood_table_data = [
            ['Metric', 'Value'],
            ['Average Mood', f"{mood_data['average']}/10" if mood_data['average'] else 'N/A'],
            ['Range', f"{mood_data['minimum']} - {mood_data['maximum']}" if mood_data['minimum'] else 'N/A'],
            ['Volatility', f"{mood_data['volatility']}" if mood_data['volatility'] else 'N/A'],
            ['Total Entries', str(mood_data['total_entries'])],
        ]

        mood_table = Table(mood_table_data, colWidths=[2.5*inch, 2.5*inch])
        mood_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4D06F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        story.append(Paragraph("<b>Mood Statistics</b>", styles['Heading2']))
        story.append(mood_table)
        story.append(Spacer(1, 0.3*inch))

        exercise_data = report_data['exercises']
        exercise_table_data = [
            ['Metric', 'Value'],
            ['Exercises Completed', str(exercise_data['completed'])],
            ['Total Minutes', str(exercise_data['total_minutes'])],
            ['Avg Effectiveness', f"{exercise_data['avg_effectiveness']}/5" if exercise_data['avg_effectiveness'] else 'N/A'],
        ]

        exercise_table = Table(exercise_table_data, colWidths=[2.5*inch, 2.5*inch])
        exercise_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9ED2C6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F5F1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        story.append(Paragraph("<b>Exercise Progress</b>", styles['Heading2']))
        story.append(exercise_table)
        story.append(Spacer(1, 0.3*inch))

        emotions = report_data['emotions']
        story.append(Paragraph("<b>Emotions</b>", styles['Heading2']))
        story.append(Paragraph(
            f"<b>Most Common:</b> {emotions['most_common'] if emotions['most_common'] else 'N/A'}",
            styles['Normal']
        ))

        doc.build(story)
        return buffer.getvalue()
