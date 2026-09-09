"""A tiny zero-dependency HTTP framework.

The game ships with no third-party packages: this module provides just enough
routing, JSON handling and static file serving for the presentation layer.
"""
import inspect
import json
import mimetypes
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


class HTTPError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _jsonable(obj):
    """Best-effort conversion of sqlite rows / sets / dates to JSON-safe data."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "keys") and hasattr(obj, "__getitem__"):
        try:
            return {str(k): _jsonable(obj[k]) for k in obj.keys()}
        except Exception:
            pass
    return str(obj)


def _coerce(value, want):
    if want is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if want is int:
        try:
            return int(float(value))
        except Exception:
            return 0
    if want is float:
        try:
            return float(value)
        except Exception:
            return 0.0
    return value if value is not None else ""


class MiniApp:
    def __init__(self, static_dir=None, static_prefix="/static"):
        self.routes = {"GET": [], "POST": []}
        self.static_dir = static_dir
        self.static_prefix = static_prefix

    # ------------------------------------------------------------ registration
    def _add(self, method, path, fn):
        names = re.findall(r"\{(\w+)\}", path)
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path) + "$")
        self.routes[method].append((regex, names, fn))
        return fn

    def get(self, path):
        return lambda fn: self._add("GET", path, fn)

    def post(self, path):
        return lambda fn: self._add("POST", path, fn)

    # ---------------------------------------------------------------- dispatch
    def call(self, method, path, query, body):
        for regex, names, fn in self.routes.get(method, []):
            m = regex.match(path)
            if not m:
                continue
            sig = inspect.signature(fn)
            kwargs = {}
            for k, v in m.groupdict().items():
                if k in sig.parameters:
                    kwargs[k] = _coerce(unquote(v), sig.parameters[k].annotation
                                        if sig.parameters[k].annotation is not inspect._empty else str)
            for k, p in sig.parameters.items():
                if k in kwargs:
                    continue
                if k in ("payload", "body"):
                    kwargs[k] = body if isinstance(body, dict) else {}
                    continue
                raw = query.get(k, [None])[0]
                default = p.default if p.default is not inspect._empty else None
                if raw is None:
                    if default is not None:
                        kwargs[k] = default
                    elif p.annotation in (int, float, bool, str):
                        kwargs[k] = _coerce("", p.annotation)
                    else:
                        kwargs[k] = None
                else:
                    want = p.annotation if p.annotation is not inspect._empty else type(default or "")
                    kwargs[k] = _coerce(unquote(raw), want if want in (int, float, bool, str) else str)
            return fn(**kwargs)
        return None

    def handle(self, method, path, query, body):
        """Returns (status, payload)."""
        try:
            res = self.call(method, path, query, body)
            if res is None:
                return 404, {"ok": False, "error": "Not found: %s" % path}
            return 200, _jsonable(res)
        except HTTPError as e:
            return e.status, {"ok": False, "error": e.detail, "detail": e.detail}
        except Exception as e:
            traceback.print_exc()
            return 500, {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    # ------------------------------------------------------------- static files
    def static_file(self, path):
        if not self.static_dir:
            return None
        if path.startswith(self.static_prefix):
            rel = path[len(self.static_prefix):].lstrip("/")
        else:
            # bare paths (/, /index.html, /favicon.ico) resolve from the static root
            rel = path.lstrip("/")
        if not rel:
            rel = "index.html"
        full = os.path.normpath(os.path.join(self.static_dir, rel))
        if not full.startswith(os.path.abspath(self.static_dir)) or not os.path.isfile(full):
            return None
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            return ctype, fh.read()


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Touchline/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, status, ctype, data, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _route(self, body=None):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/" or path == "":
                path = "/index.html"
            if path.startswith(app.static_prefix):
                got = app.static_file(path)
                if got:
                    return self._send(200, got[0], got[1])
                return self._send(404, "text/plain", b"not found")
            got = app.static_file(path) if app.static_dir else None
            if got:
                return self._send(200, got[0], got[1])
            query = parse_qs(parsed.query)
            status, payload = app.handle(self.command, path, query, body)
            data = json.dumps(payload).encode("utf-8")
            return self._send(status, "application/json", data,
                              {"Access-Control-Allow-Origin": "*"})

        def do_GET(self):
            self._route()

        def do_HEAD(self):
            self._route()

        def do_OPTIONS(self):
            self._send(204, "text/plain", b"",
                       {"Allow": "GET,POST,OPTIONS", "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                body = {}
            self._route(body)

    return Handler


def serve(app, host="0.0.0.0", port=8000):
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print("Touchline serving on http://%s:%d" % (host, port), flush=True)
    httpd.serve_forever()
