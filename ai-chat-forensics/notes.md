# Findings and notes

All findings live here. See README.md for project info. Update claims as experiments are run and keep the evidence label and tested versions on each one.

> Experiments (method, raw observations, datasets, to-do list) live in `experiments/README.md`. This file holds the conclusions.

## Evidence labels

- **[observed]** seen in my own test sample
- **[source]** stated in VS Code source or other public code
- **[hypothesis]** inferred, not yet tested

## Test environment

- VS Code 1.132.0, GitHub Copilot Chat 0.60.0, Windows 11, agent mode, model picker on `auto`
- One test session (47 lines, 7 requests): `ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl` in this folder
- Probe scripts `shape.py` to `shape5.py` print structure only, never content
- Only synthetic or fully sanitised data goes into anything published

## Where the files live

| Path (Windows) | What |
|---|---|
| `%APPDATA%\Code\User\workspaceStorage\<hash>\chatSessions\<sessionId>.jsonl` | Session log (this research) |
| `%APPDATA%\Code\User\globalStorage\emptyWindowChatSessions\` | Chats from windows with no folder open |
| `...\workspaceStorage\<hash>\workspace.json` | Maps `<hash>` back to the folder |
| `...\workspaceStorage\<hash>\state.vscdb` | Session index (`chat.ChatSessionStore.index`), metadata only. Index capped at 25 sessions [source, third-party] |

**The `<hash>` folder (workspace ID).** Deterministic for a workspace, not session-time based. It names the workspace storage folder, not a session; sessions are the `<sessionId>.jsonl` files inside `chatSessions`.
- Formula, from `src/vs/platform/workspaces/node/workspaces.ts`, `getSingleFolderWorkspaceIdentifier` ([workspaces.ts](https://github.com/microsoft/vscode/blob/main/src/vs/platform/workspaces/node/workspaces.ts); read via a web fetch summary, so re-read the source file before publishing). [source]
  - Local folder (`file` scheme): `md5( folderUri.fsPath + String(ctime) )`, where `ctime` is a salt taken from the folder's stat. If `ctime` is falsy only the path is hashed.
  - Windows: `ctime = Math.floor(birthtimeMs)` (creation time; the floor works around a Node precision issue). macOS: `birthtime.getTime()`. Linux: the **inode number**, because birthtime is unusable there.
  - Remote folder (non-`file` scheme, e.g. a WSL or SSH window): `md5( folderUri.toString() )` with no stat salt.
  - Case is not lowercased for single folders (`fsPath` as is). On Windows `fsPath` normally has a lowercase drive letter, such as `c:\dev\...`.
- Verified on Windows by recomputing the hash for the test folder (see experiments/README.md, experiment 02): `md5(fsPath + ctime)` with the drive letter lowercased reproduces `211a3faf4e627877bf03f662f79cfec8` for `C:\dev\research` + ctime `1792008626997`. [observed]
  - **2026-10-15 correction:** this was briefly and incorrectly marked "retracted" while building the app's workspace-hash tool, after an attempt to reproduce it kept failing. The failure was a bug in the ad-hoc test scripts used to check it, not in the formula: an un-doubled backslash in a Python string literal (`"...\\research"` typed as `"...\research"`) was silently parsed as the carriage-return escape `\r` instead of a literal backslash, corrupting the input before hashing. Re-tested cleanly (string built and hashed with no shell/heredoc escaping involved) and the formula reproduces the target hash exactly. The original `[observed]` finding stands.
- Consequences: the hash changes if the project folder is deleted and recreated (new birth time), and is unaffected by the contents of the storage folder. The same path on a different machine gives a different hash. This also explains the identical name after deleting the storage folder. [source + observed]
- The app's workspace-hash tool (`app/parser/workspace_hash.py`) implements this formula; it's what `hashcheck.py` was meant to become (that script was referenced in earlier notes but never actually committed to this repo).

Insiders uses `Code - Insiders`. To check next (not yet looked at): `GitHub.copilot-chat\transcripts\`, `GitHub.copilot-chat\debug-logs\`, `chatEditingSessions\`, `session-store.db`.

## File format

The file is an append log of diffs between saves, not an event stream. [source: `objectMutationLog.ts`]

| `kind` | Meaning | Shape |
|---|---|---|
| 0 | Initial snapshot (first line) | `{"kind":0,"v":{...}}` |
| 1 | Set value at path | `{"kind":1,"k":[...],"v":...}` |
| 2 | Push onto array | `{"kind":2,"k":[...],"v":[...],"i":N}` |
| 3 | Delete at path | `{"kind":3,"k":[...]}`, no `v` |

- `k` is a path: strings are object keys, numbers are array indexes. [observed, source]
- `i` on a push: remove everything after index `i`, then append `v`. `v` may be absent (pure truncate). [source; observed on two lines]
- Each save writes only differences from the last confirmed state. Several requests can appear in one push (a batch). Line order is write order, not event order. [source, observed]
- Compaction: after the entry count passes a threshold (class default 512; one PR description mentions 1024, unverified which applies), the file is replaced by one fresh `kind:0` snapshot. Earlier states, including deleted or overwritten content, are then gone. [source]
- VS Code's reader is fail-closed: a bad line or missing initial entry means the session won't open. A forensic parser should replay as far as it can and report the first bad line. [source]
- Oversized values: strings over 1 MiB (or 100 MiB total) are replaced by a `[VS Code: value truncated for persistence ...]` marker. [source]
- `version: 3` is the same in JSON and JSONL, so it does not identify the format. Use the file extension and first line. [observed]

## Fields seen in 0.60.0

**Session:** `version`, `creationDate`, `sessionId`, `initialLocation`, `responderUsername`, `hasPendingEdits`, `customTitle` (arrives as a separate `kind:1`), `requests[]`, `inputState` (`mode`, `selectedModel`, `inputText`, `selections`, `attachments`, `permissionLevel`).

**Request:** `requestId`, `timestamp`, `responseId`, `responseTimestamp`, `modelId`, `agent{...extensionVersion}`, `modeInfo{kind,isBuiltin,telemetryModeId,permissionLevel}`, `message{text,parts}`, `variableData.variables`, `response[]`, `modelState{value,completedAt}`, `promptTokens`, `completionTokens`, `promptTokenDetails`, `copilotCredits`, `elapsedMs`, `editedFileEvents`, `result{details,metadata,timings}`.

**`result.metadata`:** `resolvedModel`, `promptTokens`, `outputTokens`, `codeBlocks`, `renderedUserMessage`, `renderedGlobalContext` (first request only), `toolCallRounds[]`, `toolCallResults{}`, `agentId`, `sessionId`.

**Response item kinds:** markdown (no `kind`), `inlineReference`, `toolInvocationSerialized`, `textEditGroup`, `codeblockUri`, `undoStop`, `mcpServersStarting`, `progressTaskSerialized`, `autoModeResolution`.

**Tool invocation:** `toolId`, `toolCallId`, `isComplete`, `isConfirmed{type}`, `source`, `invocationMessage`, `pastTenseMessage`, `toolSpecificData`. Terminal calls add `commandLine{original,forDisplay}`, `confirmation`, `cwd`, `terminalCommandState{timestamp}`. Tool IDs seen: `copilot_createFile`, `copilot_replaceString`, `copilot_createDirectory`, `copilot_readFile`, `run_in_terminal`.

## Interpretation notes

- **`sessionId`** is a random version-4 UUID (seen in two sessions); it carries no time or workspace information. The `.jsonl` filename should equal the `sessionId` field in the first line; a mismatch means the file was renamed or copied. [observed; generator call in the source not fully confirmed]
- **`creationDate`** is when the session was created, not when the first prompt was sent (12.1 s earlier in experiment 01). A session with no prompts still produces a file, containing only the `kind:0` snapshot with `requests: []`. [observed]
- **Partial responses are persisted:** a file can end mid-response (`modelState.value` 0, no `result`). Treat a missing `result` as incomplete, not as an error. [observed]
- **Model attribution:** on `auto`, `inputState.selectedModel` holds a placeholder (`family`/`version` `gpt-5-mini`); the model actually used is in `autoModeResolution.resolvedModel` and later `result.metadata.resolvedModel`. [observed]
- **Account and workspace:** `inputState.selectedModel.metadata.auth.accountLabel` gives the GitHub account name; markdown items carry the workspace folder in `baseUri.path`. [observed]
- `timeSpentWaiting` equalled `responseTimestamp` in both samples; `responseTimestamp` was equal to `timestamp` in the first and 1 ms later in the second. [observed]
- **Prompt context is stored.** `result.metadata.renderedUserMessage` has `<context>` (date, open terminals, `Last Command`, `Cwd`, `Exit Code`), `<editorContext>` (the open file) and `<userRequest>`; the first request also has `renderedGlobalContext` (OS, workspace folders, a truncated file tree). Useful as a point-in-time snapshot of the user's terminal and editor state at each prompt. [observed, experiment 03, 0.59.0]
- **Line order is write order.** A request can be pushed pending and patched with `kind:1` lines (answer text can come last), or pushed whole in one line. Order by timestamps. [observed]
- `elapsedMs` = `modelState.completedAt` - request `timestamp` (exact in two requests, 1 ms off in a third). `result.timings.totalElapsed` differs slightly and is not the same measure. [observed]
- `promptTokens` is dominated by tool definitions (75% in a "Hello world" prompt), so it does not reflect what the user typed. [observed]
- **Attachments:** a file added with the `+` menu appears in `variableData.variables[]` (`kind: file`, name, URI) and its **full text at prompt time** is embedded in `renderedUserMessage` under `<attachments><attachment id filePath>`; the prompt text itself does not name the file. [observed, experiment 04]
- **Tool call identity:** `toolId` (`copilot_readFile`) is not the same string as the round's tool call `name` (`read_file`); `arguments` is a JSON string. `toolCallRounds[].phase` was `commentary` for a round that called a tool and `final_answer` for the last. [observed]
- **`autoModeResolution`** appears only on the first request of a session; later requests carry the model only in `result.metadata.resolvedModel` and round `modelId`. [observed, 2 sessions]
- A session file keeps growing by appends across long gaps (44 min idle, same file, earlier lines unchanged). [observed]
- **Opening an existing session can append lines with no prompt** (a `kind:1` line replacing `inputState.selectedModel`, now with `modelConfiguration: {tier, tierSource}`), so file mtime is not a last-prompt time; the line itself carries no timestamp. [observed, experiment 05]
- **Time** is epoch milliseconds, UTC. Build timelines from `timestamp` and `toolCallRounds[].timestamp`, not line order or file mtime. [observed]
- `responseTimestamp` and `timeSpentWaiting` both equal `timestamp`. They are not durations or completion times. [observed]
- `modelId` can be `copilot/auto`; the model actually used is in `result.metadata.resolvedModel`, per-round `modelId`, and the `autoModeResolution` item. The request inside the `kind:0` snapshot had no `modelId`. [observed]
- `agent.id` was `github.copilot.editsAgent` in agent mode. Use `modeInfo.kind` to tell modes apart. [observed]
- Each `toolCallRounds` entry is one model call; a round with no tool calls is the final answer. [observed, source]
- `toolCallResults` holds tool output, keyed by call ID (the `__vscode-<n>` suffix looks like epoch milliseconds from when the extension host or window started, then counting up per tool call; see experiment 04). Values take two forms. [observed, shape6]
  - **Plain string**: raw tool output. Seen for a create-directory result (`Created directory at ...`), a terminal command that printed only a shell prompt line (WSL-style `user@host:path$` with a UTC timestamp prefix), and `git clone` output (progress lines, so output is stored verbatim and can be long).
  - **Node tree**: dict with `type`, `ctor`, `ctorName`, `children`, `props`, `references`. Looks like a serialised prompt-element tree (prompt-tsx style) used for file read and edit results. `ctorName` was a 2 to 3 character string, probably a minified class name. Contents of `children` and `props` not yet inspected. [hypothesis for what it is]
  - Tool output is evidence of what Copilot saw, so a terminal result can show command output that never touched the endpoint logs.
  - shape6's `toolId=no match` is the script failing to join result keys to response `toolCallId`, not a data finding. Keys carry a `call_...__vscode-<n>` form; compare against the `toolCallId` format before trusting any join.
- `renderedUserMessage` is the prompt as sent, far larger than the typed text (about 2,000 to 12,000 characters). In a 0.35-era example it had `<attachments>`, `<context>`, `<editorContext>`, `<reminderInstructions>`, `<userRequest>` sections. [observed size, source structure]
- A tool record shows Copilot invoked a tool, not that it succeeded. Corroborate with endpoint telemetry.

## Hypotheses

- `isConfirmed.type`: 1 for tools needing no approval, 4 for terminal commands (user action). Denied and other values untested. [observed pattern, hypothesis for meaning]
- `elapsedMs` excludes time spent waiting for the user to approve a command. Fits requests 5 and 6 of the first sample (`totalElapsed` above `elapsedMs` by 3.5 s and 7.8 s), but in experiment 03 (no tools) `elapsedMs` = `completedAt` - `timestamp` and exceeds `totalElapsed` by about 90 ms. Needs re-checking. [hypothesis]
- `terminalCommandState.timestamp` is when the command ran; a candidate join key against process telemetry. [hypothesis]
- `modelState.value`: 0 pending, 1 complete; others (cancelled, failed) unconfirmed. [hypothesis]
- `commandLine.original` differs from `confirmation.commandLine` because of a stripped `cd` prefix, not a user edit. [hypothesis]

## Open questions

- Which compaction threshold applies (512 or 1024)?
- Exact meaning of `isConfirmed.type` values and `toolInputRetry`
- What `editedFileEvents.eventKind: 1` means
- What the node-tree tool results contain (file contents? ranges?) and whether they hold full file text
- Whether session sync (Chronicle) keeps a server-side copy for the account

## Resources

- VS Code source, workspace storage folder name (md5 of path plus folder creation time, inode on Linux): https://github.com/microsoft/vscode/blob/main/src/vs/platform/workspaces/node/workspaces.ts
- VS Code source: `src/vs/workbench/contrib/chat/common/model/objectMutationLog.ts`; PR #286644 (append log), PR #319183 (truncation), issue #317478 (file missing its initial entry)
- Parsers and notes: deja-vu PR #3088, tokmesh-core `copilot_vscode.rs`, claudex, wormlens, agentsview gist, chasm-cli schemas, budi Copilot Chat Data Contract
- Older JSON-era write-ups: remember-mcp-vscode wiki (Session Internals, Chat Session File Format)
- Tools: copilot-history-viewer, Browse-CopilotChats, AgentDFIR (check its Copilot Chat parser against the `i` field and kind-0/1/2 replay)
- Server side: GitHub Copilot audit log docs (no client prompts); VS Code session history docs (Chronicle, sync)

## Pending probe output

- `shape6.py` run: results folded into interpretation notes. Still to do: fix the toolId join, then print `children` and `props` key trees of the node-tree results
- `renderedUserMessage` section tags in 0.60.0: not yet checked

## Before publishing

- [ ] Synthetic or fully sanitised samples only: no real prompts, paths, usernames, or case data
- [ ] Confirm I'm cleared to publish
- [ ] Label every claim observed, source, or hypothesis
- [ ] Record the VS Code and extension versions each claim was tested on
