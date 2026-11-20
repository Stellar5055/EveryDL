import asyncio, os, pyperclip, threading
from textual.app import ComposeResult, App
from textual.widgets import Select, Log, Button, Input, Header, Footer, Static
from textual.containers import Horizontal
from downloader import download

class EveryDL(App):
    CSS = """
    Screen {
      align: center middle; 
      }
    #hero {
      width: 80%;
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
      margin: 1 0;
    }
    #paste {
      width: 12;
      margin: 1 0 1 1;
    }
    #actions {
      width: 80%;
      margin: 0 0 1 0;
      align: center middle;
    }
    #log {
      width: 80%;
      height: 10; 
    }
    #barrow {
      width: 80%;
      height: 1;
      margin: 1 0;
    }
    #bar {
      width: 1fr;
      height: 1;
      text-style: bold;
    }
    #pct {
      width: 12;
      height: 1;
      text-align: right;
      text-style: bold;
    }
    #mode {
      width: 80%;
      margin: 0 0 1 0;
    }
"""

    _last_logged: float = -10.0
    _progress_files: dict = {}

    BAR_WIDTH = 120

    @staticmethod
    def _render_bar(percentage: float) -> str:
        width = EveryDL.BAR_WIDTH
        filled = int(round(percentage / 100 * width))
        filled = max(0, min(width, filled))
        return f"[cyan]{'█' * filled}[/][dim]{'░' * (width - filled)}[/]"

    @staticmethod
    def _render_pct(percentage: float, eta: str = "") -> str:
        return f"{percentage:5.1f}% {eta}"

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
            Static(self._render_bar(0.0), id="bar"),
            Static(self._render_pct(0.0, eta="--:--"), id="pct"),
            id="barrow",
        )
        yield Log(id="log")
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
        
        if event.button.id != "go":
            return

        url = self.query_one("#url", Input).value.strip()
        mode = self.query_one("#mode", Select).value

        log = self.query_one("#log", Log)
        button = self.query_one("#go", Button)
        bar = self.query_one("#bar", Static)
        pct = self.query_one("#pct", Static)

        if not url:
            log.write_line("Please paste a valid URL before downloading")
            return

        if not isinstance(mode, str):
            log.write_line("Please select a download format first.")
            return

        bar.update(self._render_bar(0.0))
        pct.update(self._render_pct(0.0, eta="--:--"))
        button.disabled = True

        log.write_line("")
        log.write_line("Getting things ready...")
        log.write_line(f"URL: {url}")
        log.write_line(f"Selected format: {mode}")
        self._cancel_download.clear()

        self._download_worker = self.run_worker(
            self.do_download(url, mode),
            exclusive=True,
        )

    async def do_download(self, url: str, mode: str) -> None:

        def progress_hook(data):
            self.call_from_thread(self.update_progress, data)

        self._last_logged = -10.0
        self._progress_files = {}
        try:
            result = await asyncio.to_thread(
                download,
                url,
                mode,
                progress_hook,
                self._cancel_download,
            )

            if result == 0:
                self.query_one("#log", Log).write_line(
                    "The Download was completed successfully",
                )
                self.reset_interface(True)
            else:
                self.query_one("#log", Log).write_line(
                    "Download failed. Check URL or try again.",
                )
                self.reset_interface(False)

        except Exception as error:
            self.query_one("#log", Log).write_line(
                f"Something went wrong. Error: {error}",
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
                    raw = data.get("_percent_str", "0%").strip().replace("~", "").strip().strip("%")
                    percentage = float(raw)
                except ValueError:
                    percentage = None

            if percentage is not None:
                if percentage > 100:
                    percentage = 100
                self.query_one("#bar", Static).update(
                    self._render_bar(percentage)
                )
                self.query_one("#pct", Static).update(
                    self._render_pct(percentage, data.get("_eta_str", "").strip())
                )

                if percentage - self._last_logged >= 5.0:
                    self._last_logged = percentage
                    percent = data.get("_percent_str", "").strip()
                    eta = data.get("_eta_str", "").strip()

                    self.query_one("#log", Log).write_line(
                        f"Downloading: {percent} | Time Left: {eta}"
                    )

        elif data.get("status") == "finished":
            self.query_one("#log", Log).write_line(
                "Download complete. Processing the file..."
            )

    def reset_interface(self, success: bool) -> None:

        if success:
            self.query_one("#bar", Static).update(self._render_bar(100.0))
            self.query_one("#pct", Static).update(self._render_pct(100.0, "--:--"))
        self.query_one("#go", Button).disabled = False

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