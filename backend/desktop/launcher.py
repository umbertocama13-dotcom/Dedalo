"""Entry point of the desktop app.

Starts the backend on a free port of 127.0.0.1 in a background thread and opens a
native window (pywebview, Edge WebView2 on Windows) on it. Closing the window stops
the server. With --browser the default browser is used instead of the window, to try
the app on a system without WebView2.
"""

import argparse
import html
import logging
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.main import create_app
from app.services.embeddings.base import Embedder
from desktop.database import prepare_database
from desktop.instance_lock import InstanceLock
from desktop.paths import DesktopPaths, get_paths
from desktop.user_config import ensure_env_file, load_settings

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Dedalo"
STARTUP_TIMEOUT_SECONDS = 120
PAGE_STYLE = "font-family:system-ui,sans-serif;display:grid;place-items:center;height:90vh;color:#1d2330"
LOADING_PAGE = f"<body style='{PAGE_STYLE}'><div><h1>Dedalo</h1><p>Avvio in corso...</p></div></body>"


def main(argv: list[str] | None = None) -> int:
    """Runs the desktop app until its window is closed.

    Args:
        argv: Command line arguments; defaults to sys.argv.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(prog="dedalo", description="Dedalo desktop app")
    parser.add_argument("--browser", action="store_true", help="open the default browser instead of the app window")
    args = parser.parse_args(argv)

    paths = get_paths()
    _redirect_missing_console(paths.log_file)

    lock = InstanceLock(paths.lock_file)
    if not lock.acquire():
        _show_message("Dedalo è già aperto su questo computer.")
        return 1
    try:
        ensure_env_file(paths.env_file)
        if args.browser:
            return _run_in_browser(paths)
        return _run_in_window(paths)
    finally:
        lock.release()


def start_server(paths: DesktopPaths, embedder: Embedder | None = None) -> tuple[uvicorn.Server, threading.Thread, str]:
    """Prepares the database and starts the backend in a daemon thread.

    Args:
        paths: Paths of the installation.
        embedder: Optional embedder; tests pass a fake instead of the ONNX model.

    Returns:
        The server, its thread and the URL of the app.
    """
    port = find_free_port()
    settings = load_settings(paths, port)
    if prepare_database(paths, settings):
        logger.info("Created a new database in %s", paths.database_file)
    app = create_app(settings, embedder=embedder, static_dir=paths.frontend_dist)

    # log_config=None keeps the logging configured by create_app() instead of uvicorn's own.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None))
    thread = threading.Thread(target=server.run, name="dedalo-server", daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}/"


def wait_until_ready(server: uvicorn.Server, thread: threading.Thread, timeout: float) -> bool:
    """Waits until the server accepts requests (model loaded, embeddings warmed up).

    Args:
        server: Server started by start_server.
        thread: Thread running the server.
        timeout: Maximum seconds to wait.

    Returns:
        True if the server started, False if it failed or took too long.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.1)
    return False


def stop_server(server: uvicorn.Server, thread: threading.Thread) -> None:
    """Asks the server to stop and waits a few seconds for it.

    Args:
        server: Running server.
        thread: Thread running the server.
    """
    server.should_exit = True
    thread.join(timeout=10)


def find_free_port() -> int:
    """Returns a TCP port currently free on 127.0.0.1.

    A fixed port could be taken by another program; port 0 lets the system choose.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _run_in_window(paths: DesktopPaths) -> int:
    """Opens the native window and serves the app inside it."""
    import webview

    # WebView2 blocks downloads unless allowed: the CSV export and template need them.
    webview.settings["ALLOW_DOWNLOADS"] = True
    window = webview.create_window(WINDOW_TITLE, html=LOADING_PAGE, width=1280, height=800, min_size=(900, 600))
    running: dict[str, tuple[uvicorn.Server, threading.Thread]] = {}

    def start_and_show() -> None:
        # Runs in a pywebview worker thread, so the window shows "Avvio in corso" meanwhile.
        try:
            server, thread, url = start_server(paths)
        except Exception as error:
            logger.exception("Dedalo could not start")
            window.load_html(_error_page(str(error), paths.log_file))
            return
        running["server"] = (server, thread)
        if wait_until_ready(server, thread, STARTUP_TIMEOUT_SECONDS):
            window.load_url(url)
        else:
            window.load_html(_error_page("il server non si è avviato", paths.log_file))

    webview.start(start_and_show)
    if "server" in running:
        stop_server(*running["server"])
    return 0


def _run_in_browser(paths: DesktopPaths) -> int:
    """Serves the app and opens it in the default browser until Ctrl+C."""
    server, thread, url = start_server(paths)
    if not wait_until_ready(server, thread, STARTUP_TIMEOUT_SECONDS):
        print(f"Dedalo could not start: see {paths.log_file}", file=sys.stderr, flush=True)
        return 1
    # flush: when the output goes to a pipe or a file it is buffered, and whoever waits for
    # this line (a script, a log reader) would not see it until the app exits.
    print(f"Dedalo is running at {url} (data in {paths.data}). Press Ctrl+C to stop.", flush=True)
    webbrowser.open(url)
    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        stop_server(server, thread)
    return 0


def _redirect_missing_console(log_file: Path) -> None:
    """Sends output to the log file when the app runs without a console.

    A PyInstaller app built without console has sys.stdout and sys.stderr set to None,
    and uvicorn and logging fail as soon as they try to write to them.

    Args:
        log_file: File receiving the output.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    # Line buffering: each log line reaches the file immediately, even if the app is killed.
    stream = open(log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - kept open for the process lifetime
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _show_message(text: str) -> None:
    """Shows a message box on Windows, prints it elsewhere."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, WINDOW_TITLE, 0x40)
    else:
        print(text, file=sys.stderr)


def _error_page(reason: str, log_file: Path) -> str:
    """Builds the page shown in the window when the app cannot start."""
    return (
        f"<body style='{PAGE_STYLE}'><div><h1>Dedalo non si è avviato</h1>"
        f"<p>Motivo: {html.escape(reason)}</p><p>Dettagli nel file: {html.escape(str(log_file))}</p></div></body>"
    )
