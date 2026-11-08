"""Serve the local canvas recorder and save its WebM output in docs/."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "scripts" / "record_walkthrough.html"
OUTPUT = ROOT / "docs" / "udyam-sathi-walkthrough.webm"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/record_walkthrough.html"):
            self.send_error(404)
            return
        body = PAGE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/save-video":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1024 or length > 100_000_000:
            self.send_error(413, "Unexpected recording size")
            return
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_bytes(self.rfile.read(length))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b"Saved")

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    print("Recorder ready at http://127.0.0.1:8765")
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
