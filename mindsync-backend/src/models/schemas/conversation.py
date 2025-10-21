"""
Conversation data models
"""
from pydantic import BaseModel
from typing import Optional, List, Dict

class ConversationMessage(BaseModel):
    content: str
    history: Optional[List[Dict]] = []

class ConversationResponse(BaseModel):
    content: str
    mood_detected: Optional[float] = None
    memories_used: Optional[List[str]] = []
