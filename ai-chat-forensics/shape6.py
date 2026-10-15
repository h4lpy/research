import json, sys

def get(s, p):
    for x in p:
        s = s[x]
    return s

def tree(v, d=0, maxd=3):
    pad = "      " + "  " * d
    if isinstance(v, dict) and d < maxd:
        for k in list(v)[:15]:
            x = v[k]
            n = "(%d)" % len(x) if isinstance(x, (list, str)) else ""
            print("%s%s: %s%s" % (pad, k, type(x).__name__, n))
            tree(x, d + 1, maxd)
    elif isinstance(v, list) and v and d < maxd:
        tree(v[0], d + 1, maxd)

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

for i, r in enumerate(state["requests"]):
    md = (r.get("result") or {}).get("metadata") or {}
    tools = {it.get("toolCallId"): it.get("toolId") for it in r.get("response") or []
             if isinstance(it, dict) and it.get("kind") == "toolInvocationSerialized"}
    print("req %d" % i)
    for cid, val in (md.get("toolCallResults") or {}).items():
        print("  ...%s  toolId=%s" % (cid[-18:], tools.get(cid, "no match")))
        for c in (val.get("content") or []) if isinstance(val, dict) else []:
            x = c.get("value") if isinstance(c, dict) else None
            if isinstance(x, str):
                print("      str: %r" % x[:150])
            else:
                tree(x)
