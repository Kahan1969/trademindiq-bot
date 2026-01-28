import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, Any, Tuple, Optional


class _ControllerHandler(BaseHTTPRequestHandler):
    # injected by start_dashboard_server
    payload_provider: Optional[Callable[[], Dict[str, Any]]] = None
    url_path: str = "/status"

    def log_message(self, *args, **kwargs):
        # silence default HTTPServer logging
        return

    def do_GET(self):
        if self.path != self.url_path:
            self.send_response(404)
            self.end_headers()
            return

        payload: Dict[str, Any] = {}
        if callable(self.payload_provider):
            try:
                payload = self.payload_provider() or {}
            except Exception:
                payload = {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


def start_dashboard_server(
    bind: Tuple[str, int] = ("127.0.0.1", 8787),
    url_path: str = "/status",
    payload_provider: Optional[Callable[[], Dict[str, Any]]] = None,
) -> None:
    """
    Starts a tiny HTTP server in a daemon thread.
    Companion dashboard can call: http://127.0.0.1:8787/status
    """
    _ControllerHandler.payload_provider = payload_provider
    _ControllerHandler.url_path = url_path

    server = HTTPServer(bind, _ControllerHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

