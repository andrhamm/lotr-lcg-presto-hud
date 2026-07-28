"""Static dev server for the web twin that never lets the browser cache.

`python3 -m http.server` sends Last-Modified and nothing else, so the browser
is free to reuse an ES module it already has - and it does. Editing
docs/js/ui.js and reloading would leave the page running the OLD module,
which shows up as "the change didn't apply" or, worse, a blank screen when a
newly-imported symbol is missing from the stale copy. That wasted real review
time, so the dev server now forbids caching outright.

Only for local development. The Pages deploy serves docs/ as ordinary static
files and wants normal caching.
"""
import argparse
import http.server
import os


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_header(self, keyword, value):
        # Drop the validators too: with Last-Modified present a browser can
        # still revalidate into a 304 and keep its copy.
        if keyword in ("Last-Modified", "ETag"):
            return
        super().send_header(keyword, value)

    def log_message(self, fmt, *args):
        pass                                  # keep the preview log readable


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8642)
    ap.add_argument("--directory", default="docs")
    args = ap.parse_args()

    root = os.path.abspath(args.directory)
    handler = lambda *a, **kw: NoCacheHandler(*a, directory=root, **kw)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print("web twin (no-cache) on http://localhost:%d  serving %s" % (args.port, root))
    srv.serve_forever()


if __name__ == "__main__":
    main()
