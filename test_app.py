import os
import subprocess

from core.ffmpeg_utils import extract_frame_bytes, get_ffmpeg_path
from core.tagger import read_media_item, save_media_item


def test_full_workflow():
    ffmpeg = get_ffmpeg_path()
    assert ffmpeg is not None, "FFmpeg path must be found"

    video_path = "test_video.mp4"
    audio_path = "test_audio.mp3"
    flac_path = "test_audio.flac"

    try:
        # 1. Create a 3-second test MP4
        cmd_v = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=320x240:rate=10",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            video_path,
        ]
        subprocess.run(cmd_v, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. Create a 5-second test MP3
        cmd_a = [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-c:a", "libmp3lame", audio_path]
        subprocess.run(cmd_a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 3. Test video frame extraction
        frame = extract_frame_bytes(video_path, 1.5)
        assert frame is not None and len(frame) > 100, "Frame extraction failed"
        print(f"[OK] Video frame extracted: {len(frame)} bytes")

        # 4. Test MP4 tagging & thumbnail embedding
        v_item = read_media_item(video_path)
        assert v_item.is_video is True
        v_item.tags["title"] = "Action Trailer"
        v_item.tags["artist"] = "Studio X"
        v_item.tags["year"] = "2026"
        v_item.set_cover(frame, "image/jpeg")
        assert save_media_item(v_item) is True

        # Re-read video
        v_item2 = read_media_item(video_path)
        assert v_item2.tags["title"] == "Action Trailer"
        assert v_item2.tags["artist"] == "Studio X"
        assert v_item2.cover_bytes is not None
        print("[OK] Video tags and thumbnail saved & verified")

        # 5. Test MP3 tagging & cover embedding
        a_item = read_media_item(audio_path)
        assert a_item.is_audio is True
        a_item.tags["title"] = "Synthwave Song"
        a_item.tags["artist"] = "RetroArtist"
        a_item.tags["album"] = "Future Days"
        a_item.tags["track_number"] = "01"
        a_item.set_cover(frame, "image/jpeg")
        assert save_media_item(a_item) is True

        # Re-read MP3
        a_item2 = read_media_item(audio_path)
        assert a_item2.tags["title"] == "Synthwave Song"
        assert a_item2.tags["artist"] == "RetroArtist"
        assert a_item2.tags["album"] == "Future Days"
        assert a_item2.cover_bytes is not None
        print("[OK] Audio tags and cover art saved & verified")

        # 5b. Test FLAC tagging, Vorbis comments, and cover art
        cmd_f = [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", flac_path]
        subprocess.run(cmd_f, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        f_item = read_media_item(flac_path)
        assert f_item.is_audio is True
        f_item.tags["title"] = "Espresso Macchiato"
        f_item.tags["artist"] = "Tommy Cash (2)"
        f_item.tags["album"] = "Espresso Macchiato"
        f_item.tags["year"] = "2024"
        f_item.tags["track_number"] = "11"
        f_item.extra_tags["MUSICBRAINZ_TRACKID"] = "1fced54c-9ca6-49fd-b246-0d24158e472f"
        f_item.extra_tags["ACOUSTID_ID"] = "test-acoustid-uuid"
        f_item.extra_tags["Album"] = "Espresso Macchiato"
        f_item.set_cover(frame, "image/jpeg")
        assert save_media_item(f_item) is True, f"FLAC save failed: {f_item.error}"

        # Re-read FLAC
        f_item2 = read_media_item(flac_path)
        assert f_item2.tags["title"] == "Espresso Macchiato"
        assert f_item2.tags["artist"] == "Tommy Cash (2)"
        assert f_item2.extra_tags.get("MUSICBRAINZ_TRACKID") == "1fced54c-9ca6-49fd-b246-0d24158e472f"
        assert f_item2.cover_bytes is not None
        print("[OK] FLAC tags, Vorbis comments & cover art saved & verified")

        # 6. Test Acoustic Fingerprinting (Chromaprint / fpcalc)
        from core.audio_fingerprint import compute_chromaprint, get_fpcalc_path

        fpcalc_exe = get_fpcalc_path()
        assert fpcalc_exe and os.path.exists(fpcalc_exe), "fpcalc binary missing"
        dur, fp = compute_chromaprint(audio_path)
        assert dur > 1.0 and len(fp) > 0, "Acoustic fingerprinting failed"
        print(f"[OK] Acoustic fingerprint generated: duration={dur:.1f}s, length={len(fp)}")

        # 7. Test Synchronized Lyrics & LRC file generation
        from core.lyrics_fetcher import clean_title_for_search, save_lrc_file

        cleaned = clean_title_for_search("Synthwave Song (Remastered 2026)")
        assert cleaned == "Synthwave Song", f"Title cleaning failed: {cleaned}"
        sample_lrc = "[00:01.00] Retro synth intro\n[00:02.00] Bassline drops\n"
        lrc_file = save_lrc_file(audio_path, sample_lrc)
        assert os.path.isfile(lrc_file), ".lrc file not saved"
        os.remove(lrc_file)
        print("[OK] Synchronized lyrics & .lrc export verified")

        # 8. Test ReplayGain (EBU R128) Loudness Scanning
        from core.replay_gain import (
            apply_replaygain_tags,
            format_replaygain_album,
            format_replaygain_track,
            scan_track_loudness,
        )

        lufs, true_peak, dur = scan_track_loudness(audio_path)
        tg, tp = format_replaygain_track(lufs, true_peak)
        ag, ap = format_replaygain_album([(lufs, true_peak, dur)])
        assert tg.endswith("dB") and float(tp) >= 0.0, f"Invalid ReplayGain values: {tg}, {tp}"
        apply_replaygain_tags(a_item, tg, tp, ag, ap)
        assert a_item.extra_tags["REPLAYGAIN_TRACK_GAIN"] == tg
        save_media_item(a_item)
        a_item3 = read_media_item(audio_path)
        assert a_item3.extra_tags.get("REPLAYGAIN_TRACK_GAIN") == tg
        print(f"[OK] ReplayGain EBU R128 scanned & tagged ({tg}, peak {tp})")

        print("\nALL TESTS PASSED SUCCESSFULLY!")

    finally:
        for f in [video_path, audio_path, flac_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


if __name__ == "__main__":
    test_full_workflow()
