import os
import re
import io
import json
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class SearchResult:
    id: str
    title: str
    year: str = ""
    media_type: str = "Movie"
    director: str = ""
    cast: str = ""
    genres: List[str] = field(default_factory=list)
    overview: str = ""
    poster_url: str = ""
    source: str = "IMDb"

def clean_search_query(name: str) -> str:
    """Strips file extensions, resolution tags, scene junk, and dots/underscores."""
    # Strip extension
    name = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', name)
    # Strip bracketed tags e.g. [1080p] or (2024)
    name = re.sub(r'\[.*?\]', ' ', name)
    # Replace dots and underscores
    name = re.sub(r'[._]', ' ', name)
    # Strip resolution, quality, codec tags and anything following
    name = re.sub(r'(?i)\b(1080p|720p|2160p|4k|uhd|bluray|web-?dl|webrip|hdtv|x264|x265|hevc|aac|dts|remux)\b.*$', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def search_imdb(query: str) -> List[SearchResult]:
    """
    Queries IMDb's open suggestion service.
    Returns high-res poster URLs, title, year, cast, and media type with zero API key required.
    """
    clean_q = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip().lower()
    if not clean_q:
        return []

    first_char = clean_q[0]
    encoded_q = urllib.parse.quote(clean_q.replace(' ', '_'))
    url = f"https://v3.sg.media-imdb.com/suggestion/{first_char}/{encoded_q}.json"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    
    results: List[SearchResult] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            items = data.get("d", [])
            for item in items:
                # Filter out person results (actors/directors)
                item_id = str(item.get("id", ""))
                if not item_id.startswith("tt"):
                    continue

                title = str(item.get("l", "")).strip()
                year = str(item.get("y", "")).strip()
                q_type = str(item.get("q", "feature")).capitalize()
                cast = str(item.get("s", "")).strip()
                
                # Poster URL
                poster_url = ""
                img_data = item.get("i")
                if isinstance(img_data, dict):
                    poster_url = str(img_data.get("imageUrl", ""))
                    # Convert thumbnail URL to high-res if possible by stripping resizing params
                    if "._V1_" in poster_url:
                        poster_url = re.sub(r'\._V1_.*?\.', '._V1_.', poster_url)

                res = SearchResult(
                    id=item_id,
                    title=title,
                    year=year,
                    media_type="Movie" if "feature" in q_type.lower() else q_type,
                    cast=cast,
                    poster_url=poster_url,
                    source="IMDb"
                )
                results.append(res)
    except Exception as e:
        print(f"IMDb search error: {e}")

    return results

def search_tvmaze(query: str) -> List[SearchResult]:
    """
    Queries TVMaze API for TV Shows (title, premiered year, genres, plot summary, and original poster art).
    Completely free and open.
    """
    encoded_q = urllib.parse.quote(query.strip())
    url = f"https://api.tvmaze.com/search/shows?q={encoded_q}"
    headers = {"User-Agent": "FileTagger/1.0"}
    req = urllib.request.Request(url, headers=headers)
    
    results: List[SearchResult] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            for item in data:
                show = item.get("show", {})
                title = str(show.get("name", "")).strip()
                premiered = str(show.get("premiered", ""))
                year = premiered[:4] if premiered else ""
                genres = show.get("genres", [])
                
                summary = str(show.get("summary", ""))
                # Strip HTML tags
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                
                poster_url = ""
                img_dict = show.get("image")
                if isinstance(img_dict, dict):
                    poster_url = img_dict.get("original") or img_dict.get("medium", "")

                res = SearchResult(
                    id=f"tvm_{show.get('id')}",
                    title=title,
                    year=year,
                    media_type="TV Series",
                    genres=genres,
                    overview=summary,
                    poster_url=poster_url,
                    source="TVMaze"
                )
                results.append(res)
    except Exception as e:
        print(f"TVMaze search error: {e}")

    return results

def search_tmdb(query: str, api_key: str) -> List[SearchResult]:
    """
    Queries The Movie Database (TMDb) v3 API if an API key is provided.
    """
    if not api_key:
        return []

    encoded_q = urllib.parse.quote(query.strip())
    url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key.strip()}&query={encoded_q}&include_adult=false"
    headers = {"User-Agent": "FileTagger/1.0"}
    req = urllib.request.Request(url, headers=headers)

    results: List[SearchResult] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            for item in data.get("results", []):
                media_type = item.get("media_type", "movie")
                if media_type not in ("movie", "tv"):
                    continue

                title = item.get("title") or item.get("name") or ""
                date = item.get("release_date") or item.get("first_air_date") or ""
                year = date[:4] if date else ""
                overview = item.get("overview", "")
                poster_path = item.get("poster_path", "")
                # w780 provides high definition artwork with fast download speeds
                poster_url = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

                res = SearchResult(
                    id=f"tmdb_{item.get('id')}",
                    title=title,
                    year=year,
                    media_type="Movie" if media_type == "movie" else "TV Series",
                    overview=overview,
                    poster_url=poster_url,
                    source="TMDb"
                )
                results.append(res)
    except urllib.error.HTTPError as he:
        if he.code == 401:
            raise RuntimeError("Invalid TMDb API Key (401 Unauthorized). Please check your key in the settings.")
        elif he.code == 429:
            retry_after = he.headers.get("Retry-After", "") if hasattr(he, "headers") else ""
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"TMDb rate limit exceeded (429 Too Many Requests){hint}. Please wait a moment.")
        elif he.code == 503:
            raise RuntimeError("TMDb service temporarily unavailable (503). Please try again shortly.")
        raise RuntimeError(f"TMDb HTTP error {he.code}: {he.reason}")
    except Exception as e:
        clean_key = api_key.strip()
        safe_err = str(e).replace(clean_key, "[REDACTED]") if clean_key else str(e)
        print(f"TMDb search error: {safe_err}")
        raise RuntimeError(f"TMDb search failed: {safe_err}")

    return results

def fetch_wikipedia_plot_and_director(title: str) -> Dict[str, str]:
    """
    Fetches plot synopsis and details from Wikipedia REST summary API.
    """
    info = {"overview": "", "director": ""}
    try:
        encoded = urllib.parse.quote(title.strip())
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "FileTagger/1.0 (media tagger tool)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            extract = data.get("extract", "")
            if extract and not data.get("type") == "disambiguation":
                info["overview"] = extract
                # Try to extract director e.g. "directed by Hayao Miyazaki"
                m = re.search(r'directed by ([A-Z][a-z]+ [A-Z][a-z]+)', extract)
                if m:
                    info["director"] = m.group(1)
    except Exception:
        pass
    return info

MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB hard cap

def download_image_bytes(image_url: str) -> Optional[bytes]:
    """Downloads poster image data over HTTP/HTTPS with proper timeout and headers."""
    if not image_url:
        return None
    try:
        parsed = urllib.parse.urlparse(image_url.strip())
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            print(f"Rejected unsafe image URL scheme: {image_url}")
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(image_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            chunks = []
            total = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds maximum allowed size (15 MB)")
                chunks.append(chunk)
            return b"".join(chunks)
    except Exception as e:
        print(f"Error downloading image from {image_url}: {e}")
        return None

