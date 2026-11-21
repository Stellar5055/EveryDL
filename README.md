# EveryDL

## What it is

A simple TUI app for downloading audio and video from many sites like youtube and spotify. Made in Python using yt-dlp and Textual

## DEMO

[Demo of the App](media/demo.mp4)

## What it does

Download youtube videos, spotify tracks, instagram, TikTok, X, SoundCloud etc and 1000+ other sites using yt-dlp. Playlists supported. Downloaded media are found in your `Downloads/EveryDL/` folder (auto made on first download)

Has a TUI made with Textual, with a progress bar, ETA and a log. And there are download controls like pause/resume, stop and skip item.

## How it works behind the scenes

1. You paste a link and select a format(highest quality, 720p and audio only), then the app first checks if it is a playlist.
2. If it is, you get to pick wether to download all the videos in the playlist or the latest one or select custom ones to download
3. Each video is downloaded one at a time into `Downloads/EveryDL/`
4. Since Spotify links cant be directly downloaded, the app reads the public details like track name, artist etc and searches for the best match on youtube and downloads them.
5. After a file is downloaded, ffmpeg is used to process them

## Try it

Download `EveryDL.exe` from latest version in [Releases](https://github.com/Stellar5055/EveryDL/releases), double-click it. No Python needed.


## Notes

One limitation in the app - playlists have a cap of 100 items.

AI was used but not too much and my session is there in the repo and everything is journaled. Pls check out my journal, i spent a lot of effort on that, also check out my agent sessions.