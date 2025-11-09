"""
This agent processes dataset: given the incoming memory data, it both stores it into the object storage 
and generates the embedding of the memory and stores it into the vector database.
"""

from pathlib import Path
from typing import Union, BinaryIO, Dict, Any, List
from src.services.database.object_storage_service import ObjectStorageService
from src.services.database.vector_databaser_service import VectorDatabaserService

class DatasetAgent:
    def __init__(
        self,
        object_storage_service: ObjectStorageService,
        vector_databaser_service: VectorDatabaserService
    ):
        self.object_storage_service = object_storage_service
        self.vector_databaser_service = vector_databaser_service

    async def process_text_memory(
        self, 
        user_id: str,
        text_content: str,
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process and store text memory"""
        # Store text in object storage
        file_path = self.object_storage_service.upload_text(text_content, filename)
        
        # Generate embedding
        embedding = await self.vector_databaser_service.generate_text(text_content)
        
        return {
            "user_id": user_id,
            "type": "text",
            "file_path": str(file_path),
            "embedding": embedding,
            "metadata": metadata or {}
        }

    async def process_photo_memory(
        self,
        user_id: str,
        photo_data: Union[bytes, BinaryIO, str, Path],
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process and store photo memory"""
        # Store photo in object storage
        file_path = self.object_storage_service.upload_photo(photo_data, filename)
        
        # Generate embedding
        embedding = await self.vector_databaser_service.generate_photos(str(file_path))
        
        return {
            "user_id": user_id,
            "type": "photo",
            "file_path": str(file_path),
            "embedding": embedding,
            "metadata": metadata or {}
        }
        
    async def process_video_memory(
        self,
        user_id: str,
        video_data: Union[bytes, BinaryIO, str, Path],
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process and store video memory"""
        # Store video in object storage
        file_path = self.object_storage_service.upload_video(video_data, filename)
        
        return {
            "user_id": user_id,
            "type": "video",
            "file_path": str(file_path),
            "embedding": None,  # Video embeddings might need special handling
            "metadata": metadata or {}
        }

    async def process_audio_memory(
        self,
        user_id: str,
        audio_data: Union[bytes, BinaryIO, str, Path],
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process and store audio memory"""
        # Store audio in object storage
        file_path = self.object_storage_service.upload_audio(audio_data, filename)
        
        return {
            "user_id": user_id,
            "type": "audio",
            "file_path": str(file_path),
            "embedding": None,  # Audio embeddings might need special handling
            "metadata": metadata or {}
        }

    async def process_batch_memories(
        self,
        user_id: str,
        text_contents: List[str],
        filenames: List[str],
        metadata_list: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Process multiple text memories in batch"""
        if len(text_contents) != len(filenames):
            raise ValueError("Number of text contents must match number of filenames")
        
        # Store all texts in object storage
        file_paths = []
        for text, filename in zip(text_contents, filenames):
            file_path = self.object_storage_service.upload_text(text, filename)
            file_paths.append(file_path)
        
        # Generate embeddings in batch
        embeddings = await self.vector_databaser_service.generate_batch(text_contents)
        
        # Prepare metadata
        if metadata_list is None:
            metadata_list = [{}] * len(text_contents)
        
        # Build results
        results = []
        for i, (file_path, embedding, metadata) in enumerate(
            zip(file_paths, embeddings, metadata_list)
        ):
            results.append({
                "user_id": user_id,
                "type": "text",
                "file_path": str(file_path),
                "embedding": embedding,
                "metadata": metadata
            })
        
        return results