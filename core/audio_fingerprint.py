import os
import re
import sys
import hashlib
import tempfile
import json
import shutil
import urllib.request
import zipfile
import io
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

ACOUSTID_DEFAULT_CLIENT = "1vOwZtEn"
FPCALC_DOWNLOAD_URL = "https://github.com/acoustid/chromaprint/releases/download/v1.6.1/chromaprint-fpcalc-1.6.1-windows-x86_64.zip"
FPCALC_EXPECTED_SHA256 = "00dcc56d911f2dea84737aa9dc8e2d118c9eb7a037d815d1ed001d8593e8fbee"

@dataclass
class AudioFingerprintMatch:
    score: float
    title: str
    artist: str
    album: str
    year: str
    track_number: str
    genre: str
    recording_id: str
    fingerprint: str = ""

def get_fpcalc_path() -> Optional[str]:
    """
    Locates or automatically provisions the portable fpcalc.exe binary.
    Checks:
    1. Local bin/fpcalc.exe
    2. System PATH
    3. Auto-downloads AcoustID's official precompiled Windows binary into bin/ (verified via SHA-256)
    """
    # 1. Local bin directory
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_bin = os.path.join(app_dir, "bin", "fpcalc.exe" if os.name == "nt" else "fpcalc")
    if os.path.isfile(local_bin):
        return local_bin

    # 2. System PATH
    sys_path = shutil.which("fpcalc")
    if sys_path:
        return sys_path

    # 3. Auto-download on Windows if missing
    if os.name == "nt":
        try:
            bin_dir = os.path.join(app_dir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            req = urllib.request.Request(
                FPCALC_DOWNLOAD_URL,
                headers={"User-Agent": "FileTagger/1.0 (Portable Downloader)"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read(10 * 1024 * 1024)  # Cap at 10 MB
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for name in z.namelist():
                        if name.endswith("fpcalc.exe"):
                            exe_bytes = z.read(name)
                            digest = hashlib.sha256(exe_bytes).hexdigest().lower()
                            if FPCALC_EXPECTED_SHA256 and digest != FPCALC_EXPECTED_SHA256.lower():
                                raise RuntimeError(f"fpcalc.exe SHA-256 mismatch: {digest}")
                            fd, tmp_path = tempfile.mkstemp(dir=bin_dir, suffix=".tmp")
                            try:
                                with os.fdopen(fd, "wb") as f:
                                    f.write(exe_bytes)
                                os.replace(tmp_path, local_bin)
                            finally:
                                if os.path.exists(tmp_path):
                                    try:
                                        os.remove(tmp_path)
                                    except Exception:
                                        pass
                            return local_bin
        except Exception:
            pass

    return None

def compute_chromaprint(file_path: str) -> Tuple[float, str]:
    """
    Computes (duration_seconds, fingerprint_str) using fpcalc.
    Raises RuntimeError if fpcalc fails.
    """
    fpcalc_exe = get_fpcalc_path()
    if not fpcalc_exe:
        raise RuntimeError("Chromaprint 'fpcalc' tool could not be found or downloaded.")

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = [fpcalc_exe, "-json", file_path]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        startupinfo=startupinfo,
        timeout=30
    )

    if proc.returncode != 0:
        raise RuntimeError(f"fpcalc failed: {proc.stderr.strip() or 'Unknown error'}")

    try:
        data = json.loads(proc.stdout)
        duration = float(data.get("duration", 0.0))
        fingerprint = str(data.get("fingerprint", ""))
        return duration, fingerprint
    except Exception as e:
        raise RuntimeError(f"Failed to parse fpcalc output: {e}")

def lookup_acoustid(
    duration: float,
    fingerprint: str,
    client_key: str = ACOUSTID_DEFAULT_CLIENT
) -> List[AudioFingerprintMatch]:
    """
    Queries AcoustID API with audio fingerprint and duration.
    Returns list of AudioFingerprintMatch candidates sorted by score descending.
    """
    import requests

    url = "https://api.acoustid.org/v2/lookup"
    params = {
        "client": client_key,
        "meta": "recordings+releasegroups+releases+tracks+usermeta",
        "duration": int(duration),
        "fingerprint": fingerprint
    }
    headers = {
        "User-Agent": "FileTagger/1.0 (https://github.com/desktop-tagger/filetagger)"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "")
            hint = f" (retry after {retry_after}s)" if retry_after else ""
            raise RuntimeError(f"AcoustID rate limit reached (429){hint}. Please wait a moment.")
        resp.raise_for_status()
        data = resp.json()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"AcoustID lookup failed: {e}")

    if data.get("status") != "ok":
        err_msg = data.get("error", {}).get("message", "Unknown AcoustID error")
        raise RuntimeError(f"AcoustID API error: {err_msg}")

    results = data.get("results", [])
    matches: List[AudioFingerprintMatch] = []

    for res in results:
        score = float(res.get("score", 1.0))
        recordings = res.get("recordings", [])
        for rec in recordings:
            rec_id = rec.get("id", "")
            title = rec.get("title", "")
            
            # Extract artist
            artists_list = rec.get("artists", [])
            artist = ""
            if artists_list:
                artist = ", ".join(a.get("name", "") for a in artists_list if a.get("name"))
            elif "artist" in rec:
                artist = rec["artist"]

            # Extract release / album info
            album = ""
            year = ""
            track_number = ""
            genre = ""

            # Check releases directly or releasegroups
            releases = rec.get("releases", [])
            if not releases and "releasegroups" in rec:
                for rg in rec.get("releasegroups", []):
                    if "releases" in rg:
                        releases.extend(rg["releases"])
                    if not album and "title" in rg:
                        album = rg["title"]

            if releases:
                rel = releases[0]
                if not album:
                    album = rel.get("title", "")
                
                # Date
                date_val = rel.get("date")
                if isinstance(date_val, dict):
                    year = str(date_val.get("year", ""))
                elif isinstance(date_val, str) and len(date_val) >= 4:
                    year = date_val[:4]

                # Track position
                mediums = rel.get("mediums", [])
                if mediums:
                    tracks = mediums[0].get("tracks", [])
                    if tracks:
                        pos = tracks[0].get("position")
                        if pos:
                            track_number = str(pos)

            # User metadata / tags
            usermeta = rec.get("usermeta", [])
            if usermeta and not genre:
                tags = [m.get("value") for m in usermeta if m.get("value")]
                if tags:
                    genre = tags[0].capitalize()

            matches.append(AudioFingerprintMatch(
                score=score,
                title=title,
                artist=artist,
                album=album,
                year=year,
                track_number=track_number,
                genre=genre,
                recording_id=rec_id,
                fingerprint=fingerprint
            ))

    # Sort candidates by score descending
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches

def search_musicbrainz(query: str, limit: int = 10) -> List[AudioFingerprintMatch]:
    """
    Searches MusicBrainz recordings by text query (artist / title / filename).
    Used as an automatic fallback when AcoustID has no acoustic fingerprint on file.
    """
    import requests
    # Clean up search query
    clean_q = os.path.splitext(query)[0]
    clean_q = re.sub(r"^\d+\s*[-.]\s*", "", clean_q)
    clean_q = re.sub(r"[\(\[](?:flac|mp3|official video|audio|remastered|deluxe)[\)\]]", "", clean_q, flags=re.IGNORECASE)
    clean_q = clean_q.replace('"', '').replace("'", "").strip()

    url = "https://musicbrainz.org/ws/2/recording"
    params = {
        "query": clean_q,
        "fmt": "json",
        "limit": limit
    }
    headers = {
        "User-Agent": "FileTagger/1.0 (https://github.com/desktop-tagger/filetagger)"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=6)
        if r.status_code == 200:
            data = r.json()
        else:
            data = {}
    except Exception:
        data = {}

    results: List[AudioFingerprintMatch] = []
    for rec in data.get("recordings", []):
        mb_score = float(rec.get("score", 100)) / 100.0
        rec_id = rec.get("id", "")
        title = rec.get("title", "")

        artists = rec.get("artist-credit", [])
        artist_name = ""
        if artists:
            artist_name = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name"))

        album = ""
        year = ""
        track_number = ""
        genre = ""

        releases = rec.get("releases", [])
        if releases:
            rel = releases[0]
            album = rel.get("title", "")
            date_val = rel.get("date", "")
            if date_val and len(date_val) >= 4:
                year = date_val[:4]
            mediums = rel.get("media", [])
            if mediums:
                track_offset = mediums[0].get("track-offset", 0)
                if track_offset:
                    track_number = str(track_offset + 1)
        elif "first-release-date" in rec:
            year = rec["first-release-date"][:4]

        tags = rec.get("tags", [])
        if tags and not genre:
            genre = tags[0].get("name", "").capitalize()

        results.append(AudioFingerprintMatch(
            score=round(mb_score, 2),
            title=title,
            artist=artist_name,
            album=album,
            year=year,
            track_number=track_number,
            genre=genre,
            recording_id=rec_id
        ))

    if not results:
        # Fallback to iTunes track search
        try:
            itunes_url = "https://itunes.apple.com/search"
            itunes_params = {"term": clean_q, "entity": "song", "limit": limit}
            r_it = requests.get(itunes_url, params=itunes_params, timeout=6)
            if r_it.status_code == 200:
                for item in r_it.json().get("results", []):
                    rel_date = item.get("releaseDate", "")
                    year = rel_date[:4] if rel_date and len(rel_date) >= 4 else ""
                    results.append(AudioFingerprintMatch(
                        score=0.92,
                        title=item.get("trackName", ""),
                        artist=item.get("artistName", ""),
                        album=item.get("collectionName", ""),
                        year=year,
                        track_number=str(item.get("trackNumber", "")),
                        genre=item.get("primaryGenreName", ""),
                        recording_id=str(item.get("trackId", ""))
                    ))
        except Exception:
            pass

    return results

def identify_audio_file(
    file_path: str,
    fallback_query: str = "",
    client_key: str = ACOUSTID_DEFAULT_CLIENT
) -> List[AudioFingerprintMatch]:
    """
    High-level function: Fingerprints local audio file and identifies it via AcoustID.
    If AcoustID returns 0 matches, automatically falls back to MusicBrainz metadata search!
    """
    matches: List[AudioFingerprintMatch] = []
    fingerprint = ""

    try:
        duration, fingerprint = compute_chromaprint(file_path)
        matches = lookup_acoustid(duration, fingerprint, client_key=client_key)
    except Exception:
        pass

    # If acoustic fingerprint found matches, return them
    if matches:
        return matches

    # Fallback to MusicBrainz search
    query = fallback_query or os.path.splitext(os.path.basename(file_path))[0]
    if query:
        mb_matches = search_musicbrainz(query)
        if fingerprint:
            for m in mb_matches:
                m.fingerprint = fingerprint
        return mb_matches

    return []
