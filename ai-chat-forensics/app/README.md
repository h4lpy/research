# ai-chat-forensics app

Parses GitHub Copilot Chat session files (`chatSessions/*.jsonl`) for forensic review. Python, local Flask server — see `APP_SPEC.md` in the repo root for the full plan; the parser (`app/parser/`) and the Chat view + header (`app/web/`) are built so far.

## Setup

**Windows (PowerShell):**
```
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**WSL / Linux / macOS:**
```
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Note `python3`/`pip3` outside the venv — Ubuntu (incl. WSL) doesn't ship a bare `python` command. Once the venv is activated, `python` inside it works fine (that's what `run.py` below expects).

## Run the web app

```
cd app
python run.py
```

Then open **http://127.0.0.1:5000/** in a browser and choose (or drag and drop) a `chatSessions/<sessionId>.jsonl` file. The server parses the upload in memory and writes nothing to disk, a log, or a database — closing the tab (or stopping `run.py` with Ctrl+C) discards it. There's no need to leave it running; start it again whenever you want to look at another session.

It binds to `0.0.0.0:5000` (all interfaces, still only reachable from this machine and its own LAN — never the open internet) specifically so that **running it inside WSL and opening the browser in Windows** (a common setup for this project) works without extra configuration; `http://127.0.0.1:5000/` or `http://localhost:5000/` from Windows reaches a server running in WSL this way.

By default there's no auto-reload: `python run.py` is one plain process, which is both simpler and more reliable from a WSL shell against a `/mnt/c/...` path than Werkzeug's reloader (which restarts in a child process on every file change and was flaky there). For active development on the app itself, `FAITH_DEBUG=1 python run.py` turns debug mode and auto-reload back on.

## Run the tests

```
cd app
python -m pytest
```

Tests read fixtures straight from `experiments/datasets/` and the root `*.jsonl` sample in the repo — nothing is copied into `app/`.

## Use the parser directly (without the web app)

```python
from parser.parse import parse_session

with open("some-session.jsonl", encoding="utf-8") as f:
    text = f.read()

result = parse_session(text, "some-session.jsonl")
print(result["session"])
print(len(result["requests"]), "requests")
print(result["warnings"])
```

`parse_session` takes the file's text and its filename, and returns one plain JSON-serialisable dict (`file`, `session`, `requests`, `ops`, `warnings`, `provenance`). It never touches the filesystem or the network itself — reading the `.jsonl` file is the caller's job.
