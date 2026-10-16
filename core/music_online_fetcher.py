import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import requests

USER_AGENT = "FileTagger/1.0 (https://github.com/desktop-tagger/filetagger)"

@dataclass
class MusicSearchResult:
    source: str
    artist: str
    album: str
    year: str
    genre: str
    cover_url: str
    track_count: int = 0
    tracks: List[str] = field(default_factory=list)
    release_id: str = ""

def clean_query_text(query: str) -> str:
    """Strips file extensions, track numbers, and noise from search string."""
    q = os.path.splitext(query)[0]
    # Remove leading track numbers like "01 - " or "1. "
    q = re.sub(r"^\d+\s*[-.]\s*", "", q)
    # Remove clutter like [FLAC], [320kbps], (Official Video)
    q = re.sub(r"[\(\[](?:flac|mp3|320|vbr|official video|audio|remastered|deluxe)[\)\]]", "", q, flags=re.IGNORECASE)
    # Replace underscores with spaces
    q = q.replace("_", " ")
    return q.strip()

def search_itunes(query: str, limit: int = 15) -> List[MusicSearchResult]:
    """
    Searches Apple Music / iTunes Store for albums.
    Completely open and returns high-resolution 1400x1400 artwork.
    """
    url = "https://itunes.apple.com/search"
    params = {
        "term": clean_query_text(query),
        "entity": "album",
        "limit": limit
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After", "")
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"iTunes / Apple Music rate limit reached (429){hint}. Please wait a moment.")
        r.raise_for_status()
        data = r.json()
    except RuntimeError:
        raise
    except Exception:
        return []

    results: List[MusicSearchResult] = []
    for item in data.get("results", []):
        art_100 = item.get("artworkUrl100", "")
        # Upgrade artwork URL to high-resolution (1400x1400)
        art_hi = art_100.replace("100x100bb", "1400x1400bb") if art_100 else ""

        year = ""
        rel_date = item.get("releaseDate", "")
        if rel_date and len(rel_date) >= 4:
            year = rel_date[:4]

        results.append(MusicSearchResult(
            source="iTunes",
            artist=item.get("artistName", ""),
            album=item.get("collectionName", ""),
            year=year,
            genre=item.get("primaryGenreName", ""),
            cover_url=art_hi,
            track_count=int(item.get("trackCount", 0)),
            release_id=str(item.get("collectionId", ""))
        ))
    return results

def search_deezer(query: str, limit: int = 15) -> List[MusicSearchResult]:
    """
    Searches Deezer for albums.
    Returns 1000x1000 album covers ('cover_xl').
    """
    url = "https://api.deezer.com/search/album"
    params = {
        "q": clean_query_text(query),
        "limit": limit
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After", "")
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"Deezer rate limit reached (429){hint}. Please wait a moment.")
        r.raise_for_status()
        data = r.json()
    except RuntimeError:
        raise
    except Exception:
        return []

    results: List[MusicSearchResult] = []
    for item in data.get("data", []):
        artist_obj = item.get("artist", {})
        artist_name = artist_obj.get("name", "") if isinstance(artist_obj, dict) else ""
        cover_xl = item.get("cover_xl") or item.get("cover_big") or item.get("cover_medium") or ""

        results.append(MusicSearchResult(
            source="Deezer",
            artist=artist_name,
            album=item.get("title", ""),
            year="",
            genre="",
            cover_url=cover_xl,
            track_count=int(item.get("nb_tracks", 0)),
            release_id=str(item.get("id", ""))
        ))
    return results

def search_musicbrainz_coverart(query: str, limit: int = 15) -> List[MusicSearchResult]:
    """
    Searches MusicBrainz releases and checks Cover Art Archive (CAA).
    """
    clean_q = clean_query_text(query).replace("'", "").replace('"', "")
    url = "https://musicbrainz.org/ws/2/release"
    params = {
        "query": clean_q,
        "fmt": "json",
        "limit": limit
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code in (429, 503):
            retry_after = r.headers.get("Retry-After", "")
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"MusicBrainz rate limit reached ({r.status_code}){hint}. Please wait a moment.")
        r.raise_for_status()
        data = r.json()
    except RuntimeError:
        raise
    except Exception:
        return []

    results: List[MusicSearchResult] = []
    for rel in data.get("releases", []):
        rel_id = rel.get("id", "")
        title = rel.get("title", "")
        
        artists = rel.get("artist-credit", [])
        artist_name = ""
        if artists:
            artist_name = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name"))

        date_str = rel.get("date", "")
        year = date_str[:4] if date_str and len(date_str) >= 4 else ""

        # Cover Art Archive direct image URL
        cover_url = f"https://coverartarchive.org/release/{rel_id}/front-500"

        track_count = 0
        media = rel.get("media", [])
        if media:
            track_count = sum(m.get("track-count", 0) for m in media if isinstance(m, dict))

        results.append(MusicSearchResult(
            source="MusicBrainz",
            artist=artist_name,
            album=title,
            year=year,
            genre="",
            cover_url=cover_url,
            track_count=track_count,
            release_id=rel_id
        ))
    return results

def search_discogs(query: str, token: str = "", limit: int = 15) -> List[MusicSearchResult]:
    """
    Searches Discogs database for releases.
    If user provides an optional Discogs personal token in Settings, high-res cover images are returned.
    """
    url = "https://api.discogs.com/database/search"
    params = {
        "q": clean_query_text(query),
        "type": "release",
        "per_page": limit
    }
    headers = {"User-Agent": USER_AGENT}
    if token and token.strip():
        headers["Authorization"] = f"Discogs token={token.strip()}"

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After", "")
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"Discogs rate limit reached (429){hint}. Please wait a moment.")
        r.raise_for_status()
        data = r.json()
    except RuntimeError:
        raise
    except Exception:
        return []

    results: List[MusicSearchResult] = []
    for item in data.get("results", []):
        raw_title = item.get("title", "")
        artist = ""
        album = raw_title
        if " - " in raw_title:
            parts = raw_title.split(" - ", 1)
            artist = parts[0].strip()
            album = parts[1].strip()

        genres = item.get("genre", [])
        genre_str = ", ".join(genres) if isinstance(genres, list) else str(genres)

        cover_img = item.get("cover_image", "")
        # Discogs spacer gif placeholder check
        if "spacer.gif" in cover_img:
            cover_img = ""

        results.append(MusicSearchResult(
            source="Discogs",
            artist=artist,
            album=album,
            year=str(item.get("year", "")),
            genre=genre_str,
            cover_url=cover_img,
            track_count=0,
            release_id=str(item.get("id", ""))
        ))
    return results

def search_all_music_sources(query: str, discogs_token: str = "") -> List[MusicSearchResult]:
    """
    Searches iTunes, Deezer, and MusicBrainz in parallel or unified order.
    """
    all_results: List[MusicSearchResult] = []
    
    # 1. iTunes (highest quality artwork and metadata)
    try:
        itunes_res = search_itunes(query, limit=10)
        all_results.extend(itunes_res)
    except Exception:
        pass

    # 2. Deezer
    try:
        deezer_res = search_deezer(query, limit=10)
        all_results.extend(deezer_res)
    except Exception:
        pass

    # 3. MusicBrainz
    try:
        mb_res = search_musicbrainz_coverart(query, limit=8)
        all_results.extend(mb_res)
    except Exception:
        pass

    # 4. Discogs (if token provided or desired)
    if discogs_token:
        try:
            discogs_res = search_discogs(query, token=discogs_token, limit=8)
            all_results.extend(discogs_res)
        except Exception:
            pass

    return all_results

MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB hard cap

def download_music_image_bytes(url: str, timeout: int = 12) -> Optional[bytes]:
    """Downloads image data from URL."""
    if not url:
        return None
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        return None
    headers = {"User-Agent": USER_AGENT}
    try:
        with requests.get(url, headers=headers, timeout=timeout, stream=True) as r:
            if r.status_code != 200:
                return None
            chunks = []
            total = 0
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        return None
                    chunks.append(chunk)
            content = b"".join(chunks)
            return content if len(content) > 500 else None
    except Exception:
        pass
    return None

