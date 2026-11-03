"""
serve.py — start a local web server for the Typical Orange Cats page, and open it.

Run it any of these ways:
    double-click  "Open viz.bat"   (in this folder)
    python viz_d3/serve.py         (from the Orange_Braincells folder)
    python serve.py                (from this folder)
Keep the window open while you use the page; close it (or press Ctrl+C) to stop the server.
If the page ever stops loading, close the window and start it again.

Why a server at all: the page loads its data and the cat kit with d3.json / d3.xml, and browsers
refuse those requests for pages opened straight from disk (file://).

Why this script rather than `python -m http.server`:
  - it always serves the Orange_Braincells folder, wherever it is started from, so the page can
    reach ../oobc_archive and ../SVG;
  - it tells the browser that .js files are JavaScript. On some Windows setups Python reads the
    .js type from the registry as "text/plain", and browsers then refuse to run the page's modules;
  - if port 8000 is taken, it tries the next few ports;
  - it opens the page in your browser.
"""
import functools
import http.server
import os
import webbrowser

# The folder above this one (Orange_Braincells): the page's data and kit paths start there.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRST_PORT = 8000
PORTS_TO_TRY = 10


class Handler(http.server.SimpleHTTPRequestHandler):
    # File types, set here so they never depend on the computer's settings.
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".html": "text/html",
    }

    # Don't print a line for every file served. On Windows, clicking inside the server's window
    # pauses it the next time it prints (the console's text-selection mode), which freezes the
    # page mid-load. With nothing printed per request, a stray click can't stop the server.
    def log_message(self, format, *args):
        pass

    # Always fetch fresh files, so edits show on reload.
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def start_server():
    handler = functools.partial(Handler, directory=ROOT)
    for port in range(FIRST_PORT, FIRST_PORT + PORTS_TO_TRY):
        try:
            return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler), port
        except OSError:
            continue  # port in use: try the next one
    raise SystemExit(f"Ports {FIRST_PORT}-{FIRST_PORT + PORTS_TO_TRY - 1} are all in use.")


if __name__ == "__main__":
    server, port = start_server()
    url = f"http://localhost:{port}/viz_d3/"
    print(f"Serving {ROOT}")
    print(f"Open {url}   (add ?check to run the parity checks)")
    print("Keep this window open while you use the page. Ctrl+C or close the window to stop.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
