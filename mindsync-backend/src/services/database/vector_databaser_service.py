"""
Generate vector embeddings and store/retrieve them from vector database
"""

from typing import List
from src.config.settings import get_settings
from src.services.agent.multimodel_embedding_agent import MultimodalEmbeddingAgent

settings = get_settings()

class VectorDatabaserService:
    
    def __init__(self):
        self.agent = MultimodalEmbeddingAgent(settings.EMBEDDING_MODEL)
    
    async def generate_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        embedding = self.agent.encode_text(text, convert_to_tensor=False)
        return embedding.tolist()
    
    async def generate_photos(self, photo_path: str) -> List[float]:
        """Generate embedding for photos"""
        embedding = self.agent.encode_photo(photo_path, convert_to_tensor=False)
        return embedding.tolist()
    
    async def generate_audio(self, audio_path: str) -> List[float]:
        """Generate embedding for audio"""
        embedding = self.agent.encode_audio(audio_path, convert_to_tensor=False)
        return embedding.tolist()
    
    async def generate_video(self, video_path: str) -> List[float]:
        """Generate embedding for video"""
        embedding = self.agent.encode_video(video_path, convert_to_tensor=False)
        return embedding.tolist()

