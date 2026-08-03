#!/usr/bin/env python3
"""Serve the repo for development, with caching that can't go stale.

Like `python3 -m http.server`, but every response carries
`Cache-Control: no-cache`. That does NOT disable caching -- it tells the
browser to REVALIDATE its cached copy before each use (a conditional
request, answered 304 Not Modified with no body when the file hasn't
changed). On localhost that costs sub-millisecond per file and guarantees
an edit is always picked up on the next reload.

Why it exists: plain http.server sends no Cache-Control at all, so
browsers fall back to heuristic freshness -- typically 10% of the file's
time-since-modification. A module untouched for months can then be served
stale for days, with no request ever hitting the server. An ES-module app
is especially exposed: the import graph can't be cache-busted from
outside (imports are relative), so there is no query-string trick to
force a reload. This bit us twice: a stale grids.json, and a round of
testing that silently exercised an old interaction.js.

Usage:
    util/serve.py [port]        # default: $PORT if set, else 8000

Serves the repo root regardless of the current directory. The PORT
environment variable (used by launchers that assign a free port, such as
the Claude Code preview with "autoPort") is honored when no port argument
is given.
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8000

REPO_ROOT = Path(__file__).resolve().parent.parent


class NoStaleCacheHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that makes browsers revalidate every file."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get("PORT", DEFAULT_PORT))
    handler = partial(NoStaleCacheHandler, directory=str(REPO_ROOT))
    # ThreadingHTTPServer, because a module-graph load fires a burst of
    # parallel requests and a single-threaded server serializes them.
    with ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"Serving {REPO_ROOT} at http://localhost:{port} "
              f"(Cache-Control: no-cache)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
