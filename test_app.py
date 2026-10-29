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

        # 9. Test Studio Vector Icon Engine (ui/icons.py)
        import os as _os

        _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        _app = QApplication.instance() or QApplication([])
        from ui.icons import ICON_NAMES, get_icon, get_pixmap

        for icon_name in ICON_NAMES:
            ic = get_icon(icon_name, "#cbd5e1", 16)
            assert not ic.isNull(), f"Icon '{icon_name}' returned null QIcon"
            pm = get_pixmap(icon_name, "#3b82f6", 24)
            assert not pm.isNull() and pm.width() == 24 and pm.height() == 24, f"Invalid pixmap for '{icon_name}'"
        print(f"[OK] Studio vector icon engine verified ({len(ICON_NAMES)} SVG icons)")

        # 10. Test Compact Header Cover Art Card & Theme Tokens
        from ui.theme import COLOR_ACCENT, COLOR_DANGER, COLOR_SUCCESS, COLOR_WARNING
        from ui.thumbnail_panel import ThumbnailPanel

        assert all(c.startswith("#") for c in (COLOR_ACCENT, COLOR_DANGER, COLOR_SUCCESS, COLOR_WARNING))
        thumb = ThumbnailPanel()
        assert thumb.cover_label.width() == 120 and thumb.cover_label.height() == 120, (
            f"Expected 120x120 compact cover frame, got {thumb.cover_label.width()}x{thumb.cover_label.height()}"
        )
        for btn in (thumb.btn_choose, thumb.btn_grab, thumb.btn_fetch_online, thumb.btn_export, thumb.btn_remove):
            assert not btn.icon().isNull(), f"ThumbnailPanel button '{btn.text()}' missing vector QIcon"
            assert all(ord(ch) < 0x2600 for ch in btn.text()), f"Emoji found in button '{btn.text()}'"
        thumb.set_media_item(f_item2)
        assert thumb.cover_label.property("hasCover") is True, "hasCover property must be True when artwork is loaded"
        print("[OK] Compact 120x120 Cover Art Header Card & theme tokens verified")

        # 11. Test TagEditorPanel Unclipped Tabs, Vector Icons & Borderless Tables
        from ui.tag_editor_panel import TagEditorPanel

        tag_panel = TagEditorPanel()
        tab_titles = tuple(tag_panel.tabs.tabText(i) for i in range(tag_panel.tabs.count()))
        assert tab_titles == ("Standard", "All Tags", "Specs"), f"Unexpected tab titles: {tab_titles}"
        for i in range(tag_panel.tabs.count()):
            assert not tag_panel.tabs.tabIcon(i).isNull(), f"Tab {i} missing vector QIcon"
        assert tag_panel.ext_table.showGrid() is False, "ext_table should not show spreadsheet gridlines"
        assert tag_panel.ext_table.wordWrap() is False, "ext_table must have wordWrap=False to prevent overlapping text"
        assert tag_panel.tech_table.showGrid() is False, "tech_table should not show spreadsheet gridlines"
        assert tag_panel.tech_table.wordWrap() is False, "tech_table must have wordWrap=False"
        for btn in (tag_panel.btn_add_tag, tag_panel.btn_del_tag, tag_panel.btn_revert, tag_panel.btn_save):
            assert not btn.icon().isNull(), f"TagEditorPanel button '{btn.text()}' missing vector QIcon"
            assert all(ord(ch) < 0x2600 for ch in btn.text()), f"Emoji found in button '{btn.text()}'"
        print("[OK] TagEditorPanel unclipped tabs, vector icons & borderless tables verified")

        # 12. Test MainWindow Unified Studio Action Bar, Borderless Tracklist & Sidebar Layout
        from ui.main_window import MainWindow

        win = MainWindow()
        assert win.table_view.showGrid() is False, "Main tracklist table should be borderless (showGrid=False)"
        assert win.table_view.wordWrap() is False, "Main tracklist table must have wordWrap=False"
        assert win.table_view.verticalHeader().defaultSectionSize() == 34, "Tracklist row height should be 34px"
        assert win.toolbar.isAncestorOf(win.txt_search), "Search bar must live inside the unified top toolbar"
        assert win.inspector_sidebar.objectName() == "RightInspectorSidebar"
        sidebar_layout = win.inspector_sidebar.layout()
        assert sidebar_layout.indexOf(win.thumbnail_panel) == 0, "ThumbnailPanel must be at top of right sidebar"
        assert sidebar_layout.indexOf(win.tag_editor) == 1, "TagEditorPanel must be below ThumbnailPanel in sidebar"
        for action in win.findChildren(win.act_save_sel.__class__):
            txt = action.text() + action.iconText()
            assert all(ord(ch) < 0x2600 for ch in txt), f"Emoji found in MainWindow action: '{txt}'"
        print("[OK] MainWindow unified toolbar, borderless tracklist & top-artwork sidebar verified")

        # 13. Test Secondary Dialogs De-Slop (No Emojis, Borderless Tables, Theme Tokens)
        from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

        from ui.acoustic_id_dialog import AcousticIdDialog
        from ui.lyrics_dialog import LyricsDialog
        from ui.music_fetcher_dialog import MusicFetcherDialog
        from ui.online_fetcher_dialog import OnlineFetcherDialog
        from ui.rename_dialog import RenameDialog
        from ui.replay_gain_dialog import ReplayGainDialog

        dialogs = [
            AcousticIdDialog(f_item2, auto_start=False),
            LyricsDialog(f_item2, auto_start=False),
            MusicFetcherDialog("Espresso Macchiato", auto_start=False),
            OnlineFetcherDialog("Action Trailer", auto_start=False),
            RenameDialog([f_item2]),
            ReplayGainDialog([f_item2], auto_start=False),
        ]
        for dlg in dialogs:
            for btn in dlg.findChildren(QPushButton):
                assert all(ord(ch) < 0x2600 for ch in btn.text()), (
                    f"Emoji found in {dlg.__class__.__name__} button '{btn.text()}'"
                )
            for lbl in dlg.findChildren(QLabel):
                assert all(ord(ch) < 0x2600 for ch in lbl.text()), (
                    f"Emoji found in {dlg.__class__.__name__} label '{lbl.text()}'"
                )
            for tbl in dlg.findChildren(QTableWidget):
                assert tbl.showGrid() is False, f"{dlg.__class__.__name__} table should have showGrid=False"
                assert tbl.wordWrap() is False, f"{dlg.__class__.__name__} table should have wordWrap=False"
        print("[OK] All secondary dialogs verified emoji-free with borderless tables")

        # 14. Test WAV Full Metadata Parity (All 10 Standard Tags, Extra Tags, & Cover Art) (BUG-05)
        wav_path = "test_audio.wav"
        cmd_w = [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", wav_path]
        subprocess.run(cmd_w, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        w_item = read_media_item(wav_path)
        assert w_item.is_audio is True
        w_item.tags["title"] = "Wav Symphony"
        w_item.tags["artist"] = "Orchestra Master"
        w_item.tags["album"] = "Lossless Waves"
        w_item.tags["album_artist"] = "Orchestra"
        w_item.tags["year"] = "2025"
        w_item.tags["track_number"] = "03"
        w_item.tags["disc_number"] = "01"
        w_item.tags["genre"] = "Classical"
        w_item.tags["comment"] = "Studio Master 24bit"
        w_item.tags["composer"] = "Maestro"
        w_item.extra_tags["PRODUCER"] = "Top Producer"
        w_item.set_cover(frame, "image/jpeg")
        assert save_media_item(w_item) is True, f"WAV save failed: {w_item.error}"

        # Re-read WAV and verify round-trip
        w_item2 = read_media_item(wav_path)
        assert w_item2.tags["title"] == "Wav Symphony"
        assert w_item2.tags["artist"] == "Orchestra Master"
        assert w_item2.tags["album"] == "Lossless Waves"
        assert w_item2.tags["album_artist"] == "Orchestra"
        assert w_item2.tags["year"] == "2025"
        assert w_item2.tags["track_number"] == "03"
        assert w_item2.tags["disc_number"] == "01"
        assert w_item2.tags["genre"] == "Classical"
        assert w_item2.tags["comment"] == "Studio Master 24bit"
        assert w_item2.tags["composer"] == "Maestro"
        assert w_item2.extra_tags.get("PRODUCER") == "Top Producer"
        assert w_item2.cover_bytes is not None
        print("[OK] WAV full metadata parity & cover art saved and round-tripped (BUG-05)")

        # 15. Test Raw Probe Tag Alias Mapping (BUG-01)
        from core.tagger import RAW_TAG_ALIAS_MAP

        assert RAW_TAG_ALIAS_MAP.get("date") == "year"
        assert RAW_TAG_ALIAS_MAP.get("track") == "track_number"
        assert RAW_TAG_ALIAS_MAP.get("disc") == "disc_number"
        assert RAW_TAG_ALIAS_MAP.get("description") == "comment"
        assert RAW_TAG_ALIAS_MAP.get("albumartist") == "album_artist"
        # Audio formats shouldn't leak raw metadata into extra_tags
        assert "date" not in f_item2.extra_tags and "DATE" not in f_item2.extra_tags
        assert "track" not in f_item2.extra_tags and "TRACK" not in f_item2.extra_tags
        print("[OK] Raw probe tag alias mapping verified (BUG-01)")

        # 16. Test TagEditorPanel Comment & Extended Tags Safety (BUG-02)
        tag_panel.set_selected_items([w_item2])
        # Verify comment maps to standard tag without KeyError
        assert tag_panel.txt_comment.toPlainText() == "Studio Master 24bit"
        found_comment = False
        for r in range(tag_panel.ext_table.rowCount()):
            k_item = tag_panel.ext_table.item(r, 0)
            if k_item and k_item.text().lower() == "comment":
                found_comment = True
                val_item = tag_panel.ext_table.item(r, 1)
                val_item.setText("Updated via All Tags")
                break
        if found_comment:
            assert tag_panel.txt_comment.toPlainText() == "Updated via All Tags"

        # Test adding custom extra tag via _set_standard_field_ui_value and extra tags
        tag_panel._set_standard_field_ui_value("comment", "New Comment Value")
        assert tag_panel.txt_comment.toPlainText() == "New Comment Value"
        tag_panel._set_standard_field_ui_value("genre", "Ambient")
        assert tag_panel.cmb_genre.currentText() == "Ambient"

        # Test safe removal without KeyError
        w_item2.extra_tags["TEST_KEY"] = "TestVal"
        tag_panel.set_selected_items([w_item2])
        del w_item2.extra_tags["TEST_KEY"]
        tag_panel.set_selected_items([w_item2])
        assert "TEST_KEY" not in w_item2.extra_tags
        print("[OK] TagEditorPanel comment syncing & extra tags safety verified (BUG-02)")

        # 17. Test RenameDialog Slash Track Number Formatting, Extended Tokens, & Two-Phase Swap (BUG-03)
        from unittest.mock import patch

        from PySide6.QtWidgets import QMessageBox

        from core.media_item import MediaItem

        item_a = MediaItem(file_path="track_01_old.mp3")
        item_a.tags["track_number"] = "1/12"
        item_a.tags["title"] = "Track One"
        item_a.tags["artist"] = "Artist A"
        item_a.tags["album_artist"] = "Band Leader"
        item_a.tags["disc_number"] = "1/2"

        item_b = MediaItem(file_path="track_02_old.mp3")
        item_b.tags["track_number"] = "2/12"
        item_b.tags["title"] = "Track Two"
        item_b.tags["artist"] = "Artist B"
        item_b.tags["album_artist"] = "Band Leader"
        item_b.tags["disc_number"] = "2/2"

        rnd = RenameDialog([item_a, item_b])
        rnd.cmb_pattern.setCurrentText("{track_number} - {album_artist} - {title}")
        rnd._update_preview()
        new_name_a = rnd.table.item(0, 1).text()
        new_name_b = rnd.table.item(1, 1).text()
        assert new_name_a == "01 - Band Leader - Track One.mp3", f"Got: {new_name_a}"
        assert new_name_b == "02 - Band Leader - Track Two.mp3", f"Got: {new_name_b}"

        # Test disc_number token
        rnd.cmb_pattern.setCurrentText("CD{disc_number}-{track_number}")
        rnd._update_preview()
        assert rnd.table.item(0, 1).text() == "CD1-01.mp3"
        assert rnd.table.item(1, 1).text() == "CD2-02.mp3"

        # Test two-phase swap rename on disk without collision failure
        swap_file_1 = os.path.abspath("swap_alpha.mp3")
        swap_file_2 = os.path.abspath("swap_beta.mp3")
        with open(swap_file_1, "w") as f:
            f.write("Alpha Content")
        with open(swap_file_2, "w") as f:
            f.write("Beta Content")

        swap_item_1 = MediaItem(file_path=swap_file_1)
        swap_item_1.tags["title"] = "swap_beta"
        swap_item_2 = MediaItem(file_path=swap_file_2)
        swap_item_2.tags["title"] = "swap_alpha"

        # Rename 1 -> swap_beta.mp3, 2 -> swap_alpha.mp3 (mutual swap!)
        rnd_swap = RenameDialog([swap_item_1, swap_item_2])
        rnd_swap.cmb_pattern.setCurrentText("{title}")
        rnd_swap._update_preview()
        # Verify no collision tooltip on distinct swap targets
        assert not rnd_swap.table.item(0, 1).toolTip()
        with patch.object(QMessageBox, "information"):
            rnd_swap._execute_rename()

        with open(swap_file_1) as f:
            content_1 = f.read()
        with open(swap_file_2) as f:
            content_2 = f.read()
        assert content_1 == "Beta Content", f"Swap failed for file 1: {content_1}"
        assert content_2 == "Alpha Content", f"Swap failed for file 2: {content_2}"
        if os.path.exists(swap_file_1):
            os.remove(swap_file_1)
        if os.path.exists(swap_file_2):
            os.remove(swap_file_2)
        print("[OK] RenameDialog track formatting, tokens & atomic swap verified (BUG-03)")

        # 18. Test MainWindow Path Normalization Deduplication (BUG-06)
        abs_audio = os.path.abspath(audio_path)
        var_1 = abs_audio
        var_2 = abs_audio.replace("\\", "/")
        var_3 = abs_audio.lower()
        win.table_model.clear()
        win.load_paths([var_1, var_2, var_3])
        assert len(win.table_model.items) == 1, (
            f"Expected 1 item after deduplication, got {len(win.table_model.items)}"
        )
        # Attempt reloading the same path with another variation
        win.load_paths([var_2])
        assert len(win.table_model.items) == 1, "Duplicate item added on re-load"
        print("[OK] Path normalization and load deduplication verified (BUG-06)")

        print("\nALL TESTS PASSED SUCCESSFULLY!")

    finally:
        for f in [video_path, audio_path, flac_path, "test_audio.wav", "swap_alpha.mp3", "swap_beta.mp3"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


if __name__ == "__main__":
    test_full_workflow()
