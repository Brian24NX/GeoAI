"""Serve the chip-check sheet and save every answer to answers.json.

The browser pane's own storage is wiped when the app stops the preview
server (6 Nov 2026: Brian's first pass was lost that way). So each click is
also posted here and written to disk, and the page reloads its answers from
that file.

    python3 chip_check/serve.py 8766
"""
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "answers.json"
LABELS = {"V", "O", "H", "?"}
N_CHIPS = len(json.loads((HERE / "chips.json").read_text()))


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", 0))
        if not 0 < size <= 4096:
            self.send_error(413)
            return
        try:
            answers = json.loads(self.rfile.read(size))
            ok = isinstance(answers, dict) and all(
                k.isdigit() and 1 <= int(k) <= N_CHIPS and v in LABELS
                for k, v in answers.items())
        except (ValueError, AttributeError):
            ok = False
        if not ok:
            self.send_error(400)
            return
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(sorted(answers.items(), key=lambda kv: int(kv[0]))), indent=1) + "\n")
        tmp.replace(OUT)
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(HERE)))
    print(f"chip check on http://127.0.0.1:{port}/chip_check.html, answers -> {OUT}", flush=True)
    server.serve_forever()
