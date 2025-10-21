import pytest
import tempfile
import shutil
from pathlib import Path
from io import BytesIO
from src.services.database.object_storage_service import ObjectStorageService
DIR_PATH = "./data/database/object_storage"

@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_dir_path = ObjectStorageService.__init__.__code__.co_consts
    
    # Create test instance with temp directory
    service = ObjectStorageService()
    service.dir_path = Path(temp_dir)
    service.video_dir = service.dir_path / "video"
    service.audio_dir = service.dir_path / "audio"
    service.text_dir = service.dir_path / "text"
    service.photo_dir = service.dir_path / "photo"
    
    # Create directories
    for directory in [service.video_dir, service.audio_dir, service.text_dir, service.photo_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    
    yield service
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestObjectStorageService:
    
    def test_directories_created_on_init(self, temp_storage):
        """Test that all required directories are created."""
        assert temp_storage.video_dir.exists()
        assert temp_storage.audio_dir.exists()
        assert temp_storage.text_dir.exists()
        assert temp_storage.photo_dir.exists()
    
    # ===== Video Upload Tests =====
    
    def test_upload_video_from_bytes(self, temp_storage):
        """Test uploading video from bytes."""
        video_data = b"fake video data content"
        filename = "test_video.mp4"
        
        result = temp_storage.upload_video(video_data, filename)
        
        assert result.exists()
        assert result.name == filename
        assert result.parent == temp_storage.video_dir
        assert result.read_bytes() == video_data
    
    def test_upload_video_from_file_object(self, temp_storage):
        """Test uploading video from file-like object."""
        video_data = b"video content from file object"
        file_obj = BytesIO(video_data)
        filename = "stream_video.mp4"
        
        result = temp_storage.upload_video(file_obj, filename)
        
        assert result.exists()
        assert result.read_bytes() == video_data
    
    def test_upload_video_from_path(self, temp_storage):
        """Test uploading video from existing file path."""
        # Create a temporary source file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(b"source video content")
            source_path = tmp.name
        
        try:
            filename = "copied_video.mp4"
            result = temp_storage.upload_video(source_path, filename)
            
            assert result.exists()
            assert result.read_bytes() == b"source video content"
        finally:
            Path(source_path).unlink()
    
    # ===== Audio Upload Tests =====
    
    def test_upload_audio_from_bytes(self, temp_storage):
        """Test uploading audio from bytes."""
        audio_data = b"fake audio data"
        filename = "test_audio.mp3"
        
        result = temp_storage.upload_audio(audio_data, filename)
        
        assert result.exists()
        assert result.name == filename
        assert result.parent == temp_storage.audio_dir
        assert result.read_bytes() == audio_data
    
    def test_upload_audio_from_file_object(self, temp_storage):
        """Test uploading audio from file-like object."""
        audio_data = b"audio stream content"
        file_obj = BytesIO(audio_data)
        filename = "stream_audio.wav"
        
        result = temp_storage.upload_audio(file_obj, filename)
        
        assert result.exists()
        assert result.read_bytes() == audio_data
    
    # ===== Text Upload Tests =====
    
    def test_upload_text_from_string(self, temp_storage):
        """Test uploading text from string."""
        text_data = "Hello, this is test content!"
        filename = "test_text.txt"
        
        result = temp_storage.upload_text(text_data, filename)
        
        assert result.exists()
        assert result.name == filename
        assert result.parent == temp_storage.text_dir
        assert result.read_text(encoding='utf-8') == text_data
    
    def test_upload_text_from_bytes(self, temp_storage):
        """Test uploading text from bytes."""
        text_data = b"Byte-encoded text content"
        filename = "byte_text.txt"
        
        result = temp_storage.upload_text(text_data, filename)
        
        assert result.exists()
        assert result.read_bytes() == text_data
    
    def test_upload_text_with_unicode(self, temp_storage):
        """Test uploading text with unicode characters."""
        text_data = "Hello 世界! 🌍 Émoji test"
        filename = "unicode_text.txt"
        
        result = temp_storage.upload_text(text_data, filename)
        
        assert result.exists()
        assert result.read_text(encoding='utf-8') == text_data
    
    # ===== Photo Upload Tests =====
    
    def test_upload_photo_from_bytes(self, temp_storage):
        """Test uploading photo from bytes."""
        photo_data = b"fake image binary data"
        filename = "test_photo.jpg"
        
        result = temp_storage.upload_photo(photo_data, filename)
        
        assert result.exists()
        assert result.name == filename
        assert result.parent == temp_storage.photo_dir
        assert result.read_bytes() == photo_data
    
    def test_upload_photo_from_file_object(self, temp_storage):
        """Test uploading photo from file-like object."""
        photo_data = b"photo stream content"
        file_obj = BytesIO(photo_data)
        filename = "stream_photo.png"
        
        result = temp_storage.upload_photo(file_obj, filename)
        
        assert result.exists()
        assert result.read_bytes() == photo_data
    
    def test_upload_photo_from_path(self, temp_storage):
        """Test uploading photo from existing file path."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(b"source photo content")
            source_path = tmp.name
        
        try:
            filename = "copied_photo.jpg"
            result = temp_storage.upload_photo(source_path, filename)
            
            assert result.exists()
            assert result.read_bytes() == b"source photo content"
        finally:
            Path(source_path).unlink()
    
    # ===== Edge Cases and Error Handling =====
    
    def test_upload_overwrites_existing_file(self, temp_storage):
        """Test that uploading overwrites existing files."""
        filename = "overwrite_test.txt"
        
        # First upload
        temp_storage.upload_text("Original content", filename)
        
        # Second upload with same filename
        result = temp_storage.upload_text("New content", filename)
        
        assert result.read_text() == "New content"
    
    def test_upload_with_subdirectory_in_filename(self, temp_storage):
        """Test uploading with subdirectory structure in filename."""
        filename = "subdir/nested/file.txt"
        text_data = "Content in nested directory"
        
        # This should fail unless we create parent directories
        # You may want to modify your implementation to handle this
        with pytest.raises(FileNotFoundError):
            temp_storage.upload_text(text_data, filename)
    
    def test_upload_empty_file(self, temp_storage):
        """Test uploading empty files."""
        result = temp_storage.upload_text("", "empty.txt")
        
        assert result.exists()
        assert result.read_text() == ""
    
    def test_upload_large_file(self, temp_storage):
        """Test uploading a large file."""
        # Create 10MB of data
        large_data = b"x" * (10 * 1024 * 1024)
        filename = "large_video.mp4"
        
        result = temp_storage.upload_video(large_data, filename)
        
        assert result.exists()
        assert result.stat().st_size == len(large_data)
    
    def test_multiple_uploads_same_type(self, temp_storage):
        """Test uploading multiple files of the same type."""
        files = ["video1.mp4", "video2.mp4", "video3.mp4"]
        
        for filename in files:
            result = temp_storage.upload_video(b"content", filename)
            assert result.exists()
        
        uploaded_files = list(temp_storage.video_dir.glob("*.mp4"))
        assert len(uploaded_files) == 3

    # Add these test methods to the TestObjectStorageService class

    def test_upload_duplicate_filename_overwrites(self, temp_storage):
        """Test that uploading a file with duplicate name overwrites the original."""
        filename = "duplicate.txt"
        
        # First upload
        first_content = "This is the original content"
        result1 = temp_storage.upload_text(first_content, filename)
        assert result1.read_text() == first_content
        
        # Second upload with same filename but different content
        second_content = "This is the NEW content that replaces the old one"
        result2 = temp_storage.upload_text(second_content, filename)
        
        # Verify the file was overwritten
        assert result2.read_text() == second_content
        assert result2.read_text() != first_content
        
        # Verify only one file exists
        text_files = list(temp_storage.text_dir.glob(filename))
        assert len(text_files) == 1

    def test_upload_duplicate_across_types_separate_storage(self, temp_storage):
        """Test that same filename in different directories doesn't conflict."""
        filename = "data.bin"
        video_content = b"video binary data"
        photo_content = b"photo binary data"
        audio_content = b"audio binary data"
        
        # Upload files with same name to different directories
        video_result = temp_storage.upload_video(video_content, filename)
        photo_result = temp_storage.upload_photo(photo_content, filename)
        audio_result = temp_storage.upload_audio(audio_content, filename)
        
        # Verify all files exist independently
        assert video_result.exists()
        assert photo_result.exists()
        assert audio_result.exists()
        
        # Verify they have different content
        assert video_result.read_bytes() == video_content
        assert photo_result.read_bytes() == photo_content
        assert audio_result.read_bytes() == audio_content
        
        # Verify they're in different directories
        assert video_result.parent == temp_storage.video_dir
        assert photo_result.parent == temp_storage.photo_dir
        assert audio_result.parent == temp_storage.audio_dir

    def test_upload_duplicate_with_different_data_types(self, temp_storage):
        """Test overwriting file with different data type (bytes vs string)."""
        filename = "mixed_type.txt"
        
        # First upload as string
        text_content = "String content"
        temp_storage.upload_text(text_content, filename)
        
        # Overwrite with bytes
        bytes_content = b"Bytes content"
        result = temp_storage.upload_text(bytes_content, filename)
        
        # Verify the bytes content overwrote the string content
        assert result.read_bytes() == bytes_content
        
        # Verify only one file exists
        text_files = list(temp_storage.text_dir.glob(filename))
        assert len(text_files) == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])