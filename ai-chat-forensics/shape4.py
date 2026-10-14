import json, sys, re, collections, datetime
C = collections.defaultdict(collections.Counter)

def get(s, path):
    for p in path:
        s = s[p]
    return s

def shape(v):
    if isinstance(v, dict):
        return "{%s}" % ",".join(sorted(v))
    if isinstance(v, list):
        return "list(%d)" % len(v)
    return type(v).__name__

def ts(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%H:%M:%S")

def secs(a, b):
    try:
        return "%+.1fs" % ((a - b) / 1000.0)
    except TypeError:
        return "?"

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

def rendered(name, lst):
    for x in lst or []:
        if isinstance(x, dict):
            t = x.get("text")
            C[name]["type=%r cacheType=%r text_len~%s" % (
                x.get("type"), x.get("cacheType"),
                "-" if not isinstance(t, str) else len(t) // 500 * 500)] += 1

for i, r in enumerate(state["requests"]):
    res = r.get("result") or {}
    tm = res.get("timings") or {}
    md = res.get("metadata") or {}
    print("req %d @%s UTC: firstProgress=%r totalElapsed=%r elapsedMs=%r timeSpentWaiting=%r" % (
        i, ts(r["timestamp"]), tm.get("firstProgress"), tm.get("totalElapsed"),
        r.get("elapsedMs"), r.get("timeSpentWaiting")))
    for j, rd in enumerate(md.get("toolCallRounds") or []):
        print("    round %d: phase=%r %s tools=%d response=%s modelId=%s retry=%r" % (
            j, rd.get("phase"), secs(rd.get("timestamp"), r["timestamp"]),
            len(rd.get("toolCalls") or []), shape(rd.get("response")),
            rd.get("modelId"), rd.get("toolInputRetry")))
    nums = []
    for cid, val in (md.get("toolCallResults") or {}).items():
        m = re.search(r"__vscode-(\d+)$", cid)
        if m:
            nums.append(int(m.group(1)))
        C["toolCallResults value"][shape(val)] += 1
        if isinstance(val, dict):
            for k2, v2 in val.items():
                C["toolCallResults." + k2][shape(v2)] += 1
                if isinstance(v2, list):
                    for x in v2:
                        C["toolCallResults.%s[]" % k2][shape(x)] += 1
    if nums:
        print("    call id suffixes:", sorted(nums), "min as time: %s UTC" % ts(min(nums)))
    rendered("renderedUserMessage", md.get("renderedUserMessage"))
    rendered("renderedGlobalContext", md.get("renderedGlobalContext"))
    for cb in md.get("codeBlocks") or []:
        if isinstance(cb, dict):
            C["codeBlock language"][str(cb.get("language"))] += 1
    for ev in r.get("editedFileEvents") or []:
        if isinstance(ev, dict):
            C["editedFileEvents.eventKind"][str(ev.get("eventKind"))] += 1
    for it in r.get("response") or []:
        if not isinstance(it, dict):
            continue
        ik = it.get("kind")
        if ik == "autoModeResolution":
            print("    autoModeResolution:", {x: it.get(x) for x in (
                "confidence", "predictedLabel", "resolvedModel", "resolvedModelName")})
        elif ik == "mcpServersStarting":
            C["mcp didStartServerIds"][shape(it.get("didStartServerIds"))] += 1
        elif ik == "textEditGroup":
            for grp in it.get("edits") or []:
                for e in grp or []:
                    if isinstance(e, dict):
                        C["edit"][shape(e) + " range=" + shape(e.get("range"))] += 1
        elif ik == "toolInvocationSerialized":
            ct = (it.get("isConfirmed") or {}).get("type")
            C["toolId / isConfirmed.type"]["%s / %s" % (it.get("toolId"), ct)] += 1
            tsd = it.get("toolSpecificData") or {}
            if tsd.get("kind") == "terminal":
                cl = tsd.get("commandLine") or {}
                cf = tsd.get("confirmation") or {}
                C["terminal original==forDisplay"][str(cl.get("original") == cl.get("forDisplay"))] += 1
                C["terminal original==confirmation.commandLine"][
                    str(cl.get("original") == cf.get("commandLine"))] += 1
                C["terminal flags"]["bg=%s sandboxWrapped=%s allowNet=%s unsandboxed=%s state=%s" % (
                    tsd.get("isBackground"), cl.get("isSandboxWrapped"),
                    tsd.get("requestAllowNetwork"), tsd.get("requestUnsandboxedExecution"),
                    shape(tsd.get("terminalCommandState")))] += 1

print()
for name in sorted(C):
    print(name)
    for val, cnt in C[name].most_common(10):
        print("   %4d  %s" % (cnt, val))
