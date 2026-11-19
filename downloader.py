import argparse
import json
import os
import urllib.parse
import urllib.request
import yt_dlp

DOWNLOAD_DIR = os.path.expanduser("~/Downloads/EveryDL/")

OUTTMPL = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

def progress_hook(d):
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "N/A").strip()
        eta = d.get("_eta_str", "N/A").strip()
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

def download(url, mode, hook=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if is_spotify(url):
        try:
            url = resolve_spotify(url)
        except Exception as e:
            print(f"\nCould not read Spotify link: {e}")
            return 1
    try:
        with yt_dlp.YoutubeDL(get_opts(mode, hook)) as ydl:
            return ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        print(f"\nDownload failed: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description="EveryDL engine test")
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument("--audio", action="store_true", help="Download as mp3 instead of mp4")
    parser.add_argument("--720p", dest="s720p", action="store_true", help="Cap video at 720p")
    args = parser.parse_args()
    if args.audio:
        mode = "audio"
    elif args.s720p:
        mode = "720p"
    else:
        mode = "video"
    download(args.url, mode)

if __name__ == "__main__":
    main()    