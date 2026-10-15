# ai-chat-forensics

Research into the session files written by GitHub Copilot Chat in VS Code (`chatSessions/*.jsonl`), toward a community forensic reference: a blog post (0xh4lpy.medium.com) and a GitHub repo with a parser.

**Status:** investigating the structure. The parser is deliberately not started until the format is understood and the experiments are done.

## Contents

| File | What |
|---|---|
| `README.md` | This file: basic project info |
| `notes.md` | All findings, hypotheses, experiments checklist, open questions, resources |
| `ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl` | Test session (VS Code 1.132.0, Copilot Chat 0.60.0, agent mode, auto model) |
| `shape.py` to `shape5.py` | Probe scripts that print structure only, never content |

## Rules

- Only synthetic or fully sanitised data goes into anything published. No real prompts, paths, usernames or case data.
- Every claim in `notes.md` is labelled observed, source or hypothesis, with the VS Code and extension versions it was tested on.
- Confirm I'm cleared to publish before anything leaves this folder.
