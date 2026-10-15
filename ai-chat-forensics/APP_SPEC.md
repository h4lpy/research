# App spec: Copilot Chat session viewer

A static, client-side web app. A user drops one or more `.jsonl` session files; the app replays them and shows the session as a chat (AI on the left, user on the right) with every forensically relevant detail one click away. Built from the research in `notes.md` and `experiments/`.

## 1. Parser (`app/src/parser/`)

Input: file text and the original filename. Output: one JSON object (see "Output shape").

Replay
- Line 1 must be `kind:0` (initial snapshot, `v` = state). If not, warn "missing initial entry" (VS Code itself refuses such files) and continue from an empty state.
- `kind:1`: set value at path `k` (strings = object keys, numbers = array indexes; index equal to array length appends).
- `kind:2`: at array path `k`, if `i` is present truncate the array to `i` items first, then append the items of `v` (`v` may be absent = pure truncate).
- `kind:3`: delete at path `k`.
- Record, per applied op: line number, kind, path, `i`, and approximate size. Keep a provenance map `path -> [line numbers]`.
- Support "state at line N" (replay up to N) for the operations view. Cheap approach: replay once, store ops, replay again on demand.
- Blank last line is normal (trailing newline), not an error.
- Strings starting `[VS Code: value truncated for persistence` are a truncation marker: flag them.

Detections (each is a warning/note with the evidence, labelled observed/source/hypothesis as in the notes)
- Filename `<id>.jsonl` vs `sessionId` field: mismatch = renamed or copied.
- Session with zero requests (valid; file exists before any prompt).
- Request with `modelState.value` 0 and no `result` = incomplete / in-flight; a response ending mid-sentence is expected in that case.
- Many lines or a single `kind:0` holding many requests: note that compaction may have discarded earlier states (source: compaction replaces the log with one fresh snapshot after a threshold).
- Appended lines with no new request (e.g. `inputState.selectedModel` set): "written without a prompt" (experiment 05); do not treat as activity.
- Lines out of event order (a later line holding an earlier timestamp).
- Unknown `kind`, unknown response item kinds, unknown top-level fields.
- Multiple `extensionVersion` values in one session.

Derived facts per request (show the formula or source field, and the evidence label)
- Times (epoch ms UTC): `timestamp`, `responseTimestamp`, `timeSpentWaiting`, `modelState.completedAt`, round timestamps. `elapsedMs`, `result.timings.firstProgress/totalElapsed`. Session `creationDate`; gap creation to first prompt; idle gaps between requests.
- Models: `modelId` (e.g. `copilot/auto`), `result.metadata.resolvedModel`, per-round `modelId`, `autoModeResolution` (first request only), `inputState.selectedModel` (note: placeholder family on auto), `modelConfiguration` if present.
- Account: `inputState.selectedModel.metadata.auth.accountLabel`. Workspace: `baseUri.path`, `cwd`, attachment paths, `renderedGlobalContext` workspace folders.
- Mode: `modeInfo.kind`, `agent.id` (do not call `editsAgent` "edit mode"), `permissionLevel`.
- Tokens/cost: `promptTokens`, `completionTokens`, `outputBuffer`, `promptTokenDetails` (categories with percentages), `copilotCredits`, `result.details`.
- Attachments: `variableData.variables[]` (kind, name, id/URI) plus the embedded content in `renderedUserMessage` `<attachments>`; the attached text is as of prompt time.
- Rendered prompt: parse `result.metadata.renderedUserMessage` and `renderedGlobalContext` into sections: `<context>` (current date, terminals, Last Command, Cwd, Exit Code), `<editorContext>`, `<attachments>`/`<attachment id filePath>`, `<reminderInstructions>` (boilerplate, collapse by default), `<userRequest>`; global: `<environment_info>`, `<workspace_info>` (file tree), memory blocks. Items with `type: 3` / `cacheType` are cache markers, not content. Keep unparsed text if a section is unknown.
- Tool calls: response items `toolInvocationSerialized` (`toolId`, `toolCallId`, `isConfirmed.type`, `source`, messages, `toolSpecificData`), joined to `toolCallRounds[].toolCalls[]` (`name`, JSON-string `arguments`, `id` = `toolCallId` + `__vscode-<n>`) and `toolCallResults` (string, or a node tree whose text nodes should be flattened to text). `toolId` and round `name` are different strings for the same call (`copilot_readFile` / `read_file`). Join on the `call_...` part.
- Terminal calls: `commandLine.original/forDisplay`, `confirmation`, `cwd`, `terminalCommandState.timestamp`, `isBackground`.
- Edits: `textEditGroup` (uri, edits), `codeblockUri`, `editedFileEvents`.
- Tool ID suffix `__vscode-<n>`: show the number as a possible epoch-ms timestamp ("possible extension-host start time, hypothesis") and group tool calls by seed.
- Rounds: `phase` (`commentary`, `final_answer`), `toolInputRetry`. `statefulMarker` is opaque: show length only.
- Session: `customTitle` (arrives as its own `kind:1`), `initialLocation`, `version` (not a format discriminator), `hasPendingEdits`, `inputState` (mode, attachments, `inputText` draft, selections).

Output shape: `{ file: {name, size, sha256, lineCount}, session: {...}, requests: [...], ops: [...], warnings: [...], provenance: {...} }`. Every item carries `sourceLines`.

## 2. UI (`app/src/ui/`)

Layout: header summary, then tabs. Light/dark theme. Works on a laptop screen and in print.

Header (session summary): file name, size, SHA-256 (computed in the browser, for evidence integrity), session ID with filename-match badge, title, created time, request count, first/last prompt times, account, workspace(s), extension version(s), models used (selected vs resolved), mode(s), total tokens and credits, warning count.

Tab 1, Chat. User messages on the right, AI on the left, in request order by timestamp.
- Each request: user bubble (text, attachment chips with path, hover for the embedded content) and AI bubble(s) (markdown rendered safely: no raw HTML execution; links shown but not auto-opened).
- Between response text, tool cards: icon, `toolId`, human message, status, `isConfirmed.type` (with "meaning unconfirmed" note for values other than the ones documented), expandable arguments and result. Terminal cards show command, cwd, exit info if present, command timestamp.
- Per-request footer chips: time (UTC, with ms; toggle to local), duration (`elapsedMs`), model (resolved, with "auto" marker), tokens, credits, mode, source line numbers.
- "Details" drawer per request: Prompt context (parsed sections, `Last Command`/`Cwd`/`Exit Code`, editor file, attachments with full text, workspace tree), Token breakdown (stacked bar from `promptTokenDetails`), Timings (timeline of timestamp, firstProgress, round timestamps, completedAt), Raw JSON of the request with fields clickable to show the source line.
- Incomplete requests are marked "incomplete / in flight".
- Gaps between requests shown as dividers ("44 min idle").

Tab 2, Timeline. Single table of every timestamped event across the session, sorted by time: session created, each request sent, round start, tool call, terminal command run, completed, title set (no timestamp: shown as "unknown time, line N"), lines written without a prompt. Columns: UTC time, delta from previous, event, detail, line. Filter by type; export CSV/JSON.

Tab 3, Operations (log). Raw lines with decoded kind/path/`i`, grouped into probable save batches (hypothesis: consecutive lines on the same request). Slider or "replay to line N" showing the state at that point. Highlights lines whose timestamp order differs from line order.

Tab 4, Evidence. Everything an examiner would cite: identifiers (session, request, response IDs; note `result.metadata.responseId` differs from the request `responseId`), accounts, paths, files attached, commands run, models, times, warnings. Each with source line and evidence label. Print-friendly and "Export report" (HTML, self-contained) with the file hash, tool name/version and parse warnings.

Tab 5, Reference. The format summary and the labelled findings, so users can see why the app shows what it shows (generated from, or linking to, the research notes).

Other
- Drag-and-drop and file picker; multiple files at once with a session list. Handle files of tens of MB without freezing (parse in a Web Worker).
- Optional second input: a `workspace.json` next to the file, to show which folder the storage hash maps to; and an optional "verify workspace hash" tool: enter folder path and creation time (ms) to compute `md5(fsPath + ctime)` (Windows rule from experiment 02; Linux uses inode, remote folders hash the URI only).
- Redact mode: blur prompt/response text and paths for screenshots.
- Search across prompts, responses, commands, paths.
- Never fetch anything; links open only on user click.
- Accessibility basics: keyboard navigable, sufficient contrast, labels.

## 3. Test cases (from the experiments; synthetic data in `experiments/datasets/`)

- `eeba4cf4-...jsonl` (exp 01): 5 content lines; zero requests in line 1, request pushed in line 2; `customTitle` after the request; answer ends mid-sentence, `modelState.value` 0 and no `result` => request flagged incomplete; `autoModeResolution` shows resolved model `mai-code-1.1-flash`; account `h4lpy`; `creationDate` to first `timestamp` = 12.1 s; filename matches `sessionId`.
- `c0b4f2ea-...jsonl` (exp 03): 14 lines; two requests; request 0 patched by `kind:1` lines and its answer text arrives after completion fields (line order != event order); request 1 pushed whole; `elapsedMs` = `completedAt - timestamp`; `promptTokenDetails` percentages; `renderedUserMessage` parsed into `Last Command: mkdir datasets`, `Cwd`, `Exit Code: 0`, editor file; `renderedGlobalContext` workspace tree on request 0 only; `customTitle` before the request push.
- `c0b4f2ea-..._with_file.jsonl` (exp 04): first 14 lines identical to the exp 03 file; line 15 adds a third request 44 min later; attachment in `variableData` and embedded text in `<attachments>`; a `copilot_readFile` tool call joined to round tool call `read_file` and to a node-tree result flattened to `# Experiments`; tool ID seed 1792049432767 shown as 2026-10-15 07:30:32.767 UTC (hypothesis marker); no `autoModeResolution` on later requests.
- Experiment 05 (once the full file is added to `datasets/`): a trailing `kind:1` setting `inputState.selectedModel` with `modelConfiguration` => "written without a prompt".
- `ea2c0634-...jsonl` (first sample, 47 lines, 7 requests, 0.60.0): replay with `kind:2` + `i` (lines 32 and 42), terminal tool calls with `terminalCommandState.timestamp`, `isConfirmed.type` 1 and 4, `toolCallResults` as strings and node trees, `textEditGroup` edits. Replay must produce 7 requests with no errors.
- Robustness: a corrupted middle line (warn, continue), a file without a `kind:0` first line, an empty file, a very long line, an unknown response item kind, a truncation-marker string.

## 4. Build order

1. Parser + tests against the datasets (no UI).
2. Chat view and header, using a plain drag-and-drop page.
3. Details drawer (prompt context, tokens, timings, attachments).
4. Timeline and Operations tabs.
5. Evidence tab and report export.
6. Worker parsing, search, redact mode, workspace hash tool.
7. Static build (`npm run build`) that opens from `file://` or any static host; document it in `app/README.md`.

## 5. Out of scope for now

Other storage locations (`transcripts`, `debug-logs`, `chatEditingSessions`, `session-store.db`, `state.vscdb`); other editors; older `.json` (pre-1.109) sessions beyond a best-effort import with a warning; any server component.
