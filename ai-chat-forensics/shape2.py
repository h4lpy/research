import json, sys, collections
C = collections.defaultdict(collections.Counter)

def add(name, val):
    if val is None:
        return
    if isinstance(val, dict):
        val = "dict{%s}" % ",".join(sorted(val))
    elif isinstance(val, list):
        val = "list(%d)" % len(val)
    C[name][str(val)[:80]] += 1

def resp_item(it):
    if not isinstance(it, dict):
        return
    kind = it.get("kind")
    add("response item kind", kind or "(none)")
    if kind == "toolInvocationSerialized":
        for f in ("toolId", "isConfirmed", "isComplete", "source"):
            add("tool." + f, it.get(f))
        tsd = it.get("toolSpecificData")
        if isinstance(tsd, dict):
            add("toolSpecificData.kind", tsd.get("kind"))
            add("toolSpecificData keys", tsd)
    elif kind == "textEditGroup":
        add("textEditGroup keys", it)
        add("textEditGroup.done", it.get("done"))
        add("textEditGroup.uri", it.get("uri"))

def req(r):
    if not isinstance(r, dict):
        return
    ag = r.get("agent")
    if isinstance(ag, dict):
        for f in ("id", "extensionVersion", "name"):
            add("agent." + f, ag.get(f))
    add("modelId", r.get("modelId"))
    mi = r.get("modeInfo")
    if isinstance(mi, dict):
        for f in ("kind", "isBuiltin", "telemetryModeId", "permissionLevel"):
            add("modeInfo." + f, mi.get(f))
    add("modelState keys", r.get("modelState"))
    res = r.get("result")
    if isinstance(res, dict):
        add("result keys", res)
        add("result.details", res.get("details"))
        for f in ("metadata", "timings"):
            add("result.%s keys" % f, res.get(f))
    add("variableData.variables", (r.get("variableData") or {}).get("variables"))
    add("message.parts", (r.get("message") or {}).get("parts"))
    add("editedFileEvents", r.get("editedFileEvents"))
    for it in r.get("response") or []:
        resp_item(it)

with open(sys.argv[1], encoding="utf-8") as f:
    for n, line in enumerate(f, 1):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        kind, k, v = o.get("kind"), o.get("k") or [], o.get("v")
        if "i" in o:
            print("line %d: kind=%s k=%s i=%r v=%s" % (
                n, kind, "/".join(map(str, k)), o["i"],
                type(v).__name__ + ("(%d)" % len(v) if isinstance(v, list) else "")))
        if kind == 0 and isinstance(v, dict):
            add("initialLocation", v.get("initialLocation"))
            ins = v.get("inputState") or {}
            add("inputState.mode", ins.get("mode"))
            add("inputState.permissionLevel", ins.get("permissionLevel"))
            sm = ins.get("selectedModel") or {}
            md = sm.get("metadata") or {}
            for fld in ("vendor", "family", "version", "isBYOK"):
                add("selectedModel." + fld, md.get(fld))
            for r in v.get("requests") or []:
                req(r)
        elif kind == 2 and list(k) == ["requests"] and isinstance(v, list):
            print("line %d: PUSH requests -> %s" % (n, [
                (str(r.get("requestId"))[:20], "result" in r) for r in v if isinstance(r, dict)]))
            for r in v:
                req(r)
        elif kind == 2 and len(k) == 3 and k[0] == "requests" and k[2] == "response":
            for it in v or []:
                resp_item(it)
        elif kind == 1 and len(k) == 3 and k[0] == "requests":
            req({k[2]: v})

print()
for name in sorted(C):
    print(name)
    for val, cnt in C[name].most_common(12):
        print("   %4d  %s" % (cnt, val))
