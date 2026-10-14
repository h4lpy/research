import json, sys, collections

def p(path):
    return "/".join("*" if isinstance(x, int) else str(x) for x in (path or []))

def sig(v):
    if isinstance(v, dict):
        kind = v.get("kind")
        tag = "<kind=%s>" % kind if isinstance(kind, str) else ""
        return "obj{%s}%s" % (",".join(sorted(v)[:20]), tag)
    if isinstance(v, list):
        return "list[%s]" % " | ".join(sorted({sig(i) for i in v})[:5])
    return type(v).__name__

def tree(v, d=0, maxd=4):
    pad = "  " * d
    if isinstance(v, dict) and d < maxd:
        for k in list(v)[:30]:
            x = v[k]
            leaf = "" if isinstance(x, (dict, list)) else type(x).__name__
            print("%s%s %s" % (pad, k, leaf))
            tree(x, d + 1, maxd)
    elif isinstance(v, list) and v and d < maxd:
        print("%s(list of %d, first item:)" % (pad, len(v)))
        tree(v[0], d + 1, maxd)

ops, top, bad, shown = {}, collections.Counter(), [], False
with open(sys.argv[1], encoding="utf-8") as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except ValueError:
            bad.append(n)
            continue
        if not isinstance(o, dict):
            top["non-object"] += 1
            continue
        top[",".join(sorted(o))] += 1
        key = (o.get("kind"), p(o.get("k")))
        e = ops.setdefault(key, {"n": 0, "first": n, "sigs": set()})
        e["n"] += 1
        if len(e["sigs"]) < 4:
            e["sigs"].add(sig(o.get("v")))
        if o.get("kind") == 0 and not shown:
            shown = True
            print("== kind 0 snapshot tree (line %d) ==" % n)
            tree(o.get("v"))

print("\n== line envelopes (top-level keys) ==")
for k, c in top.most_common():
    print(c, k)
print("\n== operations: (kind, path shape) ==")
for (kind, path), e in sorted(ops.items(), key=lambda kv: kv[1]["first"]):
    print("kind=%s k=/%s  x%d  first@line %d" % (kind, path, e["n"], e["first"]))
    for s in sorted(e["sigs"]):
        print("     v: " + s)
print("\nunparseable lines:", bad[:20], "(total %d)" % len(bad))
