import os
import sys

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    # Force unbuffered/line-buffered stdout: under some terminals (notably a
    # WSL shell whose stdout isn't a real tty to Python) output gets fully
    # buffered and nothing appears - including Werkzeug's own startup banner -
    # until the process exits, which looks exactly like a silent hang.
    sys.stdout.reconfigure(line_buffering=True)

    # Default to a single plain process: no debug/reloader. The reloader
    # respawns a child process on every change, which is needlessly heavy
    # (and has been flaky from a WSL shell against a /mnt/c path) for
    # someone just running the app. Set FAITH_DEBUG=1 for the auto-reload
    # loop during active development on this code.
    debug = os.environ.get("FAITH_DEBUG") == "1"

    # Bind to all interfaces, not just 127.0.0.1: when this runs inside WSL
    # and the browser is opened from Windows, 127.0.0.1-only binding can be
    # unreachable depending on WSL's network mode. Still only reachable from
    # this machine (and its own LAN) - never the open internet.
    app.run(host="0.0.0.0", port=5000, debug=debug, use_reloader=debug)
