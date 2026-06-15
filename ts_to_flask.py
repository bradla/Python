#!/usr/bin/env python3
"""
ts_to_flask.py
=====================================================================
Convert a TypeScript Express/Fastify HTTP API into a runnable Flask
(Python) application skeleton.

Audience: you know Python (and Flask is the target), but the source is
a TypeScript backend you'd rather work on in Python.

WHAT IT DOES
  * Scans every .ts/.js file (skips node_modules, dist, .git, ...).
  * Finds Express/Fastify route definitions:
        app.get("/users/:id", handler)
        router.post("/login", async (req, res) => { ... })
        fastify.get("/ping", (req, reply) => { ... })
  * Converts each route into a Flask route:
        - HTTP method  -> methods=["GET"]
        - path params  -> Express ":id"  becomes Flask "<id>"
        - the original TS handler body is preserved in comments, plus a
          best-effort line-by-line Python "suggestion" you can finish.
  * Converts TS `interface` / `type` declarations into Python
    @dataclass models.
  * Emits a small, RUNNABLE Flask project you fill in:
        flask_app/
          app.py            <- all routes wired up (handlers are stubs)
          models.py         <- dataclasses from your TS interfaces/types
          requirements.txt  <- flask
          README.md         <- what was converted + what's left to do

HONEST LIMITATIONS (read these)
  This is a SCAFFOLDER, not a magic transpiler. Full TS->Python semantic
  translation is not possible automatically. What you get:
    - A correct, runnable route table with paths/methods/params wired.
    - Your original handler logic preserved as comments for reference.
    - A best-effort Python translation of common Express idioms
      (res.json, req.params/query/body, console.log, ===, etc.) placed
      as commented suggestions -- NOT executed, so the app always runs.
  You still hand-port the actual business logic. The tool removes the
  boilerplate and gives you a faithful map to work from.

Only the Python standard library is used. No npm, no Node needed.

USAGE
  python3 ts_to_flask.py <path-to-ts-project> [--out DIR] [--apply-suggestions]

  <path-to-ts-project>   Folder containing the TS backend.
  --out DIR              Output folder (default: ./flask_app).
  --apply-suggestions    Emit the best-effort translation as ACTIVE code
                         instead of comments. The app may not run until you
                         fix it, but you skip retyping. Default: off (safe).
  -h, --help             Show this help.

EXAMPLE
  python3 ts_to_flask.py ./my-express-api --out ./ported
"""

import io
import os
import re
import sys

SKIP_DIRS = {
    "node_modules", ".git", ".hg", ".svn",
    "dist", "build", "out", "lib", ".next", "coverage", ".cache",
    "__pycache__", ".idea", "vendor",
}
SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head", "all")


# --------------------------------------------------------------------------- #
# File reading + a tokenizer-ish brace/paren matcher
# --------------------------------------------------------------------------- #

def read_text(path):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return ""


def match_delimiter(text, start, open_ch, close_ch):
    """
    Given text and an index `start` pointing AT an `open_ch`, return the index
    of the matching `close_ch`, correctly skipping nested pairs, strings, and
    comments. Returns -1 if unbalanced.
    """
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if two == "/*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c in "'\"`":
            i = skip_string(text, i)
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def skip_string(text, i):
    """i points at a quote char; return index just past the closing quote."""
    quote = text[i]
    i += 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        # Template literals can contain ${ ... } with nested code; skip braces.
        if quote == "`" and text[i:i + 2] == "${":
            close = match_delimiter(text, i + 1, "{", "}")
            i = n if close == -1 else close + 1
            continue
        i += 1
    return n


def split_top_level_args(arglist):
    """
    Split a function-call argument string on top-level commas only
    (ignoring commas inside (), [], {}, strings). Returns list of arg strings.
    """
    args = []
    depth = 0
    cur = []
    i = 0
    n = len(arglist)
    while i < n:
        c = arglist[i]
        if c in "'\"`":
            j = skip_string(arglist, i)
            cur.append(arglist[i:j])
            i = j
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args


# --------------------------------------------------------------------------- #
# Route extraction
# --------------------------------------------------------------------------- #

# Matches the START of a route registration: <obj>.<method>(
# e.g. app.get(   router.post(   fastify.delete(   server.all(
RX_ROUTE_START = re.compile(
    r'\b([A-Za-z_$][\w$]*)\s*\.\s*(' + "|".join(HTTP_METHODS) + r')\s*\(')


class Route(object):
    def __init__(self):
        self.method = ""          # GET / POST / ...
        self.express_path = ""    # /users/:id
        self.flask_path = ""      # /users/<id>
        self.params = []          # ['id']
        self.req_name = "req"     # handler's request param name
        self.res_name = "res"     # handler's response param name
        self.handler_body = ""    # raw TS body
        self.source_file = ""
        self.source_line = 0
        self.func_name = ""


def extract_handler_signature(args_after_path):
    """
    From the route arguments that follow the path, find the handler function
    and return (req_name, res_name, body_text). Handles:
        (req, res) => { ... }
        async (req, res) => { ... }
        (req, res) => expr            (no braces)
        function (req, res) { ... }
    `args_after_path` is the full remaining argument text (may include
    middleware before the handler; we take the LAST function-looking arg).
    """
    args = split_top_level_args(args_after_path)
    if not args:
        return ("req", "res", "")
    handler = args[-1]   # handler is conventionally the last argument

    # Find the parameter list "(...)" of the handler.
    paren = handler.find("(")
    req_name, res_name = "req", "res"
    body = ""
    if paren != -1:
        close = match_delimiter(handler, paren, "(", ")")
        if close != -1:
            params = split_top_level_args(handler[paren + 1:close])
            names = []
            for p in params:
                # strip type annotations / defaults: "req: Request" -> "req"
                nm = re.split(r'[:=]', p, maxsplit=1)[0].strip()
                nm = nm.lstrip("{").strip()  # not perfect for destructuring
                if nm:
                    names.append(nm)
            if len(names) >= 1:
                req_name = names[0] or "req"
            if len(names) >= 2:
                res_name = names[1] or "res"

            # Body: arrow "=> { }" or "=> expr", or "function(){ }"
            rest = handler[close + 1:]
            arrow = rest.find("=>")
            brace = rest.find("{")
            if arrow != -1 and (brace == -1 or arrow < brace):
                after = rest[arrow + 2:]
                ab = after.find("{")
                if ab != -1 and after[:ab].strip() == "":
                    end = match_delimiter(after, ab, "{", "}")
                    body = after[ab + 1:end] if end != -1 else after[ab + 1:]
                else:
                    body = "return " + after.strip()   # concise arrow body
            elif brace != -1:
                end = match_delimiter(rest, brace, "{", "}")
                body = rest[brace + 1:end] if end != -1 else rest[brace + 1:]
    return (req_name, res_name, body.strip())


def convert_express_path(path):
    """
    Convert an Express route path to a Flask one and list the param names.
      /users/:id          -> /users/<id>            params: [id]
      /files/:name(\\d+)  -> /files/<int:name>      (numeric constraint)
      /a/*                -> /a/<path:wildcard>
    """
    params = []

    def repl(m):
        name = m.group(1)
        constraint = m.group(2)
        params.append(name)
        if constraint and re.search(r'\\d|\[0-9\]', constraint):
            return "<int:%s>" % name
        return "<%s>" % name

    # :name  optionally followed by a (regex) constraint
    flask_path = re.sub(r':([A-Za-z_$][\w$]*)(\([^)]*\))?', repl, path)
    # bare wildcard
    if "*" in flask_path:
        flask_path = flask_path.replace("*", "<path:wildcard>")
        params.append("wildcard")
    return flask_path, params


def find_routes_in_file(path, text):
    routes = []
    for m in RX_ROUTE_START.finditer(text):
        method = m.group(2).upper()
        paren_idx = text.index("(", m.end() - 1)
        close = match_delimiter(text, paren_idx, "(", ")")
        if close == -1:
            continue
        arglist = text[paren_idx + 1:close]
        args = split_top_level_args(arglist)
        if not args:
            continue
        # First arg must be a string path literal, else this is e.g. app.use().
        first = args[0].strip()
        if not (first[:1] in "'\"`" and len(first) >= 2):
            continue
        route_path = first[1:-1]   # strip quotes

        r = Route()
        r.method = "GET" if method == "ALL" else method
        r.express_path = route_path
        r.flask_path, r.params = convert_express_path(route_path)
        # everything after the first comma = middleware + handler
        after_path = arglist[len(args[0]):].lstrip(", \n\t")
        r.req_name, r.res_name, r.handler_body = extract_handler_signature(
            args[0] + ", " + after_path if after_path else args[0])
        r.source_file = path
        r.source_line = text.count("\n", 0, m.start()) + 1
        routes.append(r)
    return routes


# --------------------------------------------------------------------------- #
# Best-effort Express-handler -> Python translation (heuristic, line-based)
# --------------------------------------------------------------------------- #

def translate_handler_body(body, req, res):
    """
    Produce a list of best-effort Python lines from a TS handler body.
    Heuristic and intentionally conservative. Output is meant to be reviewed.
    """
    lines = []
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            lines.append("")
            continue
        s = line

        # Response helpers -> Flask returns ---------------------------------
        # res.status(N).json(X)  -> return jsonify(X), N
        s = re.sub(re.escape(res) + r'\.status\(\s*(\d+)\s*\)\.json\((.*)\)\s*;?',
                   r'return jsonify(\2), \1', s)
        # res.status(N).send(X)  -> return X, N
        s = re.sub(re.escape(res) + r'\.status\(\s*(\d+)\s*\)\.send\((.*)\)\s*;?',
                   r'return \2, \1', s)
        # res.json(X) -> return jsonify(X)
        s = re.sub(re.escape(res) + r'\.json\((.*)\)\s*;?', r'return jsonify(\1)', s)
        # res.send(X) -> return X
        s = re.sub(re.escape(res) + r'\.send\((.*)\)\s*;?', r'return \1', s)
        # res.status(N).end() / res.sendStatus(N) -> return "", N
        s = re.sub(re.escape(res) + r'\.sendStatus\(\s*(\d+)\s*\)\s*;?',
                   r'return "", \1', s)

        # Request accessors -------------------------------------------------
        # req.params.x -> x  (it's a route argument in Flask)
        s = re.sub(re.escape(req) + r'\.params\.([A-Za-z_$][\w$]*)', r'\1', s)
        # req.query.x  -> request.args.get("x")
        s = re.sub(re.escape(req) + r'\.query\.([A-Za-z_$][\w$]*)',
                   r'request.args.get("\1")', s)
        # req.body.x   -> (request.get_json() or {}).get("x")
        s = re.sub(re.escape(req) + r'\.body\.([A-Za-z_$][\w$]*)',
                   r'(request.get_json(silent=True) or {}).get("\1")', s)
        # req.body     -> (request.get_json() or {})
        s = re.sub(re.escape(req) + r'\.body\b', r'(request.get_json(silent=True) or {})', s)
        # req.headers["x"] / req.get("x") -> request.headers.get("x")
        s = re.sub(re.escape(req) + r'\.get\(', 'request.headers.get(', s)

        # General JS -> Python ---------------------------------------------
        s = re.sub(r'\bconsole\.log\(', 'print(', s)
        s = re.sub(r'\bconsole\.(error|warn|info)\(', 'print(', s)
        s = re.sub(r'\bconst\b|\blet\b|\bvar\b', '', s)        # drop declarations
        s = s.replace("===", "==").replace("!==", "!=")
        s = re.sub(r'\btrue\b', 'True', s)
        s = re.sub(r'\bfalse\b', 'False', s)
        s = re.sub(r'\b(null|undefined)\b', 'None', s)
        s = re.sub(r'//', '#', s)                              # line comments
        s = re.sub(r'\bawait\s+', '', s)                       # Flask sync
        s = re.sub(r'^(\s*)return\s+return\b', r'\1return', s)  # concise-arrow artifact
        s = s.rstrip(";").rstrip()

        lines.append(s)
    return lines


# --------------------------------------------------------------------------- #
# TS interface/type  ->  Python @dataclass
# --------------------------------------------------------------------------- #

RX_INTERFACE = re.compile(r'\b(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\s*(?:extends[^\{]+)?\{')
RX_TYPE_OBJ = re.compile(r'\b(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=\s*\{')


def ts_type_to_python(ts):
    """Map a TS type expression to a Python typing annotation (best-effort)."""
    ts = ts.strip().rstrip(";").strip()

    # Strip surrounding parentheses
    while ts.startswith("(") and ts.endswith(")"):
        ts = ts[1:-1].strip()

    # Union with null/undefined -> Optional[...]
    parts = [p.strip() for p in split_union(ts)]
    non_null = [p for p in parts if p not in ("null", "undefined")]
    if len(parts) != len(non_null) and non_null:
        inner = ts_type_to_python(" | ".join(non_null))
        return "Optional[%s]" % inner
    if len(non_null) > 1:
        return "Union[%s]" % ", ".join(ts_type_to_python(p) for p in non_null)
    ts = non_null[0] if non_null else ts

    # Arrays
    m = re.match(r'^(.*)\[\]$', ts)
    if m:
        return "List[%s]" % ts_type_to_python(m.group(1))
    m = re.match(r'^Array<(.+)>$', ts)
    if m:
        return "List[%s]" % ts_type_to_python(m.group(1))
    m = re.match(r'^Record<\s*([^,]+),\s*(.+)>$', ts)
    if m:
        return "Dict[%s, %s]" % (ts_type_to_python(m.group(1)), ts_type_to_python(m.group(2)))

    # String/number literal types -> base type
    if re.match(r'^[\'"].*[\'"]$', ts):
        return "str"
    if re.match(r'^-?\d+(\.\d+)?$', ts):
        return "float"

    base = {
        "string": "str", "number": "float", "boolean": "bool",
        "any": "Any", "unknown": "Any", "void": "None", "never": "Any",
        "object": "dict", "Date": "datetime", "bigint": "int",
        "null": "None", "undefined": "None",
    }
    if ts in base:
        return base[ts]
    if ts.startswith("{"):
        return "dict"
    # Otherwise assume it's another interface/type -> forward reference string.
    if re.match(r'^[A-Za-z_$][\w$]*$', ts):
        return '"%s"' % ts
    return "Any"


def split_union(ts):
    """Split a TS union 'A | B<C|D> | E[]' on top-level | only."""
    parts = []
    depth = 0
    cur = []
    for c in ts:
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(c)
    parts.append("".join(cur))
    return [p for p in parts if p.strip()]


def parse_object_fields(body):
    """
    Parse the inside of an interface/type-object body into
    [(name, python_type, optional_bool)].
    """
    fields = []
    # Split members on ';' or newlines at top level.
    members = []
    depth = 0
    cur = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth -= 1
        if c in ";\n" and depth == 0:
            members.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    members.append("".join(cur))

    for mem in members:
        mem = mem.strip()
        if not mem or mem.startswith("//"):
            continue
        # method signatures, index signatures -> skip
        if mem.startswith("[") or "(" in mem.split(":", 1)[0]:
            continue
        m = re.match(r'^([A-Za-z_$][\w$]*)\s*(\?)?\s*:\s*(.+)$', mem)
        if not m:
            continue
        name, optional, ts_type = m.group(1), bool(m.group(2)), m.group(3)
        py = ts_type_to_python(ts_type)
        if optional and not py.startswith("Optional["):
            py = "Optional[%s]" % py
        fields.append((name, py, optional))
    return fields


def extract_models(text):
    """Return list of (ClassName, fields) from interfaces and object types."""
    models = []
    for rx in (RX_INTERFACE, RX_TYPE_OBJ):
        for m in rx.finditer(text):
            name = m.group(1)
            brace = text.index("{", m.end() - 1)
            end = match_delimiter(text, brace, "{", "}")
            if end == -1:
                continue
            body = text[brace + 1:end]
            fields = parse_object_fields(body)
            if fields:
                models.append((name, fields))
    return models


# --------------------------------------------------------------------------- #
# Code generation
# --------------------------------------------------------------------------- #

def make_func_name(route, used):
    slug = route.flask_path.strip("/")
    slug = re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'by_\1', slug)   # <int:id> -> by_id
    slug = re.sub(r'[^A-Za-z0-9]+', '_', slug).strip("_").lower()
    base = ("%s_%s" % (route.method.lower(), slug)).strip("_")
    if not base:
        base = route.method.lower() + "_root"
    name = base
    i = 2
    while name in used:
        name = "%s_%d" % (base, i)
        i += 1
    used.add(name)
    return name


def generate_app_py(routes, apply_suggestions):
    out = []
    out.append('"""')
    out.append("Flask app generated from a TypeScript Express/Fastify API by ts_to_flask.py.")
    out.append("")
    out.append("Each route below mirrors a route from the original TS code. Handler")
    out.append("bodies are STUBS: the original TypeScript is kept in comments, with a")
    out.append("best-effort Python translation. Replace the stub return with real logic.")
    out.append('"""')
    out.append("from flask import Flask, request, jsonify")
    out.append("")
    out.append("# from models import *   # uncomment if you use the generated dataclasses")
    out.append("")
    out.append("app = Flask(__name__)")
    out.append("")

    for r in routes:
        args = ", ".join(r.params)
        rel = os.path.basename(r.source_file)
        out.append("")
        out.append('@app.route("%s", methods=["%s"])' % (r.flask_path, r.method))
        out.append("def %s(%s):" % (r.func_name, args))
        out.append('    """%s %s  (from %s:%d)"""'
                   % (r.method, r.express_path, rel, r.source_line))

        # Original TS body, as reference comments.
        if r.handler_body:
            out.append("    # ----- ORIGINAL TypeScript handler -----")
            for ln in r.handler_body.splitlines():
                out.append("    # " + ln)
            out.append("    # ----- best-effort Python translation -----")
            translated = translate_handler_body(r.handler_body, r.req_name, r.res_name)
            prefix = "    " if apply_suggestions else "    # "
            had_return = False
            for ln in translated:
                if ln.strip().startswith("return "):
                    had_return = True
                out.append((prefix + ln) if ln.strip() else "")
            if apply_suggestions and not had_return:
                out.append('    return jsonify({"ok": True})')
            if not apply_suggestions:
                out.append('    return jsonify({"todo": "implement %s"})' % r.func_name)
        else:
            out.append("    # (no inline handler found in source -- it may be a named")
            out.append("    #  function or imported controller; port it manually)")
            out.append('    return jsonify({"todo": "implement %s"})' % r.func_name)

    out.append("")
    out.append("")
    out.append('if __name__ == "__main__":')
    out.append("    app.run(debug=True, port=5000)")
    out.append("")
    return "\n".join(out)


def generate_models_py(models):
    out = []
    out.append('"""Dataclasses generated from TypeScript interfaces/types.')
    out.append("")
    out.append("Type mapping used: string->str, number->float, boolean->bool,")
    out.append("T[]/Array<T>->List[T], Record<K,V>->Dict[K,V], Date->datetime,")
    out.append("any/unknown->Any, optional (name?)->Optional[...] with default None.")
    out.append("Adjust number->int where appropriate.")
    out.append('"""')
    out.append("from dataclasses import dataclass, field")
    out.append("from datetime import datetime")
    out.append("from typing import Any, Dict, List, Optional, Union")
    out.append("")
    if not models:
        out.append("# (no interfaces or object type aliases were found)")
        return "\n".join(out) + "\n"

    for name, fields in models:
        # Required fields (no default) must come before fields with defaults.
        required = [f for f in fields if not f[2]]
        optional = [f for f in fields if f[2]]
        out.append("")
        out.append("@dataclass")
        out.append("class %s:" % name)
        if not required and not optional:
            out.append("    pass")
        for fname, ftype, _ in required:
            out.append("    %s: %s" % (fname, ftype))
        for fname, ftype, _ in optional:
            out.append("    %s: %s = None" % (fname, ftype))
    return "\n".join(out) + "\n"


def generate_readme(routes, models, src_root):
    out = []
    out.append("# Flask port (generated by ts_to_flask.py)")
    out.append("")
    out.append("Source TypeScript project: `%s`" % os.path.abspath(src_root))
    out.append("")
    out.append("## Run it")
    out.append("```bash")
    out.append("python3 -m venv venv && source venv/bin/activate")
    out.append("pip install -r requirements.txt")
    out.append("python app.py        # serves on http://localhost:5000")
    out.append("```")
    out.append("")
    out.append("## What was converted")
    out.append("- **%d routes** wired into `app.py`" % len(routes))
    out.append("- **%d data models** generated in `models.py`" % len(models))
    out.append("")
    out.append("## Route map")
    out.append("")
    out.append("| Method | Flask path | From TS path | Source |")
    out.append("|--------|-----------|--------------|--------|")
    for r in routes:
        out.append("| %s | `%s` | `%s` | %s:%d |" % (
            r.method, r.flask_path, r.express_path,
            os.path.basename(r.source_file), r.source_line))
    out.append("")
    out.append("## What's left for YOU to do")
    out.append("- Each handler in `app.py` is a stub. The original TypeScript is in")
    out.append("  comments, with a best-effort Python translation. Port the real logic.")
    out.append("- Wire up your database/ORM (TS code often uses Prisma/TypeORM;")
    out.append("  Python equivalents: SQLAlchemy, Peewee).")
    out.append("- Recreate middleware (auth, CORS, body parsing). Flask uses")
    out.append("  `@app.before_request`, extensions like flask-cors, etc.")
    out.append("- Check `number` fields in `models.py`: change `float` to `int`")
    out.append("  where the value is really an integer.")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def collect(src_root):
    routes, models = [], []
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in SOURCE_EXTS:
                continue
            full = os.path.join(dirpath, name)
            text = read_text(full)
            if not text:
                continue
            routes.extend(find_routes_in_file(full, text))
            models.extend(extract_models(text))
    # de-dup models by name (first definition wins)
    seen, uniq = set(), []
    for nm, fields in models:
        if nm not in seen:
            seen.add(nm)
            uniq.append((nm, fields))
    return routes, uniq


def parse_args(argv):
    opts = {"src": None, "out": "flask_app", "apply": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif a == "--out":
            i += 1
            opts["out"] = argv[i]
        elif a == "--apply-suggestions":
            opts["apply"] = True
        elif a.startswith("-"):
            print("Unknown option: %s (use --help)" % a)
            sys.exit(2)
        else:
            opts["src"] = a
        i += 1
    if not opts["src"]:
        print("Error: missing <path-to-ts-project>. Use --help.")
        sys.exit(2)
    return opts


def main():
    opts = parse_args(sys.argv[1:])
    src = opts["src"]
    if not os.path.isdir(src):
        print("Error: '%s' is not a directory." % src)
        sys.exit(1)

    routes, models = collect(src)

    # Assign unique function names.
    used = set()
    for r in routes:
        r.func_name = make_func_name(r, used)

    out_dir = opts["out"]
    os.makedirs(out_dir, exist_ok=True)

    with io.open(os.path.join(out_dir, "app.py"), "w", encoding="utf-8") as f:
        f.write(generate_app_py(routes, opts["apply"]))
    with io.open(os.path.join(out_dir, "models.py"), "w", encoding="utf-8") as f:
        f.write(generate_models_py(models))
    with io.open(os.path.join(out_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("flask>=3.0\n")
    with io.open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(generate_readme(routes, models, src))

    # Console summary
    print("Converted TypeScript -> Flask")
    print("  source : %s" % os.path.abspath(src))
    print("  output : %s/" % os.path.abspath(out_dir))
    print("  routes : %d" % len(routes))
    print("  models : %d" % len(models))
    if routes:
        print("\nRoute map:")
        for r in routes:
            print("  %-6s %-28s <- %s:%d"
                  % (r.method, r.flask_path, os.path.basename(r.source_file), r.source_line))
    else:
        print("\nNo Express/Fastify routes found. Is this the right folder?")
        print("Expected calls like  app.get(\"/x\", ...)  or  router.post(...).")
    print("\nNext: cd %s && pip install -r requirements.txt && python app.py" % out_dir)
    print("Handlers are stubs -- see README.md for what to finish.")


if __name__ == "__main__":
    main()
