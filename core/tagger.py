import os
import io
import shutil
import subprocess
import tempfile
from typing import Optional, Dict, Any, List

import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, APIC, TIT2, TPE1, TALB, TPE2, TDRC, TRCK, TPOS, TCON,
    COMM, TCOM, TXXX, USLT, TCOP, TPUB, TBPM, TKEY, TENC, TSSE,
    TSRC, TIT1, TIT3, TPE3, TEXT, TCMP, ID3NoHeaderError
)
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.wave import WAVE
from PIL import Image

Image.MAX_IMAGE_PIXELS = 36_000_000  # Cap at 36 MP (e.g., 6000x6000) to prevent decompression bombs

from core.media_item import MediaItem, STANDARD_TAG_KEYS
from core.ffmpeg_utils import (
    get_media_duration_and_resolution,
    get_media_technical_and_raw_metadata,
    get_ffmpeg_path
)

MP4_ATOM_MAP = {
    "\xa9too": "encoder",
    "desc": "description",
    "ldes": "long_description",
    "cprt": "copyright",
    "\xa9grp": "grouping",
    "\xa9lyr": "lyrics",
    "tvsh": "tv_show",
    "tvsn": "season",
    "tves": "episode",
    "tven": "episode_id",
    "purd": "purchase_date",
    "soar": "artist_sort",
    "soal": "album_sort",
    "sonm": "title_sort",
    "soco": "composer_sort",
    "pgap": "gapless",
    "cpil": "compilation",
    "tmpo": "bpm",
}
REVERSE_MP4_ATOM_MAP = {v: k for k, v in MP4_ATOM_MAP.items()}

ID3_FRAME_MAP = {
    "TCOP": "copyright",
    "TPUB": "publisher",
    "TBPM": "bpm",
    "TKEY": "initial_key",
    "TENC": "encoder",
    "TSSE": "encoding_tool",
    "TSRC": "isrc",
    "USLT": "lyrics",
    "TIT1": "grouping",
    "TIT3": "subtitle",
    "TPE3": "conductor",
    "TEXT": "lyricist",
    "TSOP": "artist_sort",
    "TSOA": "album_sort",
    "TSOT": "title_sort",
    "TCMP": "compilation",
}
REVERSE_ID3_FRAME_MAP = {v: k for k, v in ID3_FRAME_MAP.items()}

def detect_image_mime(data: bytes) -> str:
    """Detects if image data is JPEG, PNG, WEBP, etc."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            if fmt == "PNG":
                return "image/png"
            elif fmt == "WEBP":
                return "image/webp"
            elif fmt == "GIF":
                return "image/gif"
            return "image/jpeg"
    except Exception:
        return "image/jpeg"

def normalize_cover_image(data: bytes, prefer_format: str = "JPEG") -> tuple:
    """
    Normalizes any input image (WebP, BMP, GIF, PNG, or disguised JPEG)
    into standard, valid JPEG (or PNG) bytes.
    Ensures container decoders (like MP4 covr or ID3 APIC) never receive corrupt/unsupported formats.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            if img.width > 3000 or img.height > 3000:
                img.thumbnail((3000, 3000), Image.Resampling.LANCZOS)
            if prefer_format.upper() == "PNG" and fmt == "PNG":
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue(), "image/png"
            else:
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95, optimize=True)
                return buf.getvalue(), "image/jpeg"
    except Exception as e:
        raise ValueError(f"Invalid or unsupported cover image data: {e}")

def notify_windows_shell(file_path: str):
    """Notifies Windows Explorer that a file has been modified to invalidate cached thumbnails."""
    if os.name == "nt":
        try:
            import ctypes
            SHCNE_UPDATEITEM = 0x00002000
            SHCNF_PATHW = 0x0005
            ctypes.windll.shell32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW, file_path, None)
        except Exception:
            pass

def read_media_item(file_path: str) -> MediaItem:
    """Reads all metadata tags, technical properties, and cover art from an audio or video file."""
    item = MediaItem(file_path=file_path)
    ext = item.extension

    try:
        if ext in {".mp4", ".m4a", ".m4v", ".mov"}:
            _read_mp4(item)
        elif ext == ".mp3":
            _read_mp3(item)
        elif ext == ".flac":
            _read_flac(item)
        elif ext in {".ogg", ".opus"}:
            _read_ogg(item)
        elif ext == ".wav":
            _read_wav(item)
        elif item.is_video:
            _read_video_generic(item)
        else:
            _read_generic_mutagen(item)
    except Exception as e:
        item.error = f"Read error: {str(e)}"

    # Retrieve technical stream details and probe raw metadata in a single pass
    tech_info, raw_meta = get_media_technical_and_raw_metadata(file_path)
    probed_dur_str = tech_info.pop("_duration_sec", "")
    probed_res = tech_info.pop("_resolution", "")
    item.technical_info.update(tech_info)

    # For container formats where mutagen doesn't write extra tags (like generic MKV/AVI),
    # include any probed raw metadata not already in standard tags
    for rk, rv in raw_meta.items():
        rk_lower = rk.lower()
        if rk_lower in item.tags and not item.tags[rk_lower]:
            item.tags[rk_lower] = rv
        elif rk_lower not in item.tags and rk not in item.extra_tags:
            item.extra_tags[rk] = rv

    if item.duration <= 0 and probed_dur_str:
        try:
            item.duration = float(probed_dur_str)
        except ValueError:
            pass
    if item.is_video and not item.resolution and probed_res:
        item.resolution = probed_res

    if item.duration <= 0 or (item.is_video and not item.resolution):
        dur, res = get_media_duration_and_resolution(file_path)
        if dur > 0 and item.duration <= 0:
            item.duration = dur
        if res and not item.resolution:
            item.resolution = res

    item.mark_saved()
    return item

def save_media_item(item: MediaItem) -> bool:
    """Saves updated metadata tags and cover art back to the media file."""
    ext = item.extension
    try:
        if item.cover_modified and item.cover_bytes:
            norm_bytes, mime = normalize_cover_image(item.cover_bytes)
            item.cover_bytes = norm_bytes
            item.cover_mime = mime

        if ext in {".mp4", ".m4a", ".m4v", ".mov"}:
            _save_mp4(item)
        elif ext == ".mp3":
            _save_mp3(item)
        elif ext == ".flac":
            _save_flac(item)
        elif ext in {".ogg", ".opus"}:
            _save_ogg(item)
        elif ext == ".wav":
            _save_wav(item)
        elif ext in {".mkv", ".webm"}:
            _save_mkv(item)
        else:
            item.error = f"Saving tags is not supported for {ext}"
            return False

        item.mark_saved()
        notify_windows_shell(item.file_path)
        return True
    except Exception as e:
        item.error = f"Save error: {str(e)}"
        return False

# -------------------------------------------------------------
# MP3 Handler
# -------------------------------------------------------------
def _read_mp3(item: MediaItem):
    audio = MP3(item.file_path)
    if audio.info:
        item.duration = audio.info.length

    if not audio.tags:
        try:
            audio.add_tags()
        except Exception:
            return

    tags = audio.tags
    item.tags["title"] = str(tags.get("TIT2", ""))
    item.tags["artist"] = str(tags.get("TPE1", ""))
    item.tags["album"] = str(tags.get("TALB", ""))
    item.tags["album_artist"] = str(tags.get("TPE2", ""))
    item.tags["year"] = str(tags.get("TDRC", tags.get("TYER", "")))
    item.tags["track_number"] = str(tags.get("TRCK", ""))
    item.tags["disc_number"] = str(tags.get("TPOS", ""))
    item.tags["genre"] = str(tags.get("TCON", ""))
    item.tags["composer"] = str(tags.get("TCOM", ""))
    
    comments = tags.getall("COMM")
    if comments:
        item.tags["comment"] = str(comments[0].text[0]) if comments[0].text else ""

    apics = tags.getall("APIC")
    if apics:
        cover = next((a for a in apics if a.type == 3), apics[0])
        item.cover_bytes = cover.data
        item.cover_mime = cover.mime or detect_image_mime(cover.data)

    # Read all other extended frames
    standard_id3_keys = {"TIT2", "TPE1", "TALB", "TPE2", "TDRC", "TYER", "TRCK", "TPOS", "TCON", "TCOM", "COMM", "APIC"}
    for frame_id, frame in tags.items():
        base_id = frame_id.split(":")[0]
        if base_id in standard_id3_keys:
            continue

        if frame_id.startswith("TXXX:"):
            desc = frame_id[5:]
            item.extra_tags[desc] = str(frame.text[0]) if (hasattr(frame, "text") and frame.text) else str(frame)
        elif base_id in ID3_FRAME_MAP:
            friendly_name = ID3_FRAME_MAP[base_id]
            val = str(frame.text[0]) if (hasattr(frame, "text") and frame.text) else str(frame)
            item.extra_tags[friendly_name] = val
        else:
            val = str(frame.text[0]) if (hasattr(frame, "text") and frame.text) else str(frame)
            item.extra_tags[frame_id] = val

def _save_mp3(item: MediaItem):
    try:
        tags = ID3(item.file_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.setall("TIT2", [TIT2(encoding=3, text=item.tags.get("title", ""))])
    tags.setall("TPE1", [TPE1(encoding=3, text=item.tags.get("artist", ""))])
    tags.setall("TALB", [TALB(encoding=3, text=item.tags.get("album", ""))])
    tags.setall("TPE2", [TPE2(encoding=3, text=item.tags.get("album_artist", ""))])
    tags.setall("TDRC", [TDRC(encoding=3, text=item.tags.get("year", ""))])
    tags.setall("TRCK", [TRCK(encoding=3, text=item.tags.get("track_number", ""))])
    tags.setall("TPOS", [TPOS(encoding=3, text=item.tags.get("disc_number", ""))])
    tags.setall("TCON", [TCON(encoding=3, text=item.tags.get("genre", ""))])
    tags.setall("TCOM", [TCOM(encoding=3, text=item.tags.get("composer", ""))])

    comment_text = item.tags.get("comment", "")
    if comment_text:
        tags.setall("COMM", [COMM(encoding=3, lang="eng", desc="", text=[comment_text])])
    else:
        tags.delall("COMM")

    # Save extra tags
    # First, handle deletions: remove any extra tags deleted from original_extra_tags
    for orig_key in item.original_extra_tags.keys():
        if orig_key not in item.extra_tags:
            if orig_key in REVERSE_ID3_FRAME_MAP:
                tags.delall(REVERSE_ID3_FRAME_MAP[orig_key])
            else:
                tags.delall(f"TXXX:{orig_key}")
                tags.delall(orig_key)

    # Now write current extra tags
    for k, v in item.extra_tags.items():
        if not v:
            continue
        if k in REVERSE_ID3_FRAME_MAP:
            f_id = REVERSE_ID3_FRAME_MAP[k]
            if f_id == "USLT":
                tags.setall("USLT", [USLT(encoding=3, lang="eng", desc="", text=v)])
            elif f_id in globals() and issubclass(globals()[f_id], mutagen.id3.TextFrame):
                tags.setall(f_id, [globals()[f_id](encoding=3, text=[v])])
            else:
                tags.setall(f"TXXX:{k}", [TXXX(encoding=3, desc=k, text=[v])])
        else:
            tags.setall(f"TXXX:{k}", [TXXX(encoding=3, desc=k, text=[v])])

    if item.cover_modified:
        tags.delall("APIC")
        if item.cover_bytes:
            mime = item.cover_mime or detect_image_mime(item.cover_bytes)
            tags.add(APIC(
                encoding=3,
                mime=mime,
                type=3,  # Front cover
                desc="Cover",
                data=item.cover_bytes
            ))

    tags.save(item.file_path, v2_version=3)

# -------------------------------------------------------------
# MP4 / M4A / M4V Handler
# -------------------------------------------------------------
def _read_mp4(item: MediaItem):
    audio = MP4(item.file_path)
    if audio.info:
        item.duration = audio.info.length

    def get_first(key):
        val = audio.tags.get(key) if audio.tags else None
        if val and isinstance(val, list) and len(val) > 0:
            return str(val[0])
        return ""

    if audio.tags:
        item.tags["title"] = get_first("\xa9nam")
        item.tags["artist"] = get_first("\xa9ART")
        item.tags["album"] = get_first("\xa9alb")
        item.tags["album_artist"] = get_first("aART")
        item.tags["year"] = get_first("\xa9day")
        item.tags["genre"] = get_first("\xa9gen")
        item.tags["comment"] = get_first("\xa9cmt")
        item.tags["composer"] = get_first("\xa9wrt")

        trkn = audio.tags.get("trkn")
        if trkn and isinstance(trkn, list) and len(trkn) > 0:
            track_no, track_total = trkn[0]
            item.tags["track_number"] = f"{track_no}/{track_total}" if track_total else str(track_no)

        disk = audio.tags.get("disk")
        if disk and isinstance(disk, list) and len(disk) > 0:
            disc_no, disc_total = disk[0]
            item.tags["disc_number"] = f"{disc_no}/{disc_total}" if disc_total else str(disc_no)

        covr = audio.tags.get("covr")
        if covr and isinstance(covr, list) and len(covr) > 0:
            cov = covr[0]
            item.cover_bytes = bytes(cov)
            if hasattr(cov, "imageformat") and cov.imageformat == MP4Cover.FORMAT_PNG:
                item.cover_mime = "image/png"
            else:
                item.cover_mime = "image/jpeg"

        # Read all other extended atoms
        standard_mp4_atoms = {
            "\xa9nam", "\xa9ART", "\xa9alb", "aART", "\xa9day", "\xa9gen",
            "\xa9cmt", "\xa9wrt", "trkn", "disk", "covr"
        }
        for atom_key, val_list in audio.tags.items():
            if atom_key in standard_mp4_atoms:
                continue

            val_str = ""
            if isinstance(val_list, list) and len(val_list) > 0:
                first_val = val_list[0]
                if isinstance(first_val, bytes):
                    val_str = first_val.decode("utf-8", errors="ignore")
                else:
                    val_str = str(first_val)
            else:
                val_str = str(val_list)

            # Map atom key to friendly name if known
            if atom_key in MP4_ATOM_MAP:
                friendly = MP4_ATOM_MAP[atom_key]
                item.extra_tags[friendly] = val_str
            elif atom_key.startswith("----:com.apple.iTunes:"):
                custom_name = atom_key.replace("----:com.apple.iTunes:", "")
                item.extra_tags[custom_name] = val_str
            else:
                item.extra_tags[atom_key] = val_str

def _save_mp4(item: MediaItem):
    audio = MP4(item.file_path)
    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags
    tags["\xa9nam"] = [item.tags.get("title", "")]
    tags["\xa9ART"] = [item.tags.get("artist", "")]
    tags["\xa9alb"] = [item.tags.get("album", "")]
    tags["aART"] = [item.tags.get("album_artist", "")]
    tags["\xa9day"] = [item.tags.get("year", "")]
    tags["\xa9gen"] = [item.tags.get("genre", "")]
    tags["\xa9cmt"] = [item.tags.get("comment", "")]
    tags["\xa9wrt"] = [item.tags.get("composer", "")]

    track_str = item.tags.get("track_number", "").strip()
    if track_str:
        try:
            if "/" in track_str:
                p1, p2 = track_str.split("/", 1)
                tags["trkn"] = [(int(p1), int(p2))]
            else:
                tags["trkn"] = [(int(track_str), 0)]
        except ValueError:
            pass
    elif "trkn" in tags:
        del tags["trkn"]

    disc_str = item.tags.get("disc_number", "").strip()
    if disc_str:
        try:
            if "/" in disc_str:
                p1, p2 = disc_str.split("/", 1)
                tags["disk"] = [(int(p1), int(p2))]
            else:
                tags["disk"] = [(int(disc_str), 0)]
        except ValueError:
            pass
    elif "disk" in tags:
        del tags["disk"]

    # Handle deletion of extra tags
    for orig_k in item.original_extra_tags.keys():
        if orig_k not in item.extra_tags:
            atom = REVERSE_MP4_ATOM_MAP.get(orig_k, orig_k)
            if atom in tags:
                del tags[atom]
            freeform_key = f"----:com.apple.iTunes:{orig_k}"
            if freeform_key in tags:
                del tags[freeform_key]

    # Write current extra tags
    for k, v in item.extra_tags.items():
        if not v:
            continue
        if k in REVERSE_MP4_ATOM_MAP:
            atom = REVERSE_MP4_ATOM_MAP[k]
            tags[atom] = [v]
        elif len(k) == 4:
            # 4-character standard atom
            tags[k] = [v]
        else:
            # Custom iTunes freeform atom
            freeform_key = f"----:com.apple.iTunes:{k}"
            tags[freeform_key] = [v.encode("utf-8")]

    # Cover
    if item.cover_modified:
        if item.cover_bytes:
            mime = item.cover_mime or detect_image_mime(item.cover_bytes)
            fmt = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
            tags["covr"] = [MP4Cover(item.cover_bytes, imageformat=fmt)]
        elif "covr" in tags:
            del tags["covr"]

    audio.save()

# -------------------------------------------------------------
# FLAC Handler
# -------------------------------------------------------------
def _read_flac(item: MediaItem):
    audio = FLAC(item.file_path)
    if audio.info:
        item.duration = audio.info.length

    def get_first(key):
        val = audio.get(key)
        return str(val[0]) if val and len(val) > 0 else ""

    item.tags["title"] = get_first("TITLE")
    item.tags["artist"] = get_first("ARTIST")
    item.tags["album"] = get_first("ALBUM")
    item.tags["album_artist"] = get_first("ALBUMARTIST") or get_first("ALBUM ARTIST")
    item.tags["year"] = get_first("DATE") or get_first("YEAR")
    item.tags["track_number"] = get_first("TRACKNUMBER")
    item.tags["disc_number"] = get_first("DISCNUMBER")
    item.tags["genre"] = get_first("GENRE")
    item.tags["comment"] = get_first("COMMENT") or get_first("DESCRIPTION")
    item.tags["composer"] = get_first("COMPOSER")

    if audio.pictures:
        pic = next((p for p in audio.pictures if p.type == 3), audio.pictures[0])
        item.cover_bytes = pic.data
        item.cover_mime = pic.mime or detect_image_mime(pic.data)

    standard_flac_keys = {
        "TITLE", "ARTIST", "ALBUM", "ALBUMARTIST", "ALBUM ARTIST", "DATE",
        "YEAR", "TRACKNUMBER", "DISCNUMBER", "GENRE", "COMMENT", "DESCRIPTION", "COMPOSER"
    }
    for k, val_list in audio.items():
        k_upper = k.upper()
        if k_upper in standard_flac_keys:
            continue
        item.extra_tags[k] = str(val_list[0]) if val_list else ""

def _save_flac(item: MediaItem):
    audio = FLAC(item.file_path)
    audio["TITLE"] = item.tags.get("title", "")
    audio["ARTIST"] = item.tags.get("artist", "")
    audio["ALBUM"] = item.tags.get("album", "")
    audio["ALBUMARTIST"] = item.tags.get("album_artist", "")
    audio["DATE"] = item.tags.get("year", "")
    audio["TRACKNUMBER"] = item.tags.get("track_number", "")
    audio["DISCNUMBER"] = item.tags.get("disc_number", "")
    audio["GENRE"] = item.tags.get("genre", "")
    audio["COMMENT"] = item.tags.get("comment", "")
    audio["COMPOSER"] = item.tags.get("composer", "")

    # Deletions
    for orig_k in item.original_extra_tags.keys():
        if orig_k not in item.extra_tags:
            if orig_k in audio:
                del audio[orig_k]
            elif orig_k.upper() in audio:
                del audio[orig_k.upper()]

    # Add/update extra tags
    for k, v in item.extra_tags.items():
        if v:
            audio[k.upper()] = v

    if item.cover_modified:
        audio.clear_pictures()
        if item.cover_bytes:
            pic = Picture()
            pic.type = 3  # Front cover
            pic.mime = item.cover_mime or detect_image_mime(item.cover_bytes)
            pic.desc = "Cover"
            pic.data = item.cover_bytes
            audio.add_picture(pic)

    audio.save()

# -------------------------------------------------------------
# OGG / Opus Handler
# -------------------------------------------------------------
def _read_ogg(item: MediaItem):
    try:
        audio = OggOpus(item.file_path)
    except Exception:
        audio = OggVorbis(item.file_path)

    if audio.info:
        item.duration = audio.info.length

    def get_first(key):
        val = audio.get(key)
        return str(val[0]) if val and len(val) > 0 else ""

    item.tags["title"] = get_first("title")
    item.tags["artist"] = get_first("artist")
    item.tags["album"] = get_first("album")
    item.tags["album_artist"] = get_first("albumartist")
    item.tags["year"] = get_first("date")
    item.tags["track_number"] = get_first("tracknumber")
    item.tags["disc_number"] = get_first("discnumber")
    item.tags["genre"] = get_first("genre")
    item.tags["comment"] = get_first("comment")
    item.tags["composer"] = get_first("composer")

    standard_ogg_keys = {
        "title", "artist", "album", "albumartist", "date",
        "tracknumber", "discnumber", "genre", "comment", "composer"
    }
    for k, val_list in audio.items():
        k_lower = k.lower()
        if k_lower in standard_ogg_keys:
            continue
        item.extra_tags[k] = str(val_list[0]) if val_list else ""

def _save_ogg(item: MediaItem):
    try:
        audio = OggOpus(item.file_path)
    except Exception:
        audio = OggVorbis(item.file_path)

    audio["title"] = item.tags.get("title", "")
    audio["artist"] = item.tags.get("artist", "")
    audio["album"] = item.tags.get("album", "")
    audio["albumartist"] = item.tags.get("album_artist", "")
    audio["date"] = item.tags.get("year", "")
    audio["tracknumber"] = item.tags.get("track_number", "")
    audio["discnumber"] = item.tags.get("disc_number", "")
    audio["genre"] = item.tags.get("genre", "")
    audio["comment"] = item.tags.get("comment", "")
    audio["composer"] = item.tags.get("composer", "")

    # Deletions
    for orig_k in item.original_extra_tags.keys():
        if orig_k not in item.extra_tags and orig_k in audio:
            del audio[orig_k]

    for k, v in item.extra_tags.items():
        if v:
            audio[k] = v

    audio.save()

# -------------------------------------------------------------
# WAV Handler
# -------------------------------------------------------------
def _read_wav(item: MediaItem):
    audio = WAVE(item.file_path)
    if audio.info:
        item.duration = audio.info.length
    if audio.tags:
        item.tags["title"] = str(audio.tags.get("TIT2", ""))
        item.tags["artist"] = str(audio.tags.get("TPE1", ""))
        item.tags["album"] = str(audio.tags.get("TALB", ""))
        item.tags["year"] = str(audio.tags.get("TDRC", ""))
        item.tags["genre"] = str(audio.tags.get("TCON", ""))

def _save_wav(item: MediaItem):
    audio = WAVE(item.file_path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.setall("TIT2", [TIT2(encoding=3, text=item.tags.get("title", ""))])
    audio.tags.setall("TPE1", [TPE1(encoding=3, text=item.tags.get("artist", ""))])
    audio.tags.setall("TALB", [TALB(encoding=3, text=item.tags.get("album", ""))])
    audio.tags.setall("TDRC", [TDRC(encoding=3, text=item.tags.get("year", ""))])
    audio.tags.setall("TCON", [TCON(encoding=3, text=item.tags.get("genre", ""))])
    audio.save()

# -------------------------------------------------------------
# MKV / Video Handler
# -------------------------------------------------------------
def _read_video_generic(item: MediaItem):
    """Probes video duration and attempts to extract embedded cover if present."""
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        return

    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel", "error",
        "-i", item.file_path,
        "-map", "0:v",
        "-map", "-0:V",
        "-c", "copy",
        "-f", "image2pipe",
        "-"
    ]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, timeout=8)
        if proc.returncode == 0 and len(proc.stdout) > 500:
            item.cover_bytes = proc.stdout
            item.cover_mime = detect_image_mime(proc.stdout)
    except Exception:
        pass

def _save_mkv(item: MediaItem):
    """
    Saves tags and attached thumbnail into MKV using FFmpeg stream copy (no re-encoding!).
    """
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg is required to save MKV tags/thumbnails")

    target_dir = os.path.dirname(os.path.abspath(item.file_path))
    fd_out, temp_out = tempfile.mkstemp(
        prefix=".filetagger_tmp_",
        suffix=item.extension,
        dir=target_dir
    )
    os.close(fd_out)
    cover_temp = None

    cmd = [ffmpeg_exe, "-hide_banner", "-y", "-i", item.file_path, "-map", "0", "-c", "copy"]

    # Write standard tags
    if item.tags.get("title"):
        cmd.extend(["-metadata", f"title={item.tags['title']}"])
    if item.tags.get("artist"):
        cmd.extend(["-metadata", f"artist={item.tags['artist']}"])
    if item.tags.get("comment"):
        cmd.extend(["-metadata", f"comment={item.tags['comment']}"])
    if item.tags.get("year"):
        cmd.extend(["-metadata", f"date={item.tags['year']}"])

    # Write extra tags
    for k, v in item.extra_tags.items():
        if v:
            cmd.extend(["-metadata", f"{k}={v}"])

    if item.cover_modified and item.cover_bytes:
        mime = item.cover_mime or detect_image_mime(item.cover_bytes)
        ext = ".png" if mime == "image/png" else ".jpg"
        fd_cov, cover_temp = tempfile.mkstemp(prefix=".cover_tmp_", suffix=ext, dir=target_dir)
        with os.fdopen(fd_cov, "wb") as f:
            f.write(item.cover_bytes)

        cmd.extend([
            "-attach", cover_temp,
            "-metadata:s:t", f"mimetype={mime}",
            "-metadata:s:t", f"filename=cover{ext}"
        ])

    cmd.append(temp_out)

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, timeout=60)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg MKV update failed: {err}")

        os.replace(temp_out, item.file_path)
    finally:
        if cover_temp and os.path.exists(cover_temp):
            try:
                os.remove(cover_temp)
            except Exception:
                pass
        if os.path.exists(temp_out):
            try:
                os.remove(temp_out)
            except Exception:
                pass

def _read_generic_mutagen(item: MediaItem):
    try:
        mf = mutagen.File(item.file_path)
        if mf and mf.info:
            item.duration = mf.info.length
    except Exception:
        pass
