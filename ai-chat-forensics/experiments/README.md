# Experiments

Method, raw observations, datasets and the to-do list. Conclusions are copied into `../notes.md` once settled. Test environment unless stated: Windows 11, VS Code 1.132.0, GitHub Copilot Chat 0.59.0 (experiment 01) and 0.60.0 (earlier sample), agent mode, model picker on `auto`. Datasets contain test prompts only.

| # | Experiment | Status | Dataset |
|---|---|---|---|
| 01 | Session initialisation and one prompt | captured; re-copy after the response finishes | `datasets/eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl` |
| 02 | Delete workspace storage and reinitialise with the same folder | done | none |
| 03 | New session, two prompts | captured (complete session) | `datasets/c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl` |
| 04 | Attach a file with `+` and ask about it (same session, later) | captured | `datasets/c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl` |
| 05 | Restart VS Code and reopen the existing session (no prompt) | one line captured; full file copy needed | none yet |

## 01 Session initialisation and one prompt

**Found:** a session file exists before any prompt (empty `requests`), and the response is written in pieces, so a file can end mid-answer.

- [ ] Re-copy the dataset once the response has finished and compare it with the current copy (the current copy ends mid-sentence)

[chat initialisation](datasets/eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl)

Prompt: "Hello world, testing chat initialisation". Workspace `C:\dev\research`.

| Line | Op | What it shows |
|---|---|---|
| 1 | `kind:0` | Written when the session was created, **before any prompt**: `requests: []`, `pendingRequests: []`, `inputState` (mode, selected model, permission level). |
| 2 | `kind:2` at `["requests"]` | The first request is **pushed** as a separate line, not part of the snapshot. `modelState.value` is 0 (pending) and `response` holds only `mcpServersStarting`. No `result`, tokens or timings yet. |
| 3 | `kind:1` at `["customTitle"]` | The generated title ("Chat initialization test") arrives separately, before the response text. |
| 4 | `kind:2` at `["requests",0,"response"]` | `autoModeResolution`: `resolvedModel` `mai-code-1.1-flash`, `predictedLabel` `no_reasoning`, `confidence` 0.95. |
| 5 | `kind:2` at `["requests",0,"response"]` | First markdown chunk of the answer. It **stops mid-sentence** ("...help with the next "). |

Findings:
- **Timeline** (epoch ms, UTC): `creationDate` 2026-10-15 08:09:29.129; request `timestamp` 08:09:41.264, i.e. **12.1 s after the session was created** (the user typed the prompt). `responseTimestamp` is `timestamp` + 1 ms; `timeSpentWaiting` equals `responseTimestamp`. This refines the first sample, where all three were equal. So `creationDate` is session creation, not first-prompt time. [observed]
- **A file can exist with zero requests** (line 1 only). A session opened and never used still leaves a `.jsonl`. [observed]
- **Partial responses are persisted.** The file ends mid-sentence with `modelState.value` 0 and no `result`, so what is on disk can be an in-flight response. Whether this was a copy taken during streaming or the response was cut off is not recorded; re-copy the file once the response has finished and compare. [observed; cause unknown]
- **Auto model:** `inputState.selectedModel` shows `copilot/auto` with `family`/`version` `gpt-5-mini` (a placeholder for Auto), while the model actually used is `mai-code-1.1-flash` in `autoModeResolution`. Do not read the model from `selectedModel` for attribution. [observed]
- **Account attribution:** `inputState.selectedModel.metadata.auth.accountLabel` holds the GitHub account name (`h4lpy`). A cheap way to tie a session to an account. [observed]
- **Workspace path in the data:** the markdown item's `baseUri.path` is `/c:/dev/research/` (the workspace folder, lowercase drive), matching the folder whose hash is `211a3f...`. [observed]
- **IDs:** `sessionId` `eeba4cf4-74fa-417e-86ba-bf4990fe4c03` is a version-4 UUID (third group starts `4`, fourth starts `8`), like the first sample's. `requestId` and `responseId` are `request_<uuid>` / `response_<uuid>`. Random, no embedded time. [observed]
- **Filename check:** the dataset filename equals the `sessionId` field in line 1. [observed]
- **Open:** what accounts for the 12 s gap between creation and the first request (likely typing time)?

## 02 Delete workspace storage and reinitialise with the same folder

**Found:** the `<hash>` folder name is `md5(path + folder creation time)`, so it comes back identical; deleting it wipes all history for that workspace.

- [X] Delete `%APPDATA%\Code\User\workspaceStorage\<hash>` in Explorer and restart VS Code

`%APPDATA%\Code\User\workspaceStorage\<hash>` is computed with the folder path and `ctime`. If folder is remote (SSH or WSL), only folder path is used

```powershell
> $p  = 'C:\dev\research'
> $ms = [DateTimeOffset]::new((Get-Item $p).CreationTimeUtc).ToUnixTimeMilliseconds()
> $s  = $p.Substring(0,1).ToLower() + $p.Substring(1) + $ms
> $h  = [Security.Cryptography.MD5]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($s))
> "ctime(ms) = $ms"
ctime(ms) = 1792008626997
> ([BitConverter]::ToString($h) -replace '-','').ToLower()
211a3faf4e627877bf03f662f79cfec8
```

Observations [observed]:
- VS Code recreated the same folder name, so the name is deterministic for the workspace and not tied to session time. It is the storage folder, not a session: deleting it removed every session for the workspace.
- The calculation above matches the folder name, so the local-folder formula is confirmed on Windows. Formula source: [workspaces.ts](https://github.com/microsoft/vscode/blob/main/src/vs/platform/workspaces/node/workspaces.ts) (`md5(fsPath + ctime)`; Windows uses creation time in ms rounded down, macOS creation time, Linux the inode; remote folders hash the URI string only). Read via a web fetch summary, so re-read the source before publishing.
  - **2026-10-15 correction:** this finding was briefly marked "retracted" after the app's workspace-hash tool was built and an attempt to re-verify it kept producing the wrong hash. Root cause found: the re-verification scripts themselves had a bug (an un-doubled backslash in a Python string literal got parsed as a carriage-return escape instead of a literal backslash, corrupting the test input before hashing), not the formula. Re-tested with no shell/heredoc escaping involved and the formula reproduces `211a3faf4e627877bf03f662f79cfec8` exactly, as originally recorded. The app's live Flask form (real HTTP input, no string-literal escaping) was unaffected by this bug throughout and always computed correctly.
- Recreated contents: `chatSessions\`, `chatEditingSessions\`, `state.vscdb`, `workspace.json`, plus folders for extensions that had run (`AndrePimeta.claude-code-chat`, `ms-python.python`).
- A recreated storage folder looks complete but holds no history. Likely signature of a wipe: the folder and its children are newer than the user's activity while sibling workspace folders are older.

`<sessionID>.jsonl` seems to be computed randomly. Both sample sessions have version-4 UUIDs (third group starts `4`, fourth starts `8` or `9`). The filename (<sessionId>.jsonl) should match the sessionId field inside the first line. A mismatch means the file was renamed or copied. That check is cheap to put in a parser.

`../hashcheck.py <folder>` recomputes the hash and prints variants (drive letter case, millisecond rounding).

Follow-ups:
- [ ] Check the Recycle Bin for the deleted folder (`$I` holds the original path and deletion time, `$R` the data) and whether VS Code opens a restored session
- [ ] Record creation times of the recreated folder and its children, and whether `state.vscdb` has an empty `chat.ChatSessionStore.index`
- [ ] Start a second chat in the same workspace: expect a second `.jsonl` under the same hash and a new `sessionId`
- [ ] Delete and recreate the project folder at the same path: expect a new hash (new creation time)
- [ ] Rename the project folder: expect a new hash (new path)
- [ ] Open the same project through WSL or SSH: expect a different hash (URI only, no ctime)

## 03 New session, two prompts

**Found:** line order is write order, not event order; each prompt stores the user's last terminal command, working directory and open file.

- [X] Create a new chat, send "Hello world", then "How's it going"

Dataset: [c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl](datasets/c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl). Copilot Chat 0.59.0, agent mode, `auto` (resolved to `mai-code-1.1-flash`), workspace `C:\dev\research`. 14 lines. [observed]

| Line | Op | What it shows |
|---|---|---|
| 1 | `kind:0` | Snapshot at creation, `requests: []`, no `customTitle`. |
| 2 | `kind:1` `customTitle` | Title "Hello world example". It comes **before** the request is pushed, the reverse of experiment 01. |
| 3 | `kind:2` `requests` | Request 0 pushed in its pending state: `modelState.value` 0, `response` = `mcpServersStarting` + `autoModeResolution`, no `result`. |
| 4-12 | `kind:1` `requests/0/<field>` | Completion fields set one at a time, in this order: `result`, `followups`, `modelState` (value 1, `completedAt`), `completionTokens`, `promptTokens`, `outputBuffer`, `promptTokenDetails`, `copilotCredits`, `elapsedMs`. |
| 13 | `kind:2` `requests/0/response` | The answer text, appended **after** the completion fields. |
| 14 | `kind:2` `requests` | Request 1 pushed **whole in one line**: `result`, `modelState` 1, tokens, credits, `elapsedMs` and the answer are all already in the pushed object. |

Findings:
- **Line order is write order, not event order.** The answer text (line 13) is written after the "completed" markers (lines 4-12), and the title can land before or after the request depending on the save. Never sort by line number; use timestamps. [observed, confirms the diff-log model]
- **A request can arrive pending-then-patched (request 0) or complete in one push (request 1).** A parser must handle both and must not assume a request line is final. Lines 4-13 look like one save, with property sets emitted before the array append. [observed; the one-save part is a hypothesis]
- **No `inputState` updates were written** (no `inputText` or `selections` lines, unlike the first sample). [observed]
- **Timing** (UTC): created 08:42:41.286; request 0 sent 08:42:52.460 (+11.2 s); completed 08:42:57.405; request 1 sent 08:43:10.709 (13.3 s after request 0 finished); completed 08:43:13.008.
  - `elapsedMs` = `modelState.completedAt` - request `timestamp`, exact for requests 0 and 1 (4945 ms, 2299 ms); within 1 ms for the third request in experiment 04 (7351 ms vs 7352 ms). [observed]
  - `result.timings.totalElapsed` is about 90-100 ms **shorter** than `elapsedMs` here (4847 vs 4945, 2210 vs 2299). In the first sample (with terminal commands) it was longer. The earlier "elapsedMs excludes approval wait" idea needs re-checking against that sample. [observed, hypothesis revised]
  - `result.timings.firstProgress` (4206 ms, 1741 ms) is the time to the first output.
  - The `toolCallRounds[].timestamp` (08:42:57.380) is about 25 ms before `completedAt`.
- **Cost of a trivial prompt:** `promptTokens` 30,450 and 30,996 for two short messages; `promptTokenDetails` says System Instructions 24%, **Tool Definitions 75%**, Messages 1%. `completionTokens` 16 and 22. So prompt size is not a measure of what the user typed. `copilotCredits` 0.41508 and 0.074208 (the `result.details` string rounds the first to "0.4 credits"); the second is much cheaper for a similar prompt (cause not known; caching is a guess). `outputBuffer` 128000.
- **The prompt context is stored, and it is evidence.** `result.metadata.renderedUserMessage` for each request holds, as the model saw it:
  - `<context>`: the current date, the open terminals (`Terminal: powershell` x2), **`Last Command: mkdir datasets`, `Cwd: C:\dev\research\ai-chat-forensics\experiments`, `Exit Code: 0`**
  - `<editorContext>`: the file open in the editor (`c:\dev\research\ai-chat-forensics\notes.md`)
  - `<reminderInstructions>`: long boilerplate that is the same in both requests
  - `<userRequest>`: the typed prompt
  
  The first request also has `renderedGlobalContext` with `<environment_info>` (OS), `<workspace_info>` (workspace folder and a **file tree**, truncated), and empty `<userMemory>`, `<sessionMemory>`, `<repoMemory>` blocks. Request 1 has none, and no `cacheKey` (which was `file:///c%3A/dev/research` on request 0). [observed]
  - Forensic value: a snapshot of the user's last terminal command and its exit code, working directory, open file and workspace contents at each prompt, independent of any tool call. It only reflects the state at the moment of the prompt.
  - The `type: 3` entries after each block (`cacheType: ephemeral`) are prompt-cache markers, not content. [observed; meaning inferred]
- **`result.metadata.responseId` differs from the request's `responseId`** (`97b1f6b2-...` vs `response_baa315e7-...`; the request one has a `response_` prefix). Do not join on them as if they were the same ID. [observed]
- `toolCallRounds[]` entries carry a large opaque `statefulMarker` (base64, over 1 KB) as well as `response`, `toolCalls`, `toolInputRetry` (0) and `id`. Meaning unknown. [observed]
- `autoModeResolution` confidence was 0.98 here and 0.95 in experiment 01. [observed]
- `agent.id` is `github.copilot.editsAgent` and `modeInfo.kind` is `agent`, as before.

Follow-ups:
- [ ] Parse `renderedUserMessage`: do the `<context>` fields change when a terminal command is run between prompts? Run a command, send a prompt, compare `Last Command` / `Exit Code`
- [ ] Does `<editorContext>` follow the focused editor tab, and what does it hold with a selection?
- [ ] Check `renderedGlobalContext` after adding files: is the file tree refreshed for later requests or only on the first?
- [ ] Re-check `elapsedMs` vs `totalElapsed` on the first sample (terminal approvals)

## 04 Attach a file with `+` and ask about it

**Found:** the session only appends, and an attached file's full text at prompt time is stored; the `__vscode-<n>` tool ID suffix looks like a start-time timestamp.

- [X] In the existing session (experiment 03), use `+` in the chat to attach `experiments/README.md` and send "just have a read at this file, return the first line"

Dataset: [c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl](datasets/c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl). Same session as experiment 03, 15 lines. Copilot Chat 0.59.0, `auto` resolved to `mai-code-1.1-flash`. [observed]

| Line | Op | What it shows |
|---|---|---|
| 1-14 | | **Byte-identical** to the experiment 03 dataset. |
| 15 | `kind:2` `requests` | The third request pushed **whole in one line** (19.6 KB), 2661 s (44 min) after the previous request completed. |

Findings:
- **Append only.** Reopening an existing session added one line and left lines 1-14 untouched. No repeated `kind:0`, no `customTitle` or `inputState` lines. [observed]
- **The attachment is recorded twice.**
  - `variableData.variables[]` has one item: `kind: "file"`, `name` (`README.md`), `id` (the file URI) and `value` (a URI object with `fsPath`, `external`, `path`, `scheme`). The prompt text and `message.parts` do not mention the file, so with the `+` menu the attachment is only visible here.
  - `result.metadata.renderedUserMessage` starts with `<attachments><attachment id="README.md" filePath="...">` followed by **the complete text of the file as it was when the prompt was sent** (10.4 KB message in total). A copy of attached content survives in the session even if the file is later changed or deleted. Whether large files are truncated is not tested.
- The `<context>`, `<editorContext>` (now the attached README as the current file), `<reminderInstructions>` and `<userRequest>` blocks follow. `<context>` still shows `Last Command: mkdir datasets` with the same `Cwd`, because no new command was run in between. No `renderedGlobalContext` and no `cacheKey` (first request only). [observed]
- **Tokens:** `promptTokens` 33,739 (up from about 31,000), and `promptTokenDetails` gains a **Files** category (6%): System Instructions 24%, Tool Definitions 68%, Messages 2%, Files 6%. `completionTokens` 76, `copilotCredits` 0.594476 (`details`: "MAI-Code-1.1-Flash • 0.6 credits"). [observed]
- **A tool call.** The model read line 1 of the file, although the file was already attached.
  - Response items: `mcpServersStarting`, markdown ("I'll read the first line..."), `toolInvocationSerialized`, markdown (the answer).
  - Tool item: `toolId` `copilot_readFile`, `isConfirmed.type` 1, `source` `{type: internal, label: Built-In}`, `invocationMessage` "Reading [](file:///...README.md#1-1), lines 1 to 1".
  - `toolCallRounds[0]`: `phase` `commentary`, tool call `name` **`read_file`** (different from the `toolId`), `arguments` a JSON **string** (`filePath`, `startLine`, `endLine`). `toolCallRounds[1]`: `phase` `final_answer`.
  - `toolCallResults` holds a node tree whose text is just the lines read (`# Experiments`), not the whole file.
- **No `autoModeResolution` item** in this request, nor in request 1 of experiment 03. It appeared only on the first request of each session (experiments 01, 03). Later requests record the model only in `result.metadata.resolvedModel` and the round `modelId`. [observed, 2 sessions]
- **Timing:** request `timestamp` 09:27:34.073; first round 09:27:39.709 (`firstProgress` 4895 ms); final round 09:27:41.403; `completedAt` 09:27:41.425. `elapsedMs` 7351, `totalElapsed` 7141. `responseTimestamp` = `timestamp` + 1 ms. [observed]
- **The `__vscode-<n>` suffix on tool call IDs looks like a timestamp, not a plain counter.** Here `call_YkS2...__vscode-1792049432767`: 1792049432767 ms = **2026-10-15 07:30:32.767 UTC**, about 2 h before the request. That is when VS Code was restarted for the storage-deletion test (message at 07:33). The first sample's IDs started at 1791964957947 = 2026-10-14 08:02:37.947, 4-5 s before its first request (08:02:42), and counted up by one per tool call. So the suffix is probably a counter seeded from the time the extension host (or window) started, which would show which VS Code run a tool call belongs to. [observed, mechanism hypothesis; verify with a second tool call in this window and after another restart]

Follow-ups:
- [ ] In this same window, make another request with a tool call: expect suffix `...768` (counter +1) if the counter hypothesis is right
- [ ] Restart VS Code, make a tool call: expect a new, later seed near the restart time
- [ ] Attach a large file (several hundred KB) and see whether `<attachment>` is truncated
- [ ] Attach a file, then edit or delete it, and compare `<attachment>` text with the current file
- [ ] Attach an image or a folder, and two files at once (`variableData.variables[]` for each)

## 05 Restart VS Code and reopen the existing session

**Found:** merely reopening a session appends a line (no prompt), so file modified time is not a last-activity time.

- [X] Restart VS Code, reopen the experiment 03/04 chat session, send nothing
- [ ] Copy the whole `.jsonl` as `datasets/c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_after_restart.jsonl`, plus its file modified time, so the new line can be checked in context

Only the new line was pasted, so it is not yet confirmed that this is the only change. [observed]

```jsonl
{"kind":1,"k":["inputState","selectedModel"],"v":{"identifier":"copilot/auto","metadata":{ ...same as the kind:0 snapshot... },"modelConfiguration":{"tier":"balance","tierSource":"default"}}}
```

Findings:
- **Reopening a session writes to its file with no prompt sent.** A `kind:1` line replaced `inputState.selectedModel`. So the file's modified time can change without any user chat activity, and **file mtime is not a "last prompt" time**. Use request `timestamp` and `modelState.completedAt` for that. [observed]
- The replacement value is identical to the `selectedModel` in the `kind:0` snapshot (checked against experiment 04's line 1, every key and value) **except for one new key, `modelConfiguration`: `{"tier": "balance", "tierSource": "default"}`**. [observed]
- `modelConfiguration` was not present when the session was created, so it was added by the restart (or the extension version/state at that time). `tierSource: "default"` suggests the tier could also come from a user setting or policy. The meaning of the `tier` values is unknown. [hypothesis]
- The line has **no timestamp**. Nothing inside the file dates the restart; only the file mtime or other artefacts (VS Code logs, the `state.vscdb` index) can. [observed]
- The update is an append of a `kind:1` set, not a rewritten snapshot: no second `kind:0`, so earlier lines stay. [observed, assuming it is the only new line]
- `inputState.selectedModel.metadata.auth.accountLabel` (`h4lpy`) is written again, so an account name can show up in lines other than the first. [observed]

Follow-ups:
- [ ] Take the full file copy and mtime, and diff it against `..._with_file.jsonl` (expect: 15 old lines identical, plus this one)
- [ ] Note the Copilot Chat version at the restart. Did the extension update, and does `modelConfiguration` appear only after an update?
- [ ] Reopen the session a second time with no changes: is another line written, or only when state changes?
- [ ] Restart and send a prompt: does the `__vscode-<n>` suffix on the next tool call show a new, later seed (experiment 04)?
- [ ] Change the model in the picker (not `auto`) and see how `selectedModel` and `modelConfiguration` change

## Queue

- [ ] Delete a request (last, then one from the middle): expect a push with `i`; check whether deleted content stays in earlier lines
- [ ] Force compaction with a long session: file should collapse to one `kind:0`; check what disappears
- [ ] Approve, edit, and decline a terminal command; try any "always allow" option
- [ ] Delay an approval by a known amount (about 30 s) and compare `elapsedMs` and `totalElapsed`
- [ ] Attach a file with `#file` in the prompt text and a code selection (the `+` menu attachment is done in experiment 04)
- [ ] Stop generation mid-response (`modelState.value`)
- [ ] Kill VS Code mid-response and see what reached disk
- [ ] Restart VS Code mid-session (does the call-ID counter reseed? does `kind:0` repeat?)
- [ ] Edit a file manually between turns (`editedFileEvents`)
- [ ] Pick a model manually and try ask and plan modes
- [ ] List the folders beside `chatSessions` (`transcripts`, `debug-logs`, `chatEditingSessions`)
