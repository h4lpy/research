# CLAUDE.md

Project: a forensic viewer for GitHub Copilot Chat session files (`chatSessions/*.jsonl`) written by VS Code. Research is done in this folder; the app is built in `app/` as a Python web app (local Flask/FastAPI server, not a hosted service) for parsing and reviewing real session files during an investigation, not just the synthetic research samples.

## Read these first, in this order

1. `README.md` – what this project is
2. `notes.md` – the conclusions (file format, field meanings, interpretation rules, hypotheses, open questions)
3. `experiments/README.md` – how each conclusion was established, with the dataset for it in `experiments/datasets/`
4. `APP_SPEC.md` – what to build

Do not start coding until you have read all four and the datasets. If the spec and the notes disagree, the notes win; tell the user.

## Evidence rules (the app is for forensic use, so accuracy matters more than polish)

- Every claim in the notes is labelled `[observed]`, `[source]` or `[hypothesis]`. Keep those labels in the app: anything that is a hypothesis must be shown as one (a "hypothesis" marker or tooltip), never as fact. Do not promote a hypothesis because it seems likely.
- Do not invent field meanings. If a field is not in the notes, show it as raw data and mark it "meaning unknown".
- Never assume line order is event order. Order by `timestamp`/`completedAt`, and show the line number separately.
- The file is a mutation log (`kind` 0 initial, 1 set, 2 push with optional `i` truncate-then-append, 3 delete). Replay it exactly as described in `notes.md`. Keep, for every value in the replayed state, the line number(s) that wrote it (provenance).
- Be fail-soft: on a bad line, record the line number and error, keep replaying, and show a warning. Do not silently skip and do not crash.
- Be version-tolerant: unknown fields and unknown response item kinds must render generically with the raw JSON, not be dropped. Record the Copilot Chat `extensionVersion` seen; the formats differ between versions.
- Never change the uploaded data. The app is read-only.

## Privacy rules

- The app is a **local** web app: a Python server process, opened in the user's own browser, not hosted, not multi-tenant, and must never make outbound network calls (no analytics, no external fonts/CDN/scripts, no telemetry, no "check for updates"). It binds to `0.0.0.0` (all interfaces) rather than strictly `127.0.0.1`, deliberately: the dev workflow for this project runs the server inside WSL with the browser in Windows, which needs that to be reachable. This still only reaches this machine and its own LAN, never the open internet — "local-only" means no outbound calls and no hosting, not a specific bind address. Add a test or lint check that fails on outbound HTTP calls (`requests`, `urllib.request`, `httpx`, raw sockets to non-localhost addresses) anywhere in `app/`, other than links the user clicks in their own browser.
- Uploaded/parsed session content lives in memory (or a per-run temp location the app itself controls) for the duration of use only. Never write session content to a database, a log file, or any persistent store; never print prompt/response content to server logs or stdout beyond what a failing test needs.
- This app will be used on **real case data** at runtime — that's its purpose. The restriction is about what goes in this git repo and what the app persists, not what a user may load into it: test/sample data committed to the repo (`experiments/datasets/`, the root `.jsonl`) stays synthetic only; real case data must never be committed or pasted into logs/issues. Do not ask the user for real data as a way to "try it out" — use the existing datasets for that.

## Engineering

- Python. A local Flask server serves the UI (Jinja2 templates) and a parse endpoint; pytest for tests. Keep the parser a pure library in `app/parser/` with no Flask/request imports, so it can be reused (CLI, other tools, a future rewrite). The web layer lives in `app/web/` (routes/templates/static assets).
- Write parser tests first, from the experiments (see "Test cases" in `APP_SPEC.md`), then the web layer.
- Keep the parser output a plain JSON-serialisable structure (dicts/lists/primitives) so it can be exported and handed to templates or an API response unchanged.
- Small commits, one concern each. Do not add dependencies without a reason; prefer few (stdlib + one web framework + pytest covers most of this).
- Update `notes.md` and `experiments/README.md` only when asked, or when the app reveals something the research got wrong (then tell the user, and mark it `[observed]` with the dataset used).

## Ask before

- Anything that sends data off the machine
- Treating a hypothesis as a fact in the UI
- Supporting a format not covered by the datasets (e.g. older `.json` sessions) beyond a best-effort import with a clear warning
