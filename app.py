import asyncio, pyperclip, threading
from textual.app import ComposeResult, App
from textual.widgets import Select, ProgressBar, Log, Button, Input, Header, Footer, Static
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
    #bar {
      width: 80%;
      height: 3;
      margin: 1 0;
      border: solid gray;
    }
    #mode {
      width: 80%;
      margin: 0 0 1 0;
    }
"""

    _last_logged: float = -10.0

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

        yield ProgressBar(total=100, id="bar")
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
        bar = self.query_one("#bar", ProgressBar)

        if not url:
            log.write_line("Please paste a valid URL before downloading")
            return

        if not isinstance(mode, str):
            log.write_line("Please select a download format first.")
            return

        bar.update(progress=0)
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

            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )

            downloaded = data.get("downloaded_bytes", 0)
            percentage = None

            if total:
                percentage = downloaded / total * 100
            else:
                try:
                    percentage = float(
                        data.get("_percent_str", "0%").strip().strip("%")
                    )
                except ValueError:
                    percentage = None

            if percentage is not None:
                self.query_one("#bar", ProgressBar).update(
                    progress=percentage
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
            self.query_one("#bar", ProgressBar).update(progress=100)
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

if __name__ == "__main__":
    EveryDL().run()