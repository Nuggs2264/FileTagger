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
| `Ctrl+F` | Fetch Movie/TV Info & Poster Online |
| `Ctrl+R` | Open Batch Rename dialog |
| `Del` | Remove selected items from list |
| `Ctrl+Q` | Exit |
