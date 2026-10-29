import math
import os
import re
import subprocess
from dataclasses import dataclass

from core.ffmpeg_utils import get_ffmpeg_path
from core.media_item import MediaItem

DEFAULT_REFERENCE_LUFS = -18.00  # Standard ReplayGain 2.0 Reference


@dataclass
class ReplayGainResult:
    file_path: str
    integrated_lufs: float
    true_peak_db: float
    duration: float
    track_gain: str
    track_peak: str
    album_gain: str | None = None
    album_peak: str | None = None


def scan_track_loudness(file_path: str, proc_list: list | None = None) -> tuple[float, float, float]:
    """
    Runs FFmpeg's ebur128 audio filter to calculate:
    - Integrated loudness (LUFS)
    - True peak (dBFS)
    - Audio duration (seconds)
    Returns: (integrated_lufs, true_peak_db, duration_seconds)
    """
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg is required for ReplayGain analysis but was not found.")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Run ebur128 filter
    cmd = [
        ffmpeg_exe,
        "-nostats",
        "-hide_banner",
        "-i",
        file_path,
        "-filter_complex",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        startupinfo=startupinfo,
    )
    if proc_list is not None:
        proc_list.append(proc)
    try:
        _, stderr_output = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    finally:
        if proc_list is not None and proc in proc_list:
            proc_list.remove(proc)

    # Parse Integrated loudness
    # Example in FFmpeg:
    #   Integrated loudness:
    #     I:         -14.2 LUFS
    #     Threshold: -24.2 LUFS
    i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", stderr_output)
    if not i_match:
        # Try alternate pattern
        i_match = re.search(r"\bI:\s+([-\d\.]+)\s+LUFS", stderr_output)

    integrated_lufs = float(i_match.group(1)) if i_match else -18.0

    # Parse True peak
    # Example in FFmpeg:
    #   True peak:
    #     Peak:       -1.5 dBFS
    peak_match = re.search(r"True peak:\s+Peak:\s+([-\d\.]+)\s+dBFS", stderr_output)
    if not peak_match:
        peak_match = re.search(r"\bPeak:\s+([-\d\.]+)\s+dBFS", stderr_output)

    true_peak_db = float(peak_match.group(1)) if peak_match else 0.0

    # Parse Duration
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", stderr_output)
    duration = 0.0
    if dur_match:
        hrs, mins, secs = dur_match.groups()
        duration = int(hrs) * 3600 + int(mins) * 60 + float(secs)

    return integrated_lufs, true_peak_db, duration


def format_replaygain_track(
    integrated_lufs: float, true_peak_db: float, reference_lufs: float = DEFAULT_REFERENCE_LUFS
) -> tuple[str, str]:
    """Calculates and formats (track_gain, track_peak) strings."""
    gain_db = reference_lufs - integrated_lufs
    track_gain = f"{gain_db:+.2f} dB"

    # Linear scale true peak
    linear_peak = 10.0 ** (true_peak_db / 20.0)
    track_peak = f"{linear_peak:.6f}"
    return track_gain, track_peak


def format_replaygain_album(
    track_scans: list[tuple[float, float, float]], reference_lufs: float = DEFAULT_REFERENCE_LUFS
) -> tuple[str, str]:
    """
    Calculates unified Album Gain & Album Peak from multiple tracks using energy-weighted LUFS aggregation.
    """
    valid_tracks = [t for t in track_scans if t[2] > 0]
    if not valid_tracks:
        valid_tracks = track_scans

    if not valid_tracks:
        return "+0.00 dB", "1.000000"

    total_dur = sum(d for _, _, d in valid_tracks)
    if total_dur <= 0:
        total_dur = len(valid_tracks)
        valid_tracks = [(lufs, tp, 1.0) for lufs, tp, _ in valid_tracks]

    power_sum = sum(d * (10.0 ** (lufs / 10.0)) for lufs, _, d in valid_tracks)
    album_lufs = 10.0 * math.log10(power_sum / total_dur)
    album_gain_db = reference_lufs - album_lufs
    album_gain = f"{album_gain_db:+.2f} dB"

    max_true_peak_db = max(tp for _, tp, _ in valid_tracks)
    album_peak_linear = 10.0 ** (max_true_peak_db / 20.0)
    album_peak = f"{album_peak_linear:.6f}"

    return album_gain, album_peak


def apply_replaygain_tags(
    item: MediaItem, track_gain: str, track_peak: str, album_gain: str | None = None, album_peak: str | None = None
):
    """
    Applies standard ReplayGain tags to the MediaItem's extra_tags dictionary.
    """
    item.extra_tags["REPLAYGAIN_TRACK_GAIN"] = track_gain
    item.extra_tags["REPLAYGAIN_TRACK_PEAK"] = track_peak
    if album_gain:
        item.extra_tags["REPLAYGAIN_ALBUM_GAIN"] = album_gain
    if album_peak:
        item.extra_tags["REPLAYGAIN_ALBUM_PEAK"] = album_peak
    item.extra_tags["REPLAYGAIN_REFERENCE_LOUDNESS"] = f"{DEFAULT_REFERENCE_LUFS:.2f} LUFS"
    item.mark_dirty()
