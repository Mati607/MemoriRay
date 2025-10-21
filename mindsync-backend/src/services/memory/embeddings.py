"""
Embedding Generator - Converts text to vectors
"""
from sentence_transformers import SentenceTransformer
from typing import List
from src.config.settings import get_settings

settings = get_settings()

class EmbeddingGenerator:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    async def generate_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        embedding = self.model.encode_text(text, convert_to_tensor=False)
        return embedding.tolist()
    
    async def generate_photos(self, photo_path: str) -> List[float]:
        """Generate embedding for photos"""
        embedding = self.model.encode_photo(photo_path, convert_to_tensor=False)
        return embedding.tolist()
        
    async def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()
