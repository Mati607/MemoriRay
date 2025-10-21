"""
Memory data models
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class MemoryBase(BaseModel):
    content: str
    mood_score: Optional[float] = None
    tags: Optional[list[str]] = []
    memory_type: str = "experience"

class MemoryCreate(MemoryBase):
    metadata: Optional[Dict[str, Any]] = {}

class Memory(MemoryBase):
    id: str
    user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class PhotoMemoryCreate(MemoryCreate):
    image_url: str

class VideoMemoryCreate(MemoryCreate):
    video_url: str

class TextualMemoryCreate(MemoryCreate):
    text_content: str

class AudioMemoryCreate(MemoryCreate):
    audio_url: str
