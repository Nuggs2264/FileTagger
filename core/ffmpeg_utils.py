import os
import subprocess
import shutil
import re
from typing import Optional, Tuple, Dict, Any

_FFMPEG_PATH = None

def get_ffmpeg_path() -> Optional[str]:
    """Finds or resolves the path to the ffmpeg executable."""
    global _FFMPEG_PATH
    if _FFMPEG_PATH and os.path.exists(_FFMPEG_PATH):
        return _FFMPEG_PATH

    # Check system PATH first
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        _FFMPEG_PATH = sys_ffmpeg
        return _FFMPEG_PATH

    # Try imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            _FFMPEG_PATH = exe
            return _FFMPEG_PATH
    except Exception:
        pass

    return None

def get_media_duration_and_resolution(file_path: str) -> Tuple[float, Optional[str]]:
    """
    Returns (duration_in_seconds, resolution_str_e.g._1920x1080)
    using ffmpeg stderr probe.
    """
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe or not os.path.exists(file_path):
        return 0.0, None

    cmd = [ffmpeg_exe, "-hide_banner", "-i", file_path]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            startupinfo=startupinfo,
            timeout=10
        )
        output = proc.stderr

        duration = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if dur_match:
            hours = int(dur_match.group(1))
            minutes = int(dur_match.group(2))
            seconds = float(dur_match.group(3))
            duration = hours * 3600 + minutes * 60 + seconds

        res_match = re.search(r"Video:.*?,\s*(\d{2,5}x\d{2,5})", output)
        resolution = res_match.group(1) if res_match else None

        return duration, resolution
    except Exception as e:
        print(f"Error probing media with ffmpeg: {e}")
        return 0.0, None

def get_media_technical_and_raw_metadata(file_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Returns (technical_info_dict, raw_metadata_dict) using a single FFmpeg invocation.
    Also populates internal keys '_duration_sec' and '_resolution' in tech_info
    to avoid redundant FFmpeg probes.
    """
    tech_info: Dict[str, str] = {}
    raw_meta: Dict[str, str] = {}

    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe or not os.path.exists(file_path):
        return tech_info, raw_meta

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        cmd_meta = [ffmpeg_exe, "-hide_banner", "-i", file_path, "-f", "ffmetadata", "-"]
        proc = subprocess.run(
            cmd_meta,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            startupinfo=startupinfo,
            timeout=10
        )

        # 1. Parse technical streams, duration, and resolution from stderr
        err = proc.stderr or ""
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if dur_match:
            hours = int(dur_match.group(1))
            minutes = int(dur_match.group(2))
            seconds = float(dur_match.group(3))
            tech_info["_duration_sec"] = str(hours * 3600 + minutes * 60 + seconds)

        res_match = re.search(r"Video:.*?,\s*(\d{2,5}x\d{2,5})", err)
        if res_match:
            tech_info["_resolution"] = res_match.group(1)

        for line in err.splitlines():
            line_str = line.strip()
            if line_str.startswith("Input #0,"):
                m = re.search(r"Input #0,\s*([^,]+),", line_str)
                if m:
                    tech_info["Container"] = m.group(1).upper()
            elif line_str.startswith("Duration:"):
                m_dur = re.search(r"Duration:\s*([^,]+)", line_str)
                if m_dur:
                    tech_info["Duration"] = m_dur.group(1)
                m_bit = re.search(r"bitrate:\s*(\d+\s*kb/s)", line_str)
                if m_bit:
                    tech_info["Bitrate"] = m_bit.group(1)
            elif "Stream #" in line_str:
                if "Video:" in line_str and "attached pic" not in line_str:
                    tech_info["Video Stream"] = line_str.split("Video:", 1)[1].strip()
                elif "Audio:" in line_str:
                    tech_info["Audio Stream"] = line_str.split("Audio:", 1)[1].strip()
                elif "Subtitle:" in line_str:
                    tech_info["Subtitle"] = line_str.split("Subtitle:", 1)[1].strip()

        # 2. Parse ffmetadata from stdout
        in_header = True
        for line in (proc.stdout or "").splitlines():
            line_s = line.strip()
            if line_s.startswith(";FFMETADATA"):
                continue
            if line_s.startswith("["):
                in_header = False
                continue
            if in_header and "=" in line_s:
                k, v = line_s.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and v and not k.startswith(";"):
                    raw_meta[k] = v
    except Exception:
        pass

    return tech_info, raw_meta

def extract_frame_bytes(file_path: str, timestamp_seconds: float, max_width: int = 1280) -> Optional[bytes]:
    """
    Extracts a single video frame at timestamp_seconds as JPEG bytes.
    Optionally scales down if max_width is exceeded to keep frame extraction snappy.
    """
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe or not os.path.exists(file_path):
        return None

    time_str = f"{timestamp_seconds:.3f}"
    
    vf_filter = f"scale='min({max_width},iw)':-2"
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel", "error",
        "-ss", time_str,
        "-i", file_path,
        "-vf", vf_filter,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-q:v", "3",
        "pipe:1"
    ]

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            timeout=15
        )
        if proc.returncode == 0 and len(proc.stdout) > 0:
            return proc.stdout
    except Exception as e:
        print(f"Error extracting frame: {e}")

    return None
