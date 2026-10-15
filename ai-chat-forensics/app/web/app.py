"""Local Flask app: upload one or more session files, parse them in memory,
render them. Nothing is written to disk, a database, or a log; nothing
leaves the machine."""

from __future__ import annotations

from flask import Flask, render_template, request

from parser import artifacts, workspace_hash
from parser.parse import parse_session

from . import view

MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # generous ceiling for a local, single-user tool


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.jinja_env.filters["timestamp"] = view.format_timestamp_ms
    app.jinja_env.filters["duration"] = view.format_duration_ms
    app.jinja_env.filters["time_short"] = view.format_time_short
    app.jinja_env.filters["datetime_short"] = view.format_datetime_short

    @app.get("/")
    def upload():
        return render_template("upload.html")

    @app.post("/")
    def parse():
        uploaded_files = [f for f in request.files.getlist("session_file") if f and f.filename]
        if not uploaded_files:
            return render_template("upload.html", error="Choose at least one .jsonl file first.")

        sessions = []
        errors = []
        for uploaded in uploaded_files:
            filename = uploaded.filename
            raw = uploaded.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{filename}: not valid UTF-8 text.")
                continue

            parsed = parse_session(text, filename)
            sessions.append({
                "session_data": parsed,
                "header": view.build_header_summary(parsed),
                "rows": view.build_session_view(parsed),
                "artifacts": artifacts.build_session_artifacts(parsed),
            })

        if not sessions:
            return render_template("upload.html", error=" / ".join(errors))

        return render_template("sessions.html", sessions=sessions, errors=errors)

    @app.route("/tools/workspace-hash", methods=["GET", "POST"])
    def workspace_hash_tool():
        path = request.form.get("path", "").strip() if request.method == "POST" else ""
        os_type = request.form.get("os_type", "windows") if request.method == "POST" else "windows"
        ctime_ms_raw = request.form.get("ctime_ms", "") if request.method == "POST" else ""
        inode_raw = request.form.get("inode", "") if request.method == "POST" else ""

        variants = None
        if request.method == "POST" and path:
            variants = workspace_hash.compute_variants(
                path, os_type, _to_int(ctime_ms_raw), _to_int(inode_raw)
            )

        return render_template(
            "workspace_hash.html",
            variants=variants, path=path, os_type=os_type,
            ctime_ms=ctime_ms_raw, inode=inode_raw,
        )

    return app


def _to_int(raw: str) -> int | None:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return None
