from transformers import pipeline
from typing import Dict, List
import numpy as np



# MOOD_CATEGORIES = {
#     "positive": ["interested", "excited", "enthusiastic", "proud", "optimistic"],
#     "negative": ["distressed", "upset", "scared", "depressed"]
# }

class SafetyAnalyzer:
    """
    A class to monitor user's mood and detect low mood or harmful content.
    """
    def __init__(self):
        # Use emotion classification model
        self.emotion_classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            return_all_scores=True
        )
    
    def analyze_mood(self, text: str) -> Dict[str, float]:
        """
        Analyze the mood of the given text and return scores (0-5) for mood categories.
        
        Returns:
            Dict with 'positive' and 'negative' scores (0-5 scale)
        """
        # Get emotion predictions
        emotions = self.emotion_classifier(text)[0]
        
        # Map emotions to your categories
        emotion_scores = {item['label']: item['score'] for item in emotions}
        
        # Calculate positive and negative scores
        positive_score = (
            emotion_scores.get('joy', 0) * 1.2 +
            emotion_scores.get('surprise', 0) * 0.8 +
            emotion_scores.get('neutral', 0) * 0.3
        )
        
        negative_score = (
            emotion_scores.get('sadness', 0) * 1.0 +
            emotion_scores.get('anger', 0) * 1.0 +
            emotion_scores.get('fear', 0) * 1.0 +
            emotion_scores.get('disgust', 0) * 0.8
        )
        
        # Scale to 0-5 range
        return {
            "positive": min(5.0, positive_score * 5),
            "negative": min(5.0, negative_score * 5),
            "detailed_emotions": emotion_scores
        }
    

# Example usage:
if __name__ == "__main__":
    analyzer = SafetyAnalyzer()
    sample_text = "I am feeling very happy and excited about my new job!"
    mood_scores = analyzer.analyze_mood(sample_text)
    print("Mood Scores:", mood_scores)
    # Good!