import json, sys, collections, datetime
C = collections.defaultdict(collections.Counter)

def sig(v, d=0):
    if isinstance(v, dict):
        return "{%s}" % ",".join(
            "%s:%s" % (k, sig(x, d + 1)) if d < 1 and isinstance(x, (dict, list)) else k
            for k, x in sorted(v.items()))
    if isinstance(v, list):
        return "[%s]" % "|".join(sorted({sig(i, d + 1) for i in v})[:4])
    return type(v).__name__

def add(name, val):
    if val is not None:
        C[name][sig(val)] += 1

def addv(name, val):
    if val is not None:
        C[name][str(val)[:80]] += 1

def get(s, path):
    for p in path:
        s = s[p]
    return s

def iso(ms):
    try:
        return datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms)

state, intro, errs = None, {}, []
with open(sys.argv[1], encoding="utf-8") as f:
    for n, line in enumerate(f, 1):
        try:
            o = json.loads(line)
            kind, k, v = o.get("kind"), o.get("k") or [], o.get("v")
            if kind == 0:
                state = v
                for i in range(len(v.get("requests", []))):
                    intro[i] = n
            elif kind == 1:
                if not k:
                    state = v
                else:
                    par, key = get(state, k[:-1]), k[-1]
                    if isinstance(par, list) and key == len(par):
                        par.append(v)
                    else:
                        par[key] = v
            elif kind == 2:
                arr = get(state, k)
                before, i = len(arr), o.get("i")
                if i is not None:
                    del arr[i:]
                arr.extend(v)
                if i is not None:
                    print("line %d: k=%s i=%s len_before=%d len(v)=%d len_after=%d" % (
                        n, "/".join(map(str, k)), i, before, len(v), len(arr)))
                if k == ["requests"]:
                    for j in range(before, len(arr)):
                        intro[j] = n
            elif kind == 3:
                print("line %d: kind=3 k=%s" % (n, k))
                del get(state, k[:-1])[k[-1]]
            else:
                errs.append((n, "unknown kind %r" % kind))
        except Exception as e:
            errs.append((n, repr(e)[:120]))

print("replay errors:", errs[:10])
addv("version", state.get("version"))
addv("responderUsername", state.get("responderUsername"))
print("\nidx  introduced@line  timestamp(UTC)  responseTimestamp(UTC)  resp_items  has_result")
for i, r in enumerate(state.get("requests", [])):
    print("%3d  %15s  %s  %s  %10d  %s" % (
        i, intro.get(i), iso(r.get("timestamp", 0)), iso(r.get("responseTimestamp", 0)),
        len(r.get("response") or []), "result" in r))
    res = r.get("result") or {}
    add("result.metadata", res.get("metadata"))
    add("result.timings", res.get("timings"))
    addv("modelState.value", (r.get("modelState") or {}).get("value"))
    for fld in ("message.parts", "editedFileEvents", "contentReferences", "codeCitations", "followups"):
        top, _, sub = fld.partition(".")
        val = r.get(top)
        add(fld, val.get(sub) if sub and isinstance(val, dict) else val)
    for it in r.get("response") or []:
        if not isinstance(it, dict):
            continue
        ik = it.get("kind") or "(markdown)"
        add("item " + ik, it)
        if ik == "toolInvocationSerialized":
            ic = it.get("isConfirmed")
            add("tool.isConfirmed", ic)
            addv("tool.isConfirmed.type", ic.get("type") if isinstance(ic, dict) else ic)
            sr = it.get("source")
            if isinstance(sr, dict):
                addv("tool.source.type", sr.get("type"))
                addv("tool.source.label", sr.get("label"))
            add("tool.invocationMessage", it.get("invocationMessage"))
            tsd = it.get("toolSpecificData")
            if isinstance(tsd, dict):
                add("toolSpecificData", tsd)
                add("toolSpecificData.commandLine", tsd.get("commandLine"))
                add("toolSpecificData.confirmation", tsd.get("confirmation"))
        elif ik == "textEditGroup":
            add("textEditGroup.edits", it.get("edits"))

print()
for name in sorted(C):
    print(name)
    for val, cnt in C[name].most_common(8):
        print("   %4d  %s" % (cnt, val))
