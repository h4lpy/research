import json, sys, datetime

def get(s, p):
    for x in p:
        s = s[x]
    return s

def ts(ms):
    if not isinstance(ms, (int, float)):
        return "?"
    d = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
    return d.strftime("%H:%M:%S.") + "%03d" % (d.microsecond // 1000)

state = None
with open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        kind, k, v = o.get("kind"), o.get("k") or [], o.get("v")
        if kind == 0:
            state = v
        elif kind == 1:
            par, key = get(state, k[:-1]), k[-1]
            if isinstance(par, list) and key == len(par):
                par.append(v)
            else:
                par[key] = v
        elif kind == 2:
            arr = get(state, k)
            if o.get("i") is not None:
                del arr[o["i"]:]
            arr.extend(v)

print("creationDate:", ts(state.get("creationDate")), "UTC")
for i, r in enumerate(state["requests"]):
    t, w = r.get("timestamp"), r.get("timeSpentWaiting")
    diff = "%+d ms" % (w - t) if isinstance(w, int) and isinstance(t, int) else "?"
    print("req %d: modelId=%r timestamp=%s timeSpentWaiting=%s (%s)" % (
        i, r.get("modelId"), ts(t), ts(w), diff))
    md = (r.get("result") or {}).get("metadata") or {}
    for cid, val in (md.get("toolCallResults") or {}).items():
        for c in (val.get("content") or []) if isinstance(val, dict) else []:
            x = c.get("value") if isinstance(c, dict) else None
            print("    toolCallResults value: %s%s" % (
                type(x).__name__, " len=%d" % len(x) if isinstance(x, str) else ""))
    for it in r.get("response") or []:
        if isinstance(it, dict) and it.get("kind") == "toolInvocationSerialized":
            tsd = it.get("toolSpecificData") or {}
            if tsd.get("kind") == "terminal":
                tt = (tsd.get("terminalCommandState") or {}).get("timestamp")
                rel = "%+.1fs" % ((tt - t) / 1000.0) if isinstance(tt, (int, float)) and isinstance(t, (int, float)) else "?"
                print("    terminal: commandState.timestamp=%s (%s vs request)" % (ts(tt), rel))
    for ev in r.get("editedFileEvents") or []:
        print("    editedFileEvent: eventKind=%r uri keys=%s" % (
            ev.get("eventKind"), sorted(ev.get("uri") or {})))
