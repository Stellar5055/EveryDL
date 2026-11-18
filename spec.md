# EveryDL - spec

Goal: Windows app to download videos/audio from URL for learning yt-dlp.
Stack: Python only.

## Stage 1 - Engine (CLI test)
- One file: `downloader.py` with `download(url, mode)` where mode = video / audio.
- Use `yt_dlp.YoutubeDL` directly, no subprocess.
- Support: YouTube video, YouTube audio (mp3 via ffmpeg).
- Proof: `python downloader.py <URL> --audio` works, shows progress in terminal.
- Learn: `-F`, `-f`, `format`, `postprocessors`, `progress_hooks`, `outtmpl`.

## Stage 2 - TUI + MVP
- TUI lib: `Textual`. 1 header, 1 URL input + Paste, 1 format row, 1 progress, 1 log. One accent color, dark bg.
- Layout: `[URL input] [Paste] / Format: [video-best|720p|mp3] [Download] / [progress] / log`.
- Sites: YouTube, Instagram, TikTok, X, SoundCloud (all via yt-dlp default extractors, no custom code).
- Spotify: paste link -> lookup title + artist -> `ytsearch1:` download. No direct Spotify download.
- Queue: add 1 URL at a time, download one by one. No parallel.
- Files go to `~/Downloads/EveryDL/` with `%(title)s.%(ext)s`.

## Distribution (Windows)
- Dev/command: `pyproject.toml` with `everydl = "app:main"`. Publish to PyPI. Run via `pipx install everydl` or `uv tool install everydl`.
- Single exe: `PyInstaller --onefile` -> `EveryDL.exe` in GitHub Releases. Bundle `ffmpeg.exe`, no Python needed.
- Later: `winget install EveryDL` via manifest pointing to Release exe. Not in MVP.

## Stage 3 - Improvement
- Playlist support with limit.
- Cookies.txt import for private/login videos.
- Thumbnail + subtitles embed option.
- History of past downloads.
- Update yt-dlp automatically.

Non-goals: no DRM bypass, no GUI, no accounts, no mobile.
Legal: only download own / CC / public content. Note in README.
