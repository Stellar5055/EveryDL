import asyncio, os, pyperclip, re, threading
from textual import events
from textual.app import ComposeResult, App
from textual.widgets import Select, Log, Button, Input, Header, Footer, Static, Label
from textual.containers import Horizontal, Vertical, VerticalScroll
from downloader import download, get_playlist_entries, download_selection, _paused, _skip
from textual.screen import ModalScreen

class PlaylistModal(ModalScreen):
    def __init__(self, entries):
        super().__init__()
        self.entries = entries

    def compose(self):
        listing = "\n".join(
            f"{n}. {e.get('title', 'Unknown title')}"
            for n, e in enumerate(self.entries, start=1)
        )

        with Vertical(id="dialog"):
            yield Label(
                f"Playlist: {len(self.entries)} videos", id="dlg-title"
            )

            with VerticalScroll(id="dlg-list"):
                yield Label(listing, id="dlg-items")

            yield Button("Latest only", id="first")
            yield Button(f"All {len(self.entries)}", id="all")

            yield Input(
                placeholder="e.g. 1,5,8",
                id="selection"
            )

            yield Button("Download selected", id="selected")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event):
        if event.button.id == "first":
            self.dismiss([0])
        elif event.button.id == "all":
            self.dismiss(list(range(len(self.entries))))
        elif event.button.id == "selected":
            text = self.query_one("#selection", Input).value

            indices = []

            for item in text.split(","):
                try:
                    index = int(item.strip()) - 1

                    if 0 <= index < len(self.entries):
                        if index not in indices:
                            indices.append(index)

                except ValueError:
                    continue
            if indices:
                self.dismiss(indices)
            else:
                self.dismiss("invalid")
        elif event.button.id == "cancel":
            self.dismiss(None)

class EveryDL(App):
    CSS = """
    Screen {
      align: center top; 
      }
    #hero {
      width: 80%;
      height: auto;
      text-align: center;
      margin: 1 0;
      text-style: bold;
    }
    #url {
      width: 1fr;
      margin: 1 0; 
    }
    #row {
      width: 80%;
      height: auto;
      margin: 1 0;
    }
    #paste {
      width: 12;
      margin: 1 0 1 1;
    }
    #actions {
      width: 80%;
      height: auto;
      margin: 0 0 1 0;
      align: center middle;
    }
    #log {
      width: 80%;
      height: 10; 
    }
    #controls {
    width: 80%;
    height: auto;
    margin: 1 0;
    align: center middle;
    }
    #barrow {
      width: 80%;
      height: auto;
      margin: 1 0;
    }
    #bar {
      width: 1fr;
      min-width: 0;
      height: 1;
      text-style: bold;
      overflow: hidden;
    }
    #pct {
      width: 16;
      height: 1;
      text-align: right;
      text-style: bold;
    }
    PlaylistModal {
      align: center middle;
    }
    #dialog {
      width: 70%;
      max-width: 80;
      height: auto;
      max-height: 80%;
      background: $surface;
      border: thick $primary;
      padding: 1 2;
    }
    #dlg-title {
      width: 100%;
      text-align: center;
      text-style: bold;
      margin-bottom: 1;
    }
    #dlg-list {
      width: 100%;
      height: 10;
      margin-bottom: 1;
    }
    #dlg-items {
      width: 100%;
      text-align: left;
    }
    #dialog Button, #dialog Input {
      width: 100%;
      margin: 0 0 1 0;
    }
    #mode {
      width: 80%;
      margin: 0 0 1 0;
    }
"""

    _last_logged: float = -10.0
    _progress_files: dict = {}
    _last_pct: float = 0.0
    _last_eta: str = "--:--"
    _is_playlist = False

    BAR_WIDTH = 200

    def _bar_width(self) -> int:
        # Fit the bar into the current terminal instead of a fixed width.
        # barrow is 80% of screen, minus the pct widget and margins.
        # screen.size is used (not self.size) so the value is fresh
        # even when App-level resize events don't fire.
        try:
            screen_width = self.screen.size.width
        except Exception:
            screen_width = 0
        if not screen_width:
            return 60
        return max(20, min(EveryDL.BAR_WIDTH, int(screen_width * 0.8) - 18))

    @staticmethod
    def _render_bar(percentage: float, width: int) -> str:
        filled = int(round(percentage / 100 * width))
        filled = max(0, min(width, filled))
        return f"[cyan]{'█' * filled}[/][dim]{'░' * (width - filled)}[/]"

    def _paint_bar(self, percentage: float, eta: str = "") -> None:
        width = self._bar_width()
        self.query_one("#bar", Static).update(self._render_bar(percentage, width))
        self.query_one("#pct", Static).update(self._render_pct(percentage, eta))
        self._last_pct = percentage
        self._last_eta = eta

    @staticmethod
    def _clean(s: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*m", "", s or "").strip()

    @staticmethod
    def _render_pct(percentage: float, eta: str = "") -> str:
        return f"{percentage:5.1f}% {EveryDL._clean(eta)}"

    def compose(self) -> ComposeResult:
        yield Header()

        yield Static("[bold white]Every[/][bold purple]DL[/]", id="hero")

        yield Horizontal(
            Input(placeholder="Paste a URL...", id="url"),
            Button("Paste", id="paste"),
            id="row"
        )

        yield Select(
            [
                ("Best available quality", "video"),
                ("720p quality", "720p"),
                ("Extract audio (MP3)", "audio"),
            ],
            value="video",
            id="mode",
        )

        yield Horizontal(
            Button("Start Download", id="go"),
            Button("Exit", id="quit"),
            id="actions"
        )

        yield Horizontal(
            Static(self._render_bar(0.0, 60), id="bar"),
            Static(self._render_pct(0.0, eta="--:--"), id="pct"),
            id="barrow",
        )
        yield Log(id="log")

        yield Horizontal(
            Button("Pause", id="pause", disabled=True),
            Button("Stop", id="stop", disabled=True),
            Button("Skip", id="skip", disabled=True),
            id="controls",
        )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:

        log = self.query_one("#log", Log)

        if event.button.id == "paste":
            try:
                clipboard = pyperclip.paste().strip()
            except Exception:
                clipboard = ""

            if clipboard:
                self.query_one("#url", Input).value = clipboard
                log.write_line("Pasted from clipboard")

            else:
                log.write_line("Clipboard empty")

            return

        if event.button.id == "quit":
            self.action_request_quit()
            return

        if event.button.id == "pause":
            pause_button = self.query_one("#pause", Button)

            if _paused.is_set():
                _paused.clear()
                pause_button.label = "Pause"
                log.write_line("Resumed")
            else:
                _paused.set()
                pause_button.label = "Unpause"
                log.write_line("Paused")

            return
        
        if event.button.id == "stop":
            self._cancel_download.set()
            _paused.clear()
            _skip.clear()

            self.query_one("#pause", Button).disabled = True
            self.query_one("#skip", Button).disabled = True
            self.query_one("#stop", Button).disabled = True

            log.write_line("Stopping download...")

            return

        if event.button.id == "skip":
            if self._is_playlist:
                _skip.set()
                log.write_line("Skipping current item...")
            return
        
        
        if event.button.id != "go":
            return

        url = self.query_one("#url", Input).value.strip()
        mode = self.query_one("#mode", Select).value

        log = self.query_one("#log", Log)
        button = self.query_one("#go", Button)

        if not url:
            log.write_line("Please paste a valid URL before downloading")
            return

        if not isinstance(mode, str):
            log.write_line("Please select a download format first.")
            return

        self._paint_bar(0.0, "--:--")
        button.disabled = True

        log.write_line("")
        log.write_line("Getting things ready...")
        log.write_line(f"URL: {url}")
        log.write_line(f"Selected format: {mode}")
        self._cancel_download.clear()

        _paused.clear()
        _skip.clear()
        self._is_playlist = False

        pause_button = self.query_one("#pause", Button)
        pause_button.label = "Pause"
        pause_button.disabled = False

        self.query_one("#stop", Button).disabled = False
        self.query_one("#skip", Button).disabled = True

        self._download_worker = self.run_worker(
            self.do_download(url, mode),
            exclusive=True,
        )

    async def do_download(self, url: str, mode: str) -> None:

        def progress_hook(data):
            self.call_from_thread(
                self.update_progress, data
            )

        self._last_logged = -10.0
        self._progress_files = {}

        try:
            entries = await asyncio.to_thread(
                get_playlist_entries, url
            )

            if self._cancel_download.is_set():
                self.query_one("#log", Log).write_line("Download stopped.")
                self.reset_interface(False)
                return
            
            if not entries:
                self.query_one("#log", Log).write_line(
                    "Not a playlist or empty playlist. "
                    "Starting single download..."
                )

                result = await asyncio.to_thread(
                    download,
                    url,
                    mode,
                    progress_hook,
                    self._cancel_download,
                )

            else:
                # Show the playlist selection modal.
                indices = await self.push_screen_wait(
                    PlaylistModal(entries)
                )

                if indices == "invalid":
                    self.query_one("#log", Log).write_line("No valid video numbers selected")
                    self.reset_interface(False)
                    return

                if not indices:
                    self.reset_interface(False)
                    return

                self._is_playlist = True
                self.query_one("#skip", Button).disabled = len(indices) <= 1

                result = await asyncio.to_thread(
                    download_selection,
                    url,
                    mode,
                    progress_hook,
                    indices,
                    entries,
                    self._cancel_download,
                )

            if self._cancel_download.is_set():
                self.query_one("#log", Log).write_line("Download stopped.")
                self.reset_interface(False)

            elif result == 0:
                self.query_one("#log", Log).write_line(
                    "The Download was completed successfully"
                )
                self.reset_interface(True)

            else:
                self.query_one("#log", Log).write_line(
                    "Download failed. Check URL or try again."
                )
                self.reset_interface(False)

        except Exception as error:
            self.query_one("#log", Log).write_line(
                f"Something went wrong. Error: {error}"
            )
            self.reset_interface(False)

    def update_progress(self, data: dict) -> None:

        if data.get("status") == "downloading":
            key = data.get("filename") or "main"
            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )
            downloaded = data.get("downloaded_bytes", 0)

            if total:
                self._progress_files[key] = (downloaded, total)
                overall_done = sum(d for d, _ in self._progress_files.values())
                overall_total = sum(t for _, t in self._progress_files.values())
                percentage = overall_done / overall_total * 100 if overall_total else None
            else:
                try:
                    raw = self._clean(data.get("_percent_str", "0%")).replace("~", "").strip().strip("%")
                    percentage = float(raw)
                except ValueError:
                    percentage = None

            if percentage is not None:
                if percentage > 100:
                    percentage = 100
                self._paint_bar(percentage, self._clean(data.get("_eta_str", "")))

                if percentage - self._last_logged >= 5.0:
                    self._last_logged = percentage
                    percent = self._clean(data.get("_percent_str", ""))
                    eta = self._clean(data.get("_eta_str", ""))

                    self.query_one("#log", Log).write_line(
                        f"Downloading: {percent} | Time Left: {eta}"
                    )

        elif data.get("status") == "playlist_item":
            self._progress_files = {}
            self._last_logged = -10.0
            self._paint_bar(0.0, "--:--")
            self.query_one("#log", Log).write_line(
                f"Video {data.get('number')}/{data.get('total')}: {data.get('title')}"
            )

        elif data.get("status") == "playlist_item_failed":
            self.query_one("#log", Log).write_line(
                f"Failed: {data.get('title')}"
            )

        elif data.get("status") == "playlist_item_skipped":
            self.query_one("#log", Log).write_line(f"Skipped: {data.get('title')}")

        elif data.get("status") == "finished":
            self.query_one("#log", Log).write_line(
                "Download complete. Processing the file..."
            )

    def reset_interface(self, success: bool) -> None:

        if success:
            self._paint_bar(100.0, "--:--")
        else:
            self._progress_files = {}
            self._paint_bar(0.0, "--:--")
        self.query_one("#go", Button).disabled = False

        pause_button = self.query_one("#pause", Button)
        pause_button.disabled = True
        pause_button.label = "Pause"

        self.query_one("#stop", Button).disabled = True
        self.query_one("#skip", Button).disabled = True

        _paused.clear()
        _skip.clear()
        self._cancel_download.clear()
        self._is_playlist = False


    def on_resize(self, event: events.Resize) -> None:
        width = max(20, min(EveryDL.BAR_WIDTH, int(event.size.width * 0.8) - 18))
        self.query_one("#bar", Static).update(self._render_bar(self._last_pct, width))
        self.query_one("#pct", Static).update(self._render_pct(self._last_pct, self._last_eta))

    BINDINGS = [
        ("q", "request_quit", "Quit")
    ]

    _cancel_download = threading.Event()
    _download_worker = None

    def action_request_quit(self):
        self._cancel_download.set()

        if self._download_worker:
            self._download_worker.cancel()

        self.exit()


def main():
    EveryDL().run()
    # yt-dlp runs in a non-daemon worker thread. Textual's exit() stops
    # the UI loop but that thread can keep the process alive, leaving the
    # console window open. Force-terminate once the UI is gone.
    os._exit(0)

if __name__ == "__main__":
    main()