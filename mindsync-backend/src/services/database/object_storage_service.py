from pathlib import Path
from typing import Union, BinaryIO
import shutil

DIR_PATH = "./data/database/object_storage"

class ObjectStorageService:
    def __init__(self, path: str = DIR_PATH):
        self.dir_path = Path(path)
        self.video_dir = self.dir_path / "video"
        self.audio_dir = self.dir_path / "audio"
        self.text_dir = self.dir_path / "text"
        self.photo_dir = self.dir_path / "photo"
        
        for directory in [self.video_dir, self.audio_dir, self.text_dir, self.photo_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def upload_video(self, video_data: Union[bytes, BinaryIO, str, Path], filename: str) -> Path:
        return self._save_file(video_data, self.video_dir / filename)
    
    def upload_audio(self, audio_data: Union[bytes, BinaryIO, str, Path], filename: str) -> Path:
        return self._save_file(audio_data, self.audio_dir / filename)
    
    def upload_text(self, text_data: Union[str, bytes], filename: str) -> Path:
        target_path = self.text_dir / filename
        if isinstance(text_data, str):
            target_path.write_text(text_data, encoding='utf-8')
        else:
            target_path.write_bytes(text_data)
        return target_path
    
    def upload_photo(self, photo_data: Union[bytes, BinaryIO, str, Path], filename: str) -> Path:
        return self._save_file(photo_data, self.photo_dir / filename)
    
    def _save_file(self, data: Union[bytes, BinaryIO, str, Path], target_path: Path) -> Path:
        if isinstance(data, bytes):
            target_path.write_bytes(data)
        elif isinstance(data, (str, Path)):
            shutil.copy2(data, target_path)
        else:
            with open(target_path, 'wb') as f:
                shutil.copyfileobj(data, f)
        return target_path

# Example usage:
if __name__ == "__main__":
    service = ObjectStorageService("mindsync-backend/data/database/object_storage")
    text_path = service.upload_text("sample.txt", "sample.txt")
    print(f"Text file saved at: {text_path}")
    photo_path = service.upload_photo("mindsync-backend/data/database/object_storage/photo/6-Reasons-To-Explore-Amusement-Parks.webp", "copied_photo.webp")
    print(f"Photo file saved at: {photo_path}")