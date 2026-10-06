import collections
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = json.load(open(os.path.join(ROOT, "swagger", "openapi.json"), encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]
OUT = os.path.join(ROOT, "design", "screen_spec.json")

SKIP_FIELDS = {"tenant_id", "created_by", "updated_by"}


def deref(schema, depth=0):
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        resolved = deref(SCHEMAS.get(name, {}), depth + 1)
        resolved = dict(resolved)
        resolved.setdefault("_name", name)
        return resolved
    for key in ("allOf",):
        if key in schema:
            merged = {"properties": {}, "required": []}
            for part in schema[key]:
                p = deref(part, depth + 1)
                merged["properties"].update(p.get("properties", {}))
                merged["required"] += p.get("required", [])
                for k, v in p.items():
                    merged.setdefault(k, v)
            return merged
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [o for o in schema[key] if not (isinstance(o, dict) and o.get("type") == "null")]
            nullable = len(options) != len(schema[key])
            first = deref(options[0], depth + 1) if options else {}
            first = dict(first)
            first["_nullable"] = nullable
            if schema.get("title"):
                first.setdefault("title", schema["title"])
            if "default" in schema:
                first["default"] = schema["default"]
            return first
    return schema


def field_of(name, raw, required, depth=0):
    s = deref(raw)
    typ = s.get("type", "object" if "properties" in s else "string")
    f = {"key": name, "type": typ, "required": required}
    if s.get("format"):
        f["format"] = s["format"]
    if s.get("enum"):
        f["enum"] = s["enum"]
    for k in ("minLength", "maxLength", "minimum", "maximum", "pattern", "default", "description"):
        if k in s and s[k] is not None:
            f[k] = s[k] if k != "description" else s[k][:140]
    if s.get("_nullable"):
        f["nullable"] = True
    if typ == "array":
        item = deref(s.get("items", {}))
        if "properties" in item and depth < 3:
            f["items"] = fields_of(item, depth + 1)
        else:
            f["itemType"] = item.get("type", "string")
            if item.get("enum"):
                f["enum"] = item["enum"]
            if item.get("format"):
                f["itemFormat"] = item["format"]
    elif typ == "object" and "properties" in s and depth < 3:
        f["fields"] = fields_of(s, depth + 1)
    return f


def fields_of(schema, depth=0):
    s = deref(schema)
    req = set(s.get("required", []))
    out = []
    for name, raw in (s.get("properties") or {}).items():
        if name in SKIP_FIELDS:
            continue
        out.append(field_of(name, raw, name in req, depth))
    return out


def body_schema(op):
    body = (op.get("requestBody") or {}).get("content", {})
    for ctype, val in body.items():
        sch = val.get("schema", {})
        d = deref(sch)
        return ctype, d, d.get("_name")
    return None, None, None


def response_schema(op):
    for code in ("200", "201"):
        r = (op.get("responses") or {}).get(code)
        if not r:
            continue
        sch = ((r.get("content") or {}).get("application/json") or {}).get("schema")
        if sch:
            return deref(sch)
    return None


def params_of(op, kind):
    out = []
    for p in op.get("parameters", []):
        if p.get("in") != kind:
            continue
        s = deref(p.get("schema", {}))
        out.append({"key": p["name"], "type": s.get("type", "string"), "format": s.get("format"), "required": p.get("required", False), "enum": s.get("enum"), "default": s.get("default")})
    return out


def row_fields(resp):
    if not resp:
        return []
    if resp.get("type") == "array":
        item = deref(resp.get("items", {}))
        return fields_of(item)
    props = resp.get("properties", {})
    for key in ("items", "data", "results"):
        if key in props:
            arr = deref(props[key])
            if arr.get("type") == "array":
                return fields_of(deref(arr.get("items", {})))
    if props:
        return fields_of(resp)
    return []


tags = collections.OrderedDict()
for path, item in SPEC["paths"].items():
    for method, op in item.items():
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        tag = (op.get("tags") or ["Other"])[0]
        tags.setdefault(tag, []).append((method.upper(), path, op))

result = []
for tag, ops in tags.items():
    entry = {"tag": tag, "ops": len(ops), "list": None, "detail": None, "create": None, "update": None, "delete": None, "actions": []}
    used = set()
    gets = [(m, p, o) for m, p, o in ops if m == "GET"]
    plain = [(m, p, o) for m, p, o in gets if "{" not in p]
    best, best_n = None, -1
    for m, p, o in plain:
        last = p.rstrip("/").split("/")[-1]
        if last in ("dropdown", "search", "stats", "active", "template", "export", "download"):
            continue
        fields = row_fields(response_schema(o))
        score = len(fields) - (3 if last in ("paginated",) else 0)
        if score > best_n:
            best, best_n = (m, p, o, fields), score
    if best:
        m, p, o, fields = best
        entry["list"] = {"method": m, "path": p, "summary": o.get("summary", ""), "columns": fields, "filters": params_of(o, "query")}
        used.add((m, p))
    for m, p, o in gets:
        if (m, p) in used:
            continue
        if re.search(r"/\{[^}/]+\}/?$", p) and p.count("{") == 1 and not entry["detail"]:
            entry["detail"] = {"method": m, "path": p, "summary": o.get("summary", ""), "fields": row_fields(response_schema(o)) or (fields_of(response_schema(o)) if response_schema(o) else [])}
            used.add((m, p))
    posts = [(m, p, o) for m, p, o in ops if m == "POST" and "{" not in p]
    for m, p, o in posts:
        ctype, sch, name = body_schema(o)
        last = p.rstrip("/").split("/")[-1]
        if sch and not entry["create"] and (name or "").lower().endswith("create") or (sch and not entry["create"] and last in ("", tag.split("/")[-1].lower())):
            entry["create"] = {"method": m, "path": p, "summary": o.get("summary", ""), "schema": name, "contentType": ctype, "fields": fields_of(sch), "query": params_of(o, "query")}
            used.add((m, p))
    if not entry["create"]:
        for m, p, o in posts:
            ctype, sch, name = body_schema(o)
            if sch and (m, p) not in used:
                entry["create"] = {"method": m, "path": p, "summary": o.get("summary", ""), "schema": name, "contentType": ctype, "fields": fields_of(sch), "query": params_of(o, "query")}
                used.add((m, p))
                break
    for m, p, o in ops:
        if m in ("PUT", "PATCH") and p.count("{") == 1 and not entry["update"]:
            ctype, sch, name = body_schema(o)
            entry["update"] = {"method": m, "path": p, "summary": o.get("summary", ""), "schema": name, "contentType": ctype, "fields": fields_of(sch) if sch else [], "query": params_of(o, "query")}
            used.add((m, p))
        if m == "DELETE" and p.count("{") == 1 and not entry["delete"]:
            entry["delete"] = {"method": m, "path": p, "summary": o.get("summary", "")}
            used.add((m, p))
    for m, p, o in ops:
        if (m, p) in used:
            continue
        ctype, sch, name = body_schema(o)
        entry["actions"].append(
            {
                "method": m,
                "path": p,
                "summary": (o.get("summary") or "")[:90],
                "pathParams": params_of(o, "path"),
                "query": params_of(o, "query"),
                "body": fields_of(sch) if sch else [],
                "contentType": ctype,
            }
        )
    result.append(entry)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(result, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
print(len(result), "groups,", os.path.getsize(OUT) // 1024, "KB")
for e in result[:12]:
    print(e["tag"], "| list cols", len((e["list"] or {}).get("columns", [])), "| create", len((e["create"] or {}).get("fields", [])), "| update", len((e["update"] or {}).get("fields", [])), "| actions", len(e["actions"]))
