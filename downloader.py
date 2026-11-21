import argparse
import sys
import json
import os
import re
import urllib.parse
import urllib.request
import yt_dlp

DOWNLOAD_DIR = os.path.expanduser("~/Downloads/EveryDL/")

OUTTMPL = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

def progress_hook(d):
    if d["status"] == "downloading":
        percent = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_percent_str", "N/A")).strip()
        eta = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_eta_str", "N/A")).strip()
        print(f"\r{percent} | ETA: {eta}", end="", flush=True)

    elif d["status"] == "finished":
        print("\nDownload Done")

def is_spotify(url):
    return "open.spotify.com" in url


def resolve_spotify(url):
    # No DRM bypass. Get public title via oEmbed, then search YouTube.
    oembed = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url)
    with urllib.request.urlopen(oembed, timeout=10) as r:
        data = json.loads(r.read().decode())
    title = data.get("title", "")
    author = data.get("author_name", "")
    query = f"{author} - {title}".strip(" -")
    print(f"Spotify -> searching YouTube for: {query}")
    return f"ytsearch1:{query}"


def get_opts(mode, hook=None):
    opts = {
        "outtmpl": OUTTMPL,
        "progress_hooks": [hook or progress_hook],
        "noprogress": True,
        "noplaylist": True,
    }
    if getattr(sys, "frozen", False):
        opts["ffmpeg_location"] = getattr(sys, "_MEIPASS", "")
    if mode == "audio":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    elif mode == "720p":
        opts.update({
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "merge_output_format": "mp4",
        })
    else:
        opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })
    return opts

def download(url, mode, hook=None, cancel_event=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if is_spotify(url):
        try:
            url = resolve_spotify(url)
        except Exception as e:
            print(f"\nCould not read Spotify link: {e}")
            return 1
    try:
        def checked_hook(data):
            if cancel_event and cancel_event.is_set():
                raise Exception("Download cancelled")
            if hook:
                hook(data)
            else:
                progress_hook(data)

        with yt_dlp.YoutubeDL(get_opts(mode, checked_hook)) as ydl:
            return ydl.download([url])
    except Exception as e:
        print(f"\nDownload failed: {e}")
        return 1

def is_spotify_playlist(url):
    if "open.spotify.com" not in url:
        return False
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    return len(parts) >= 2 and parts[0] in ("playlist", "album")


def get_spotify_playlist_entries(url, limit=100):
    # No API key. The public embed page server-renders its track rows as HTML:
    # number, title, artist, duration per row. Same fallback as single tracks:
    # each row becomes a YouTube search.
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    kind, spotify_id = parts[0], parts[1]
    embed = f"https://open.spotify.com/embed/{kind}/{spotify_id}"
    req = urllib.request.Request(embed, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", "|", html)
    entries = []
    expected = 1
    for m in re.finditer(r"(\d{1,4})\|{2,}([^|]*?)\|{2,}([^|]*?)\|{2,}(\d{1,3}:\d{2})", text):
        number, title, artist = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
        if number != expected or not title:
            continue
        expected += 1
        query = f"{artist} - {title}".strip(" -") if artist else title
        entries.append({"title": query, "url": f"ytsearch1:{query}"})
        if len(entries) >= limit:
            break
    return entries


def get_playlist_entries(url):
    if is_spotify_playlist(url):
        try:
            return get_spotify_playlist_entries(url) or None
        except Exception as e:
            print(f"\nCould not read Spotify playlist: {e}")
            return None
    try:
        opts = {
            "extract_flat": True,
            "skip_download": True,
            "quiet": True,
            "playlistend": 100,
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries")

        if not entries:
            return None

        return [
            {
                "title": entry.get("title", "Unknown title"),
                "url": entry.get("url") or entry.get("webpage_url"),
            }
            for entry in entries
            if entry
        ]
    except Exception:
        return None   

def _note(hook, data, text):
    if hook:
        try:
            hook(data)
        except Exception:
            pass
    else:
        print(text)


def download_selection(url, mode, hook, indices, entries=None, cancel_event=None):

    if entries is None:
        entries = get_playlist_entries(url)
    if not entries:
        _note(hook, {"status": "playlist_empty"},
              "Not a playlist or empty playlist.")
        return 1

    valid = [i for i in indices if 0 <= i < len(entries)]
    if not valid:
        _note(hook, {"status": "playlist_empty"},
              "No valid video numbers selected.")
        return 1

    failures = []

    for number, index in enumerate(valid, start=1):
        if cancel_event and cancel_event.is_set():
            return 1
        entry = entries[index]
        title = entry.get("title", "Unknown title")

        _note(hook, {
            "status": "playlist_item",
            "title": title,
            "number": number,
            "total": len(valid),
        }, f"\nVideo {number}/{len(valid)}: {title}")

        video_url = entry.get("url")
        if video_url and re.match(r"^[A-Za-z0-9_-]{11}$", video_url):
            # Bare YouTube id from flat extraction; everything else
            # (full URLs, ytsearch1:, scsearch:) passes through untouched.
            video_url = f"https://www.youtube.com/watch?v={video_url}"

        result = download(
            video_url, mode, hook, cancel_event,
        )

        if result != 0:
            failures.append(title)
            _note(hook, {
                "status": "playlist_item_failed",
                "title": title,
            }, f"Failed: {title}")

    if failures:
        _note(hook, {"status": "playlist_done", "failed": len(failures)},
              f"\nDone with {len(failures)} failure(s).")
        return 1
    return 0

def main():
    parser = argparse.ArgumentParser(description="EveryDL engine test")
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument("--audio", action="store_true", help="Download as mp3 instead of mp4")
    parser.add_argument("--720p", dest="s720p", action="store_true", help="Cap video at 720p")
    parser.add_argument("--all", dest="all_videos", action="store_true", help="Download all playlist videos (capped)")
    parser.add_argument("--pick", default=None, help='Playlist picks, e.g. "1,3,5"')
    args = parser.parse_args()
    if args.audio:
        mode = "audio"
    elif args.s720p:
        mode = "720p"
    else:
        mode = "video"
    if args.all_videos or args.pick:
        entries = get_playlist_entries(args.url)
        if not entries:
            print("Not a playlist or empty playlist.")
            return 1
        for n, e in enumerate(entries, start=1):
            print(f"{n}. {e.get('title', 'Unknown title')}")
        if args.all_videos:
            indices = list(range(len(entries)))
        else:
            indices = []
            for item in args.pick.split(","):
                try:
                    i = int(item.strip()) - 1
                    if 0 <= i < len(entries) and i not in indices:
                        indices.append(i)
                except ValueError:
                    continue
        return download_selection(args.url, mode, None, indices, entries)
    return download(args.url, mode)

if __name__ == "__main__":
    main()    