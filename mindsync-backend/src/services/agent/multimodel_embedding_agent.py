"""
Multimodal Embedding Model - Handles encoding for text, photos, audio, and video
"""

from sentence_transformers import SentenceTransformer
from typing import List, Union
import torch
from pathlib import Path
from PIL import Image
import numpy as np


class MultimodalEmbeddingAgent:
    """
    Wrapper around SentenceTransformer to provide unified interface for
    encoding different modalities (text, image, audio, video)
    """
    
    def __init__(self, model_name: str = "clip-ViT-B-32"):
        """
        Initialize the multimodal embedding model
        
        Args:
            model_name: Name of the sentence-transformers model
                       For multimodal: 'clip-ViT-B-32', 'clip-ViT-L-14'
        """
        self.model = SentenceTransformer(model_name)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
    
    def encode_text(self, text: str, convert_to_tensor: bool = False) -> Union[np.ndarray, torch.Tensor]:
        """
        Encode text into embedding vector
        
        Args:
            text: Input text string
            convert_to_tensor: Whether to return torch.Tensor instead of numpy array
            
        Returns:
            Embedding vector
        """
        embedding = self.model.encode(
            text,
            convert_to_tensor=convert_to_tensor,
            show_progress_bar=False
        )
        return embedding
    
    def encode_photo(self, photo_path: str, convert_to_tensor: bool = False) -> Union[np.ndarray, torch.Tensor]:
        """
        Encode photo/image into embedding vector
        
        Args:
            photo_path: Path to image file
            convert_to_tensor: Whether to return torch.Tensor instead of numpy array
            
        Returns:
            Embedding vector
        """
        # Load image
        image = Image.open(photo_path).convert("RGB")
        
        # Encode using CLIP's image encoder
        embedding = self.model.encode(
            image,
            convert_to_tensor=convert_to_tensor,
            show_progress_bar=False
        )
        return embedding
    
    def encode_audio(self, audio_path: str, convert_to_tensor: bool = False) -> Union[np.ndarray, torch.Tensor]:
        """
        Encode audio into embedding vector
        
        Args:
            audio_path: Path to audio file
            convert_to_tensor: Whether to return torch.Tensor instead of numpy array
            
        Returns:
            Embedding vector
        """
        # For audio, you might want to:
        # 1. Use a specialized audio model like CLAP (Contrastive Language-Audio Pretraining)
        # 2. Extract audio features using librosa and project to embedding space
        # 3. Use speech-to-text then encode the text
        
        # Option 3 (simplest): Convert audio to text using speech recognition
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
            
            # Encode the transcribed text
            embedding = self.encode_text(text, convert_to_tensor=convert_to_tensor)
            return embedding
            
        except Exception as e:
            # Fallback: return zero vector with same dimensionality
            embedding_dim = self.model.get_sentence_embedding_dimension()
            if convert_to_tensor:
                return torch.zeros(embedding_dim, device=self.device)
            return np.zeros(embedding_dim)
    
    def encode_video(self, video_path: str, convert_to_tensor: bool = False) -> Union[np.ndarray, torch.Tensor]:
        """
        Encode video into embedding vector
        
        Args:
            video_path: Path to video file
            convert_to_tensor: Whether to return torch.Tensor instead of numpy array
            
        Returns:
            Embedding vector (averaged over sampled frames)
        """
        # For video, common approaches:
        # 1. Sample frames and average their embeddings
        # 2. Use video-specific models like VideoCLIP
        # 3. Extract keyframes and encode them
        
        # Option 1 (simplest): Sample frames and average embeddings
        try:
            import cv2
            
            cap = cv2.VideoCapture(video_path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Sample 10 frames evenly distributed throughout video
            num_samples = min(10, frame_count)
            sample_indices = np.linspace(0, frame_count - 1, num_samples, dtype=int)
            
            embeddings = []
            for idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(frame_rgb)
                    
                    # Encode frame
                    embedding = self.model.encode(
                        image,
                        convert_to_tensor=True,
                        show_progress_bar=False
                    )
                    embeddings.append(embedding)
            
            cap.release()
            
            if embeddings:
                # Average embeddings across all frames
                avg_embedding = torch.stack(embeddings).mean(dim=0)
                
                if not convert_to_tensor:
                    avg_embedding = avg_embedding.cpu().numpy()
                
                return avg_embedding
            else:
                raise Exception("No frames extracted from video")
                
        except Exception as e:
            # Fallback: return zero vector with same dimensionality
            embedding_dim = self.model.get_sentence_embedding_dimension()
            if convert_to_tensor:
                return torch.zeros(embedding_dim, device=self.device)
            return np.zeros(embedding_dim)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimensionality of the embedding vectors"""
        return self.model.get_sentence_embedding_dimension()
    
# Example usage:
if __name__ == "__main__":
    model = MultimodalEmbeddingAgent("clip-ViT-B-32")
    text_emb = model.encode_text("Hello, world!", convert_to_tensor=False)
    print("Text Embedding:", text_emb)
    photo_emb = model.encode_photo("./mindsync-backend/data/database/object_storage/photo/6-Reasons-To-Explore-Amusement-Parks.webp", convert_to_tensor=False)
    print("Photo Embedding:", photo_emb)
    # It works!!!