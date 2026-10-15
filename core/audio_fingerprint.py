import os
import sys
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
    3. Auto-downloads AcoustID's official precompiled Windows binary into bin/
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
                data = resp.read()
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for name in z.namelist():
                        if name.endswith("fpcalc.exe"):
                            with open(local_bin, "wb") as f:
                                f.write(z.read(name))
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
        resp.raise_for_status()
        data = resp.json()
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

def identify_audio_file(
    file_path: str,
    client_key: str = ACOUSTID_DEFAULT_CLIENT
) -> List[AudioFingerprintMatch]:
    """
    High-level function: Fingerprints local audio file and identifies it via AcoustID.
    """
    duration, fingerprint = compute_chromaprint(file_path)
    return lookup_acoustid(duration, fingerprint, client_key=client_key)
