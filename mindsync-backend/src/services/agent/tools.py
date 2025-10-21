"""
Agent Tools - Memory recall and mood analysis tools
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

class MemoryRecallInput(BaseModel):
    """Input for memory recall tool"""
    mood_context: str = Field(description="Current emotional context or mood description")
    user_id: str = Field(description="User identifier")

class MemoryRecallTool(BaseTool):
    name = "memory_recall"
    description = "Retrieves positive memories when user seems down or needs emotional support"
    args_schema: Type[BaseModel] = MemoryRecallInput
    
    def _run(self, mood_context: str, user_id: str) -> str:
        """Synchronous version"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, mood_context: str, user_id: str) -> str:
        """Retrieve memories based on mood"""
        from src.services.memory.memory_service import MemoryService
        
        memory_service = MemoryService()
        memories = await memory_service.recall_memories(
            user_id=user_id,
            mood_context=mood_context,
            top_k=3
        )
        
        if not memories:
            return "No positive memories found in storage yet."
        
        memory_text = "\n".join([
            f"- {m.get('documents', [''])[0]} (mood: {m.get('metadatas', [{}])[0].get('mood_score', 'N/A')})"
            for m in memories.get('ids', [])
        ])
        
        return f"Retrieved positive memories:\n{memory_text}"

class MoodAnalysisInput(BaseModel):
    """Input for mood analysis tool"""
    message: str = Field(description="User's message to analyze")

class MoodAnalysisTool(BaseTool):
    name = "mood_analysis"
    description = "Analyzes the emotional tone and mood from user's message"
    args_schema: Type[BaseModel] = MoodAnalysisInput
    
    def _run(self, message: str) -> str:
        """Synchronous version"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, message: str) -> float:
        """Analyze mood from message"""
        # Simple sentiment analysis - replace with more sophisticated model
        from textblob import TextBlob
        
        blob = TextBlob(message)
        sentiment = blob.sentiment.polarity  # -1 to 1
        
        # Convert to 0-10 scale
        mood_score = (sentiment + 1) * 5
        
        return f"Mood score: {mood_score:.1f}/10 (sentiment: {sentiment:.2f})"
