#!/usr/bin/env python3
"""
analyze_ts_project.py
=====================================================================
A TypeScript project explorer for people who DON'T know TypeScript.

Audience: you know Python, C, or C# but not TypeScript/JavaScript.
Goal:     understand and safely modify an existing TS/JS project.

What it does:
  * Recursively scans every subdirectory (skipping node_modules, build
    output, .git, etc.).
  * Reads package.json  -> project name, how to build/run/test, libraries.
  * Reads tsconfig.json -> how the code is compiled.
  * Finds the entry points (where the program actually starts).
  * For every .ts/.tsx/.js/.jsx file, lists the "public" things:
    exported functions, classes, interfaces, types, enums, constants,
    and React components -- plus what each file imports.
  * Prints a TypeScript -> Python / C# / C cheat-sheet so the syntax
    you'll see makes sense.

It uses ONLY the Python standard library. No npm, no TypeScript compiler
needed. Parsing is regex-based: it's meant to give you a fast, readable
map of the project, not a 100%-perfect AST. That trade-off is on purpose
-- it works on any machine with Python 3 and never breaks on syntax it
doesn't recognize.

USAGE
  python3 analyze_ts_project.py [path-to-project] [options]

  path-to-project   Folder to analyze. Defaults to current directory ".".

OPTIONS
  --md FILE         Also write the full report to a Markdown file.
  --max-files N     Stop after detailing N source files (default: no limit).
  --no-glossary     Skip the TypeScript cheat-sheet at the end.
  -h, --help        Show this help.

EXAMPLES
  python3 analyze_ts_project.py ./my-app
  python3 analyze_ts_project.py ../some-project --md report.md
"""

import io
import json
import os
import re
import sys

# --------------------------------------------------------------------------- #
# Configuration: which folders/files to ignore, which to treat as source code.
# --------------------------------------------------------------------------- #

# Directories we never descend into. These are generated/vendored and would
# bury the real source under tens of thousands of irrelevant files.
SKIP_DIRS = {
    "node_modules",   # downloaded third-party libraries (like pip's site-packages)
    ".git", ".hg", ".svn",
    "dist", "build", "out", "lib", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".cache", ".turbo", ".parcel-cache",
    "__pycache__", ".idea", ".vscode-test", "vendor",
}

# File extensions that hold actual program logic.
#   .ts  = TypeScript            (compiles to .js)
#   .tsx = TypeScript + JSX      (TS with embedded HTML-like UI markup)
#   .js  = JavaScript            (what TS becomes; also hand-written)
#   .jsx = JavaScript + JSX
#   .mts/.cts = ES-module / CommonJS module variants of TypeScript
SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}

# Files that are usually generated or are type-only declarations; we count
# them but don't dig into their internals.
DECLARATION_SUFFIX = ".d.ts"   # ".d.ts" files = type signatures only, like C header files (.h)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def read_text(path):
    """Read a file as UTF-8 text, tolerating odd bytes. Returns '' on failure."""
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return ""


def strip_comments_and_strings(code):
    """
    Remove // line comments, /* block comments */, and the *contents* of
    string/template literals. This keeps our later regexes from matching
    keywords that merely appear inside text or comments.

    We replace string bodies with empty quotes so the surrounding code
    structure (commas, parens) stays intact.
    """
    out = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        two = code[i:i + 2]

        # Line comment: // ... end of line
        if two == "//":
            j = code.find("\n", i)
            i = n if j == -1 else j
            continue

        # Block comment: /* ... */
        if two == "/*":
            j = code.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue

        # String / template literals: ' " `
        if c in "'\"`":
            quote = c
            i += 1
            while i < n:
                if code[i] == "\\":       # skip escaped char
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                i += 1
            out.append(quote + quote)     # keep an empty placeholder ""
            continue

        out.append(c)
        i += 1

    return "".join(out)


def human_size(num):
    """Bytes -> human readable, e.g. 12.3 KB."""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024.0:
            return "%3.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f TB" % num


# --------------------------------------------------------------------------- #
# Regex patterns for "important" declarations.
#
# Note for the regex-wary: these are deliberately simple. They catch the
# common, idiomatic ways people declare things. Unusual formatting may slip
# past -- that's acceptable for an overview map.
# --------------------------------------------------------------------------- #

# `export` makes a thing visible to other files (like Python not prefixing
# with `_`, or C# `public`, or a C symbol in a header).
RX = {
    # export function foo(...)   /  export async function foo(...)
    "function": re.compile(
        r'^\s*export\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)',
        re.M),

    # export class Foo  (optionally: extends Bar / implements Baz)
    "class": re.compile(
        r'^\s*export\s+(?:default\s+|abstract\s+)*class\s+([A-Za-z_$][\w$]*)'
        r'(?:\s+extends\s+([A-Za-z_$][\w$.]*))?'
        r'(?:\s+implements\s+([^\{]+))?',
        re.M),

    # export interface Foo   -> like a C# interface / Python Protocol / C struct of fields
    "interface": re.compile(
        r'^\s*export\s+interface\s+([A-Za-z_$][\w$]*)', re.M),

    # export type Foo = ...  -> a named type alias (no direct C equivalent;
    #                            think C# `using` alias or a typedef)
    "type": re.compile(
        r'^\s*export\s+type\s+([A-Za-z_$][\w$]*)', re.M),

    # export enum Foo  -> exactly like a C/C# enum
    "enum": re.compile(
        r'^\s*export\s+(?:const\s+)?enum\s+([A-Za-z_$][\w$]*)', re.M),

    # export const X = ...  /  export let X  /  export var X
    # Top-level constants and (often) arrow-function definitions live here.
    "const": re.compile(
        r'^\s*export\s+(?:default\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)', re.M),
}

# A React component is, by convention, a function/const whose name starts
# with a Capital letter and that returns JSX. We approximate: capitalized
# exported const/function in a .tsx/.jsx file.
RX_REACT_HINT = re.compile(r'return\s*\(?\s*<')   # returns something like <div>...

# import ... from "module"     (ES module import -- like Python's `from x import y`)
RX_IMPORT_FROM = re.compile(r'^\s*import\s+(?:type\s+)?(.+?)\s+from\s+[\'"]([^\'"]+)[\'"]', re.M)
# import "module"              (side-effect import, runs the module for effects)
RX_IMPORT_BARE = re.compile(r'^\s*import\s+[\'"]([^\'"]+)[\'"]', re.M)
# const x = require("module")  (older CommonJS style -- like a plain Python import)
RX_REQUIRE = re.compile(r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)')


# --------------------------------------------------------------------------- #
# Per-file analysis
# --------------------------------------------------------------------------- #

def analyze_source_file(path):
    """Return a dict describing the important, exported pieces of one file."""
    raw = read_text(path)
    clean = strip_comments_and_strings(raw)
    # For imports we need the string literals INTACT (the module path is a
    # string), but still want comments gone so we don't pick up commented-out
    # imports. This variant keeps strings, drops comments.
    clean_keep_strings = strip_comments_and_strings_for_json(raw)

    info = {
        "path": path,
        "bytes": len(raw.encode("utf-8", "replace")),
        "lines": raw.count("\n") + 1 if raw else 0,
        "is_declaration": path.endswith(DECLARATION_SUFFIX),
        "exports": {k: [] for k in RX},
        "imports": [],            # list of imported module specifiers
        "react_components": [],   # likely React component names
        "has_default_export": "export default" in clean,
    }

    for kind, pattern in RX.items():
        for m in pattern.finditer(clean):
            name = m.group(1)
            extra = ""
            if kind == "class":
                parent = m.group(2)
                if parent:
                    extra = " extends %s" % parent
            info["exports"][kind].append(name + extra)

    # Imports: gather every module this file depends on.
    seen = set()
    for m in RX_IMPORT_FROM.finditer(clean_keep_strings):
        spec = m.group(2)
        if spec not in seen:
            seen.add(spec)
            info["imports"].append(spec)
    for m in RX_IMPORT_BARE.finditer(clean_keep_strings):
        spec = m.group(1)
        if spec not in seen:
            seen.add(spec)
            info["imports"].append(spec)
    for m in RX_REQUIRE.finditer(clean_keep_strings):
        spec = m.group(1)
        if spec not in seen:
            seen.add(spec)
            info["imports"].append(spec)

    # React component guess (only meaningful in .tsx/.jsx).
    if path.endswith((".tsx", ".jsx")) and RX_REACT_HINT.search(clean):
        candidates = info["exports"]["function"] + info["exports"]["const"]
        for name in candidates:
            base = name.split(" ")[0]
            if base[:1].isupper():
                info["react_components"].append(base)

    return info


# --------------------------------------------------------------------------- #
# Project-level config readers
# --------------------------------------------------------------------------- #

def load_json_loose(path):
    """
    Parse JSON, tolerating // and /* */ comments and trailing commas, which
    are common in tsconfig.json (technically 'JSONC'). Returns {} on failure.
    """
    text = read_text(path)
    if not text:
        return {}
    text = strip_comments_and_strings_for_json(text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)   # drop trailing commas
    try:
        return json.loads(text)
    except ValueError:
        return {}


def strip_comments_and_strings_for_json(text):
    """Like strip_comments_and_strings but PRESERVES string contents (JSON needs them)."""
    out = []
    i, n = 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if two == "/*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def find_package_jsons(root):
    """Find all package.json files (a monorepo can have several)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "package.json" in filenames:
            found.append(os.path.join(dirpath, "package.json"))
    return found


# --------------------------------------------------------------------------- #
# Report sections (each appends lines to a list `L`)
# --------------------------------------------------------------------------- #

def section(L, title):
    L.append("")
    L.append("=" * 70)
    L.append(title)
    L.append("=" * 70)


def report_overview(L, root, pkg_paths):
    section(L, "1. PROJECT OVERVIEW")
    L.append("Analyzed folder: %s" % os.path.abspath(root))
    if not pkg_paths:
        L.append("No package.json found. This may not be a Node/TS project,")
        L.append("or it's a loose collection of scripts.")
        return

    # The root-most package.json is the main project descriptor.
    main_pkg_path = min(pkg_paths, key=lambda p: len(p))
    pkg = load_json_loose(main_pkg_path)
    L.append("Main manifest:   %s" % main_pkg_path)
    L.append("  (package.json is like Python's pyproject.toml or a .csproj file:")
    L.append("   it names the project, lists libraries, and defines commands.)")
    L.append("")
    L.append("  name:        %s" % pkg.get("name", "(unnamed)"))
    L.append("  version:     %s" % pkg.get("version", "(none)"))
    if pkg.get("description"):
        L.append("  description: %s" % pkg["description"])
    if pkg.get("type"):
        L.append("  module type: %s   ('module' = modern import/export; "
                 "'commonjs' = older require())" % pkg["type"])
    if len(pkg_paths) > 1:
        L.append("")
        L.append("  NOTE: %d package.json files found -> this is a MONOREPO" % len(pkg_paths))
        L.append("  (multiple sub-projects in one repo). They are:")
        for p in sorted(pkg_paths, key=len):
            L.append("    - %s" % p)


def report_run_commands(L, pkg_paths):
    section(L, "2. HOW TO BUILD / RUN / TEST IT")
    L.append("These come from the \"scripts\" block in package.json.")
    L.append("You run them with:  npm run <name>   (or yarn/pnpm <name>)")
    L.append("Think of them as a Makefile's targets.")
    if not pkg_paths:
        L.append("  (no package.json -> no defined scripts)")
        return
    main_pkg = load_json_loose(min(pkg_paths, key=len))
    scripts = main_pkg.get("scripts", {})
    if not scripts:
        L.append("  (no scripts defined)")
        return
    # Highlight the commands people care about most, in a sensible order.
    priority = ["dev", "start", "build", "test", "lint", "typecheck", "format"]
    shown = set()
    L.append("")
    for key in priority:
        if key in scripts:
            L.append("  npm run %-10s ->  %s" % (key, scripts[key]))
            shown.add(key)
    for key, val in scripts.items():
        if key not in shown:
            L.append("  npm run %-10s ->  %s" % (key, val))


def report_dependencies(L, pkg_paths):
    section(L, "3. LIBRARIES IT DEPENDS ON")
    L.append("\"dependencies\"     = needed to RUN the program (like requirements.txt).")
    L.append("\"devDependencies\"  = needed only to BUILD/TEST it (compilers, linters).")
    if not pkg_paths:
        L.append("  (no package.json)")
        return
    pkg = load_json_loose(min(pkg_paths, key=len))
    deps = pkg.get("dependencies", {})
    dev = pkg.get("devDependencies", {})

    if deps:
        L.append("")
        L.append("  Runtime dependencies (%d):" % len(deps))
        for name, ver in sorted(deps.items()):
            note = _dep_hint(name)
            L.append("    %-30s %-10s %s" % (name, ver, note))
    if dev:
        L.append("")
        L.append("  Dev/build dependencies (%d):" % len(dev))
        for name, ver in sorted(dev.items()):
            note = _dep_hint(name)
            L.append("    %-30s %-10s %s" % (name, ver, note))


# A few hints for very common packages, so a newcomer knows what they're seeing.
_DEP_HINTS = {
    "react": "UI library (component-based front-end)",
    "react-dom": "renders React into a web page",
    "next": "Next.js full-stack React framework",
    "express": "HTTP web server framework (like Flask)",
    "fastify": "fast HTTP web server framework",
    "typescript": "the TypeScript compiler (tsc)",
    "vite": "fast build tool / dev server",
    "webpack": "module bundler",
    "esbuild": "very fast bundler/compiler",
    "jest": "test framework (like pytest)",
    "vitest": "test framework (Vite-native, like pytest)",
    "mocha": "test framework",
    "eslint": "linter (style/error checker)",
    "prettier": "code formatter (like black)",
    "axios": "HTTP client (like requests)",
    "zod": "runtime data validation (like pydantic)",
    "prisma": "database ORM",
    "typeorm": "database ORM",
    "@types/node": "type definitions for Node.js built-ins",
    "dotenv": "loads .env config files",
    "lodash": "utility helper functions",
}


def _dep_hint(name):
    if name in _DEP_HINTS:
        return "<- " + _DEP_HINTS[name]
    if name.startswith("@types/"):
        return "<- type definitions (headers) for '%s'" % name[len("@types/"):]
    return ""


def report_tsconfig(L, root):
    section(L, "4. COMPILER SETTINGS (tsconfig.json)")
    path = os.path.join(root, "tsconfig.json")
    if not os.path.exists(path):
        # look one level down too
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if "tsconfig.json" in filenames:
                path = os.path.join(dirpath, "tsconfig.json")
                break
    if not os.path.exists(path):
        L.append("  No tsconfig.json found (project may be plain JavaScript).")
        return
    cfg = load_json_loose(path)
    opts = cfg.get("compilerOptions", {})
    L.append("Found: %s" % path)
    L.append("tsconfig.json controls how TypeScript is turned into JavaScript.")
    L.append("")
    interesting = {
        "target": "JS version to output (e.g. ES2020)",
        "module": "module system used in output",
        "rootDir": "where source code lives",
        "outDir": "where compiled .js is written",
        "strict": "strict type checking on/off (true = safest)",
        "jsx": "how JSX (UI markup) is compiled",
        "baseUrl": "base for non-relative imports",
        "esModuleInterop": "smooths importing CommonJS modules",
    }
    for key, desc in interesting.items():
        if key in opts:
            L.append("  %-18s = %-22s (%s)" % (key, json.dumps(opts[key]), desc))
    paths = opts.get("paths")
    if paths:
        L.append("")
        L.append("  Import path aliases (shorthands you'll see in imports):")
        for alias, targets in paths.items():
            L.append("    %-15s -> %s" % (alias, ", ".join(targets)))


def report_entry_points(L, root, pkg_paths, files):
    section(L, "5. ENTRY POINTS (where execution starts)")
    L.append("This is the most useful thing to find first: the function/file")
    L.append("that runs when the program starts -- like Python's")
    L.append("`if __name__ == '__main__'` or C's `int main()`.")
    L.append("")
    candidates = []

    # From package.json: "main", "module", "bin", and dev/start scripts.
    if pkg_paths:
        pkg = load_json_loose(min(pkg_paths, key=len))
        for key in ("main", "module", "exports"):
            if key in pkg and isinstance(pkg[key], str):
                candidates.append(("package.json \"%s\"" % key, pkg[key]))
        bins = pkg.get("bin")
        if isinstance(bins, str):
            candidates.append(("package.json \"bin\" (CLI command)", bins))
        elif isinstance(bins, dict):
            for cmd, target in bins.items():
                candidates.append(("CLI command '%s'" % cmd, target))

    # Common conventional entry filenames.
    common_names = ("index.ts", "index.tsx", "main.ts", "main.tsx",
                    "app.ts", "app.tsx", "server.ts", "cli.ts", "index.js", "main.js")
    rel_files = {os.path.relpath(f["path"], root).replace("\\", "/") for f in files}
    for name in common_names:
        for rel in rel_files:
            if rel == name or rel.endswith("/" + name) or rel == "src/" + name:
                candidates.append(("conventional file", rel))

    if not candidates:
        L.append("  Could not confidently identify an entry point.")
        L.append("  Look for files named index/main/app/server, or check the")
        L.append("  \"dev\"/\"start\" scripts in section 2.")
        return

    seen = set()
    for why, target in candidates:
        key = target
        if key in seen:
            continue
        seen.add(key)
        L.append("  %-40s  [%s]" % (target, why))


def report_file_tree(L, root, files):
    section(L, "6. SOURCE FILE INVENTORY")
    L.append("Every source file found, with size and line count.")
    L.append("'.d.ts' files are type-only declarations (like C .h headers).")
    L.append("")
    total_lines = sum(f["lines"] for f in files)
    total_bytes = sum(f["bytes"] for f in files)
    L.append("  %d source files,  %s lines,  %s total" %
             (len(files), "{:,}".format(total_lines), human_size(total_bytes)))
    L.append("")
    # Sort biggest-first: large files are usually the most important.
    for f in sorted(files, key=lambda x: x["lines"], reverse=True):
        rel = os.path.relpath(f["path"], root).replace("\\", "/")
        tag = " (declarations)" if f["is_declaration"] else ""
        L.append("  %6d lines  %10s  %s%s" %
                 (f["lines"], human_size(f["bytes"]), rel, tag))


def report_file_details(L, root, files, max_files):
    section(L, "7. WHAT EACH FILE DEFINES (the public API)")
    L.append("For each file: the exported (publicly visible) declarations and")
    L.append("what it imports. 'export' = visible to other files, like C# 'public'")
    L.append("or a symbol in a C header. No 'export' = private to that file.")
    L.append("")

    # Skip declaration files in the detail dump; they're rarely edited by hand.
    detail_files = [f for f in files if not f["is_declaration"]]
    # Order: by path, so it reads like a directory walk.
    detail_files.sort(key=lambda x: x["path"])

    shown = 0
    for f in detail_files:
        if max_files and shown >= max_files:
            L.append("... (stopped after %d files; use --max-files to change)" % max_files)
            break
        rel = os.path.relpath(f["path"], root).replace("\\", "/")

        # Build a compact list of what's exported.
        pieces = []
        labels = {
            "function": "functions",
            "class": "classes",
            "interface": "interfaces",
            "type": "types",
            "enum": "enums",
            "const": "constants/vars",
        }
        for kind in ("class", "function", "interface", "type", "enum", "const"):
            names = f["exports"][kind]
            if names:
                pieces.append((labels[kind], names))

        # Only print files that actually export something or import notably.
        if not pieces and not f["react_components"] and not f["imports"]:
            continue

        L.append("-" * 70)
        L.append(rel)
        if f["has_default_export"]:
            L.append("  (has a DEFAULT export -- the file's primary thing, imported")
            L.append("   without braces: `import Thing from './file'`)")
        if f["react_components"]:
            L.append("  React components: %s" % ", ".join(sorted(set(f["react_components"]))))
        for label, names in pieces:
            L.append("  %-15s: %s" % (label, ", ".join(names)))

        # Imports, split into external libraries vs local files.
        if f["imports"]:
            local = [m for m in f["imports"] if m.startswith(".") or m.startswith("/")]
            external = [m for m in f["imports"] if not (m.startswith(".") or m.startswith("/"))]
            if external:
                L.append("  imports libs : %s" % ", ".join(sorted(set(external))))
            if local:
                L.append("  imports local: %s" % ", ".join(sorted(set(local))))
        shown += 1


def report_glossary(L):
    section(L, "8. TYPESCRIPT CHEAT-SHEET (for Python / C# / C developers)")
    glossary = [
        ("let / const x = 5",
         "Variable. 'const' can't be reassigned. Types are inferred."),
        ("let x: number = 5",
         "Explicit type annotation. ': number' is like C# 'int x' but written after."),
        ("function f(a: string): boolean { }",
         "Typed function. Param type after name, return type after the ')'."),
        ("const f = (a: number) => a + 1",
         "Arrow function = lambda. Like Python 'lambda a: a+1' but can have a body."),
        ("interface User { id: number; name: string }",
         "A shape/contract for an object. Like a C struct or C# interface; no runtime cost."),
        ("type ID = string | number",
         "Type alias. '|' = union = 'either type'. Like C# 'object' but checked."),
        ("x?: string",
         "Optional field/param (may be undefined). Like C# 'string?' nullable."),
        ("x!: string",
         "'Trust me, it's not null' assertion. Suppresses a null warning."),
        ("x as Foo",
         "Type cast. Like C# '(Foo)x' or C '(Foo*)x'. No runtime check."),
        ("a?.b?.c",
         "Optional chaining: stops at null/undefined instead of crashing."),
        ("a ?? b",
         "Nullish coalescing: use 'a' unless it's null/undefined, then 'b'."),
        ("`hello ${name}`",
         "Template string = Python f-string: f'hello {name}'. Uses backticks."),
        ("export / import",
         "Module visibility. 'export' = public. 'import {x} from \"./y\"' pulls x in."),
        ("export default X",
         "The file's single main export; imported without braces."),
        ("async function / await",
         "Same idea as Python's async/await. Returns a Promise (a future/Task)."),
        ("Promise<T>",
         "A future value of type T. Like C# Task<T> or Python's awaitable."),
        ("[1,2,3].map(x => x*2)",
         "Like Python list comprehension / LINQ .Select(). Also .filter, .reduce."),
        ("{ ...obj, x: 1 }",
         "Spread: copy obj's fields, then override x. Like Python {**d, 'x':1}."),
        ("const { a, b } = obj",
         "Destructuring: pull fields into variables. Like Python a,b = ..."),
        ("enum Color { Red, Green }",
         "Same as a C/C# enum."),
        ("class C extends B implements I",
         "OOP. 'extends' = inherit (one parent). 'implements' = satisfy interface(s)."),
        ("<T>(x: T): T => x",
         "Generics. <T> is a type parameter, like C# <T> or C++ templates."),
        (".tsx / JSX: <div>{x}</div>",
         "HTML-like UI markup embedded in code (React). {x} drops in a value."),
        ("null vs undefined",
         "Two 'empty' values. undefined = never set; null = explicitly empty."),
        ("===  vs  ==",
         "Always use === (strict equality, no type coercion). == is bug-prone."),
    ]
    L.append("")
    for syntax, meaning in glossary:
        L.append("  %-34s %s" % (syntax, meaning))
    L.append("")
    L.append("Rule of thumb: types (the ': Foo' bits, interfaces, type aliases)")
    L.append("are ERASED at runtime -- they exist only to catch mistakes while")
    L.append("editing/compiling. The actual running code is plain JavaScript.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def collect_source_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in SOURCE_EXTS:
                files.append(analyze_source_file(os.path.join(dirpath, name)))
    return files


def parse_args(argv):
    opts = {"root": ".", "md": None, "max_files": 0, "glossary": True}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif a == "--md":
            i += 1
            opts["md"] = argv[i]
        elif a == "--max-files":
            i += 1
            opts["max_files"] = int(argv[i])
        elif a == "--no-glossary":
            opts["glossary"] = False
        elif a.startswith("-"):
            print("Unknown option: %s (use --help)" % a)
            sys.exit(2)
        else:
            opts["root"] = a
        i += 1
    return opts


def main():
    opts = parse_args(sys.argv[1:])
    root = opts["root"]

    if not os.path.isdir(root):
        print("Error: '%s' is not a directory." % root)
        sys.exit(1)

    pkg_paths = find_package_jsons(root)
    files = collect_source_files(root)

    L = []
    L.append("#" * 70)
    L.append("#  TYPESCRIPT PROJECT ANALYSIS")
    L.append("#  (a map of the project for someone who doesn't know TypeScript)")
    L.append("#" * 70)

    report_overview(L, root, pkg_paths)
    report_run_commands(L, pkg_paths)
    report_dependencies(L, pkg_paths)
    report_tsconfig(L, root)
    report_entry_points(L, root, pkg_paths, files)
    report_file_tree(L, root, files)
    report_file_details(L, root, files, opts["max_files"])
    if opts["glossary"]:
        report_glossary(L)

    L.append("")
    L.append("Done. Suggested reading order: section 5 (entry points) -> the")
    L.append("entry file in section 7 -> follow its 'imports local' to trace the")
    L.append("program. Keep section 8 (cheat-sheet) open while you read code.")

    text = "\n".join(L)

    if not files and not pkg_paths:
        print(text)
        print("\nNOTE: No TypeScript/JavaScript files or package.json were found in")
        print("'%s'. Point this tool at a real TS project folder." % os.path.abspath(root))
        return

    print(text)

    if opts["md"]:
        # Wrap in a fenced code block so it renders cleanly as Markdown.
        with io.open(opts["md"], "w", encoding="utf-8") as f:
            f.write("# TypeScript Project Analysis\n\n```\n")
            f.write(text)
            f.write("\n```\n")
        print("\n[Markdown report written to %s]" % opts["md"])


if __name__ == "__main__":
    main()
