import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

STANDARD_TAG_KEYS = [
    "title",
    "artist",
    "album",
    "album_artist",
    "year",
    "track_number",
    "disc_number",
    "genre",
    "comment",
    "composer"
]

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".ts"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

@dataclass
class MediaItem:
    file_path: str
    tags: Dict[str, str] = field(default_factory=dict)
    original_tags: Dict[str, str] = field(default_factory=dict)
    
    extra_tags: Dict[str, str] = field(default_factory=dict)
    original_extra_tags: Dict[str, str] = field(default_factory=dict)

    technical_info: Dict[str, str] = field(default_factory=dict)
    
    cover_bytes: Optional[bytes] = None
    cover_mime: Optional[str] = None
    original_cover_bytes: Optional[bytes] = None
    original_cover_mime: Optional[str] = None
    cover_modified: bool = False
    
    duration: float = 0.0
    resolution: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None

    def __post_init__(self):
        if not self.tags:
            self.tags = {k: "" for k in STANDARD_TAG_KEYS}
        else:
            for k in STANDARD_TAG_KEYS:
                if k not in self.tags:
                    self.tags[k] = ""
        self.original_tags = dict(self.tags)
        self.original_extra_tags = dict(self.extra_tags)
        self.original_cover_bytes = self.cover_bytes
        self.original_cover_mime = self.cover_mime

        try:
            self.file_size = os.path.getsize(self.file_path)
        except Exception:
            self.file_size = 0

    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path)

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file_path)[1].lower()

    @property
    def is_video(self) -> bool:
        return self.extension in VIDEO_EXTENSIONS

    @property
    def is_audio(self) -> bool:
        return self.extension in AUDIO_EXTENSIONS

    @property
    def is_dirty(self) -> bool:
        if self.cover_modified:
            return True
        for k in STANDARD_TAG_KEYS:
            if self.tags.get(k, "") != self.original_tags.get(k, ""):
                return True
        if self.extra_tags != self.original_extra_tags:
            return True
        return False

    def mark_dirty(self):
        """Explicitly tracks dirty state (is_dirty also computes differences automatically)."""
        pass

    def mark_saved(self):
        self.original_tags = dict(self.tags)
        self.original_extra_tags = dict(self.extra_tags)
        self.original_cover_bytes = self.cover_bytes
        self.original_cover_mime = self.cover_mime
        self.cover_modified = False

    def revert(self):
        self.tags = dict(self.original_tags)
        self.extra_tags = dict(self.original_extra_tags)
        self.cover_bytes = self.original_cover_bytes
        self.cover_mime = self.original_cover_mime
        self.cover_modified = False

    def set_cover(self, data: Optional[bytes], mime_type: Optional[str] = "image/jpeg"):
        self.cover_bytes = data
        self.cover_mime = mime_type if data else None
        self.cover_modified = True

    def get_all_tags(self) -> Dict[str, str]:
        """Returns unified dictionary of all tags (standard + extended)."""
        combined = dict(self.extra_tags)
        for k in STANDARD_TAG_KEYS:
            val = self.tags.get(k, "")
            if val:
                combined[k] = val
        return combined

    def formatted_duration(self) -> str:
        if self.duration <= 0:
            return "--:--"
        total_sec = int(self.duration)
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def formatted_size(self) -> str:
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
