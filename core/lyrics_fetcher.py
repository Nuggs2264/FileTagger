import os
import re
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple
import requests

LRCLIB_GET_URL = "https://lrclib.net/api/get"
USER_AGENT = "FileTagger/1.0 (https://github.com/desktop-tagger/filetagger)"

@dataclass
class LyricsResult:
    track_name: str
    artist_name: str
    album_name: str
    duration: float
    synced_lyrics: str
    plain_lyrics: str
    is_synced: bool

def clean_title_for_search(title: str) -> str:
    """Removes common track title clutter like (feat. X), [Remastered], etc."""
    cleaned = title
    # Remove featuring
    cleaned = re.sub(r"\s*[\(\[](?:feat|featuring|ft)\.?\s+[^\)\]]+[\)\]]", "", cleaned, flags=re.IGNORECASE)
    # Remove Remastered / Deluxe / Official Video / etc.
    cleaned = re.sub(r"\s*[\(\[](?:remastered|deluxe|bonus|official video|version|edit|mono|stereo)[^\)\]]*[\)\]]", "", cleaned, flags=re.IGNORECASE)
    # Remove trailing track numbers or dashes
    cleaned = re.sub(r"^\d+\s*[-.]?\s*", "", cleaned)
    return cleaned.strip()

def fetch_lyrics(
    track_name: str,
    artist_name: str = "",
    album_name: str = "",
    duration: float = 0.0,
    timeout: int = 8
) -> Optional[LyricsResult]:
    """
    Fetches synchronized / plain lyrics from LRCLIB.
    Attempts query with full parameters first; if not found, cleans up parameters and retries.
    """
    if not track_name:
        return None

    headers = {"User-Agent": USER_AGENT}

    # Attempt 1: Full parameters
    params = {"track_name": track_name}
    if artist_name:
        params["artist_name"] = artist_name
    if album_name:
        params["album_name"] = album_name
    if duration > 0:
        params["duration"] = int(duration)

    try:
        r = requests.get(LRCLIB_GET_URL, params=params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return _parse_lrclib_response(r.json())
    except Exception:
        pass

    # Attempt 2: Relax parameters (remove album and duration, clean title)
    cleaned_title = clean_title_for_search(track_name)
    relaxed_params = {"track_name": cleaned_title}
    if artist_name:
        relaxed_params["artist_name"] = artist_name

    try:
        r = requests.get(LRCLIB_GET_URL, params=relaxed_params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return _parse_lrclib_response(r.json())
    except Exception:
        pass

    # Attempt 3: If artist was empty or composite (e.g. "Artist1, Artist2" or "Artist - Title")
    if not artist_name and " - " in track_name:
        parts = track_name.split(" - ", 1)
        r_params = {"artist_name": parts[0].strip(), "track_name": clean_title_for_search(parts[1])}
        try:
            r = requests.get(LRCLIB_GET_URL, params=r_params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return _parse_lrclib_response(r.json())
        except Exception:
            pass

    return None

def _parse_lrclib_response(data: dict) -> Optional[LyricsResult]:
    synced = data.get("syncedLyrics") or ""
    plain = data.get("plainLyrics") or ""
    if not synced and not plain:
        return None

    return LyricsResult(
        track_name=data.get("trackName") or "",
        artist_name=data.get("artistName") or "",
        album_name=data.get("albumName") or "",
        duration=float(data.get("duration") or 0.0),
        synced_lyrics=synced,
        plain_lyrics=plain,
        is_synced=bool(synced)
    )

def save_lrc_file(audio_file_path: str, lyrics_content: str) -> str:
    """
    Saves synchronized lyrics alongside the audio file as a standard .lrc file.
    Example: 'C:/Music/Track.mp3' -> 'C:/Music/Track.lrc'
    Returns the path of the saved .lrc file.
    """
    abs_audio = os.path.abspath(audio_file_path)
    if os.path.islink(abs_audio):
        raise ValueError("Refusing to write lyrics next to a symbolic link.")
    base_path, _ = os.path.splitext(abs_audio)
    lrc_path = f"{base_path}.lrc"
    parent_dir = os.path.dirname(lrc_path)

    fd, tmp_path = tempfile.mkstemp(prefix=".lrc_tmp_", suffix=".lrc", dir=parent_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(lyrics_content)
        os.replace(tmp_path, lrc_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    return lrc_path
