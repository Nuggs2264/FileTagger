# FileTagger 🎵🎬

An advanced audio and video metadata tagger and thumbnail editor inspired by dBpoweramp and Mp3tag.

## Features

- **Audio & Video Support**:
  - **Audio**: MP3 (ID3v2.3/v2.4), FLAC (Vorbis Comments), M4A / AAC, OGG / Opus, WAV.
  - **Video**: MP4, M4V, MOV, MKV, WebM, AVI.
- **Video Thumbnail & Poster Frame Grabber**:
  - **Interactive Scrubber**: Scrub through any video file, jump to timestamps or percentage markers (10%, 25%, 50%, etc.), stepper buttons (`-10s`, `-1s`, `+1s`, `+10s`), and grab any frame to set as the embedded thumbnail!
  - **Drag & Drop Cover Art**: Drop any image (`.jpg`, `.png`, `.webp`, `.bmp`) directly onto the thumbnail preview box.
  - **Export Cover**: Save embedded artwork to a file on disk.
- **dBpoweramp & Mp3tag-Style Tag Inspector (3 Tabs)**:
  - **🏷️ Standard Tags**: Title, Artist, Album, Album Artist, Year, Track #, Disc #, Genre, Composer, and multi-line Comments. Supports batch editing with `<keep original / multiple values>` indicators.
  - **📑 All Tags & Metadata**: Displays every single tag present in the file (encoder, copyright, description, lyrics, TV show/season/episode, ISRC, BPM, custom user tags). You can edit any value in-place, search/filter tags, add custom fields (`➕ Add Tag...`), or delete tags (`🗑️ Remove Tag`).
  - **⚙️ Stream & File Specs**: Full technical breakdown including Container, Overall Bitrate, Video Stream (codec, resolution, FPS, pixel format), Audio Stream (codec, sample rate, channels, bitrate), and File Size.
- **Online Movie & TV Poster Fetcher (TMDb / IMDb)**:
  - Query **IMDb**, **TVMaze**, or **TMDb** using the file's title or filename.
  - Automatically cleans resolution tags and scene junk from search terms.
  - Live side-by-side preview with official high-res cinema poster, release year, director, cast, genres, and plot synopsis.
  - 1-click batch application with checkboxes to selectively apply artwork, title, year, director, genres, and plot summary.
  - Automatically normalizes downloaded poster images into 100% compliant baseline JPEG before embedding.
- **Online Music Album Art & Metadata Fetcher**:
  - Search **Apple Music / iTunes** (pristine up to 1400×1400 artwork), **Deezer** (1000×1000 artwork), **MusicBrainz & Cover Art Archive (CAA)**, and **Discogs**.
  - High-resolution album cover preview, track counts, release dates, and genres.
  - 1-click batch application to all selected tracks.
- **Music & Audio Superpowers**:
  - **🎵 Acoustic Fingerprinting (Shazam-style Audio ID)**: Analyzes audio waveforms via portable **Chromaprint / AcoustID** with automatic **MusicBrainz** metadata fallback to identify untagged tracks (`Track01.mp3`).
  - **🎤 Synchronized Lyrics Downloader**: Automatically downloads timestamped karaoke lyrics from **LRCLIB**. Embeds into tags (`USLT`, `©lyr`, `LYRICS`) and exports `.lrc` sidecar files.
  - **🔊 ReplayGain / Loudness Normalization Scanner**: Scans audio tracks using **EBU R128** (`libebur128` via portable FFmpeg) to write `REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`, `REPLAYGAIN_ALBUM_GAIN`, and `REPLAYGAIN_ALBUM_PEAK`.
- **Batch Tools**:
  - **Batch Rename**: Rename files based on tags (`{artist} - {title}`, `{track_number} - {title}`, etc.) with real-time preview and safe character sanitization.
  - **Auto-Number Tracks**: Sequentially number tracks (1..N) across selections.
  - **Guess Tags from Filename**: Automatically parses `"Artist - Title"` from filenames into metadata tags.
- **Fast Virtualized Table**:
  - Direct in-cell editing for Title, Artist, Album, Year, Track, Genre, and Filename.
  - Real-time search and filter across filename, title, artist, and album.
  - Drag and drop files or folders directly into the app window.
  - Modern dark theme.

## Quick Start

### Windows Explorer
Double click [`run_app.bat`](file:///p:/code%20testing/FileTagger/run_app.bat) to launch the application.

### Command Line
```powershell
.\.venv\Scripts\python.exe main.py
```

## Hotkeys

| Shortcut | Action |
| :--- | :--- |
| `Ctrl+O` | Add Files... |
| `Ctrl+Shift+O` | Add Folder... |
| `Ctrl+S` | Save Selected files |
| `Ctrl+Shift+S` | Save All modified files |
| `Ctrl+Shift+F` | Fetch Album Art & Music Info Online (iTunes / Deezer / Discogs) |
| `Ctrl+F` | Fetch Movie/TV Info & Poster Online (TMDb / IMDb) |
| `Ctrl+I` | Identify Track (Acoustic Fingerprint / MusicBrainz) |
| `Ctrl+L` | Download Lyrics (LRCLIB Synchronized / Plain) |
| `Ctrl+G` | Scan ReplayGain Loudness (EBU R128) |
| `Ctrl+R` | Open Batch Rename dialog |
| `Del` | Remove selected items from list |
| `Ctrl+Q` | Exit |

## 🎬 TMDb API Setup & Attribution

FileTagger integrates with **The Movie Database (TMDb)** to fetch high-resolution movie and TV show posters, release metadata, directors, genres, and plot synopses.

### Attribution
> **"This product uses the TMDB API but is not endorsed or certified by TMDB."**

Please consult [TMDb Brand Guidelines & Attribution](tmdb_attribution_brand_guidelines.md) for official branding guidelines, approved logo usage, and brand colors.

---

### How to Get a Free TMDb API Key

TMDb provides free API keys for personal and non-commercial use:

1. **Create an Account**: Visit [themoviedb.org](https://www.themoviedb.org/) and register. Confirm your email address.
2. **Request an API Key**:
   - Open **Account Settings → API** ([themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)).
   - Click **Create** / **Request an API Key** and select **Developer** (Personal / Non-Commercial).
   - Accept the API Terms of Use and fill out the brief form:
     - **Application Name**: `FileTagger`
     - **Application URL**: `https://github.com/Nuggs2264/FileTagger` (or `n/a`)
     - **Type of Use**: `Personal / Desktop Application`
     - **Summary of Use**: Audio/video metadata tagging and poster art fetching.
3. **Copy Your Key**:
   - Copy the **API Key (v3 auth)** (a 32-character alphanumeric string).
4. **Add to FileTagger**:
   - In FileTagger, press `Ctrl+F` (or click **🌐 Fetch Online Info**).
   - Change the search engine dropdown to **`🌐 TMDb (API Key)`**.
   - Paste your key into the **TMDb API Key** box. FileTagger will automatically remember your key for all future sessions.

For additional details on rate limits, endpoints, and commercial licensing terms, see the [TMDb API Usage Guide](TmdbApiUsageAndHowToGetIt.md).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

