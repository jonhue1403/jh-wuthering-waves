"""Independent, loopback-only, read-only Farming Assistant browser server.

OK Script 3 does not include WebCustomTab. This process intentionally imports
neither OK Script nor game input/session modules; it exposes only two read-only
operations on the existing FarmingAssistantView. Never bind it to a public NIC.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
import webbrowser

from src.automation.farming_view import FarmingAssistantView


_ASSETS = Path(__file__).resolve().parents[1] / "web" / "farming_assistant"
_STATIC = {
    "/": ("standalone.html", "text/html; charset=utf-8"),
    "/assets/standalone.js": ("standalone.js", "text/javascript; charset=utf-8"),
    "/assets/index.js": ("index.js", "text/javascript; charset=utf-8"),
    "/assets/standalone.css": ("standalone.css", "text/css; charset=utf-8"),
}
_QUERY_KEYS = {
    "/api/targets": frozenset(("kind", "query")),
    "/api/preview": frozenset(("kind", "target_id", "desired_total")),
}
_CSP = (
    "default-src 'none'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
    "object-src 'none'"
)


class FarmingWebServer(HTTPServer):
    """A single-threaded local preview server; never a gameplay controller."""

    def __init__(self, view: FarmingAssistantView | None = None, port: int = 0):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Invalid local port")
        self.view = view if view is not None else FarmingAssistantView()
        super().__init__(("127.0.0.1", port), FarmingWebHandler)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"


class FarmingWebHandler(BaseHTTPRequestHandler):
    """Strict same-origin GET handler, with explicit routes and bounded input."""

    server: FarmingWebServer
    server_version = "FarmingAssistant"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format: str, *args: object) -> None:
        # Never log query strings, source IDs, absolute paths or private data.
        return

    def _reply(self, status: int, body: bytes, content_type: str,
               *, allow: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", _CSP)
        if allow is not None:
            self.send_header("Allow", allow)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status: int, obj: object, *, allow: str | None = None) -> None:
        data = json.dumps(obj, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
        self._reply(status, data, "application/json; charset=utf-8", allow=allow)

    def _allowed_request(self) -> bool:
        if len(self.headers) > 40 or len(self.headers.as_bytes()) > 8192:
            self._json(431, {"error": "Request headers too large"})
            return False
        hosts = self.headers.get_all("Host", [])
        if hosts != [f"127.0.0.1:{self.server.server_port}"]:
            self._json(403, {"error": "Invalid local host"})
            return False
        origins = self.headers.get_all("Origin", [])
        if origins and origins != [self.server.base_url]:
            self._json(403, {"error": "Cross-origin access forbidden"})
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site == "cross-site":
            # A user can follow a launch link from another site into this
            # harmless application shell. Keep cross-site API/data requests
            # blocked; only permit a top-level GET of the exact landing page.
            top_level_landing = (
                self.command == "GET" and self.path == "/"
                and self.headers.get("Sec-Fetch-Mode") == "navigate"
                and self.headers.get("Sec-Fetch-Dest") == "document"
                and not origins
            )
            if not top_level_landing:
                self._json(403, {"error": "Cross-site access forbidden"})
                return False
        elif fetch_site not in (None, "same-origin", "none"):
            self._json(403, {"error": "Cross-site access forbidden"})
            return False
        if self.headers.get("Transfer-Encoding") is not None:
            self._json(400, {"error": "Request body not supported"})
            return False
        length = self.headers.get("Content-Length")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or int(length) != 0):
            self._json(400, {"error": "Request body not supported"})
            return False
        return True

    @staticmethod
    def _params(raw: str, allowed: frozenset[str]) -> dict[str, str]:
        if len(raw) > 1800:
            raise ValueError("Query too long")
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=4, encoding="utf-8", errors="strict")
        if len({name for name, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate query parameter")
        if any(name not in allowed for name, _ in pairs):
            raise ValueError("Unknown query parameter")
        if any("\x00" in value or "\x00" in key for key, value in pairs):
            raise ValueError("Invalid query parameter")
        return dict(pairs)

    def do_GET(self) -> None:
        if not self._allowed_request():
            return
        if len(self.path) > 2048:
            self._json(414, {"error": "Request target too long"})
            return
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.fragment or "%" in parsed.path:
            self._json(400, {"error": "Invalid request target"})
            return
        if parsed.path in _QUERY_KEYS:
            try:
                params = self._params(parsed.query, _QUERY_KEYS[parsed.path])
                if parsed.path == "/api/targets":
                    response = self.server.view.targets(
                        params.get("kind", "material"), params.get("query", ""))
                else:
                    response = self.server.view.preview(
                        params.get("kind", "material"),
                        params.get("target_id", ""),
                        params.get("desired_total"))
            except (ValueError, UnicodeError):
                self._json(400, {"error": "Invalid Farming Assistant query"})
                return
            except Exception:
                # Do not leak private evidence filesystem details via HTTP.
                self._json(500, {"error": "Preview unavailable"})
                return
            try:
                self._json(200, response)
            except (TypeError, ValueError):
                self._json(500, {"error": "Preview unavailable"})
            return
        if parsed.path not in _STATIC or parsed.query:
            self._json(404, {"error": "Not found"})
            return
        filename, content_type = _STATIC[parsed.path]
        try:
            path = _ASSETS / filename
            if path.is_symlink() or not path.is_file():
                raise OSError("Asset unavailable")
            # Exact allowlisted filenames, never a request-derived filesystem path.
            if path.stat().st_size > 256 * 1024:
                raise OSError("Asset too large")
            data = path.read_bytes()
            if len(data) > 256 * 1024:
                raise OSError("Asset too large")
        except OSError:
            self._json(500, {"error": "Asset unavailable"})
            return
        self._reply(200, data, content_type)

    def do_HEAD(self) -> None:
        self._json(405, {"error": "Method not allowed"}, allow="GET")

    def do_POST(self) -> None:
        self._json(405, {"error": "Method not allowed"}, allow="GET")

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
    do_OPTIONS = do_POST


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local Farming Assistant")
    parser.add_argument("--port", type=int, default=0,
                        help="Local TCP port, 0 selects an available port")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open a browser automatically")
    args = parser.parse_args(argv)
    with FarmingWebServer(port=args.port) as server:
        print(f"Farming Assistant preview: {server.base_url}", flush=True)
        print("Local read-only preview. Ctrl+C stops the server.", flush=True)
        if not args.no_browser:
            webbrowser.open(server.base_url)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0
