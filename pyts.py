"""
pyts.py — convert a Python source file to TypeScript.

Usage:  python pyts.py input.py > output.ts
"""
import ast
import sys
from typing import Optional


TYPE_MAP = {
    "int": "number", "float": "number", "complex": "number",
    "str": "string", "bool": "boolean", "bytes": "Uint8Array",
    "None": "null", "NoneType": "null",
    "list": "Array", "List": "Array", "tuple": "Array", "Tuple": "Array",
    "dict": "Record", "Dict": "Record",
    "set": "Set", "Set": "Set",
    "Any": "any", "object": "any",
    "Callable": "Function", "Optional": "Optional",
}

BINOP = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
    ast.FloorDiv: "/", ast.Mod: "%", ast.Pow: "**",
    ast.LShift: "<<", ast.RShift: ">>",
    ast.BitOr: "|", ast.BitXor: "^", ast.BitAnd: "&",
}
CMPOP = {
    ast.Eq: "===", ast.NotEq: "!==", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=", ast.Is: "===", ast.IsNot: "!==",
}
BOOLOP = {ast.And: "&&", ast.Or: "||"}
UNARYOP = {ast.UAdd: "+", ast.USub: "-", ast.Not: "!", ast.Invert: "~"}


class Transpiler(ast.NodeVisitor):
    def __init__(self) -> None:
        self.indent = 0
        self.lines: list[str] = []

    # ---------- helpers ----------
    def emit(self, line: str = "") -> None:
        self.lines.append("  " * self.indent + line if line else "")

    def block(self, body: list[ast.stmt]) -> None:
        self.indent += 1
        for stmt in body:
            self.visit(stmt)
        self.indent -= 1

    def ann(self, node: Optional[ast.expr]) -> str:
        if node is None:
            return "any"
        if isinstance(node, ast.Name):
            return TYPE_MAP.get(node.id, node.id)
        if isinstance(node, ast.Constant) and node.value is None:
            return "null"
        if isinstance(node, ast.Subscript):
            base = self.ann(node.value)
            slc = node.slice
            if isinstance(slc, ast.Tuple):
                args = ", ".join(self.ann(e) for e in slc.elts)
            else:
                args = self.ann(slc)
            if base == "Record":
                return f"Record<{args}>"
            if base == "Optional":
                return f"{args} | null"
            if base == "Array":
                return f"Array<{args}>"
            return f"{base}<{args}>"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return f"{self.ann(node.left)} | {self.ann(node.right)}"
        return "any"

    # ---------- module ----------
    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self.visit(stmt)

    # ---------- imports ----------
    def visit_Import(self, node: ast.Import) -> None:
        for n in node.names:
            self.emit(f"// import {n.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        names = ", ".join(n.name for n in node.names)
        self.emit(f"// from {node.module} import {names}")

    # ---------- function & class ----------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        params = self._params(node.args)
        ret = self.ann(node.returns)
        kw = "function " if self.indent == 0 else ""
        self.emit(f"{kw}{node.name}({params}): {ret} {{")
        self.block(node.body)
        self.emit("}")

    visit_AsyncFunctionDef = visit_FunctionDef

    def _params(self, args: ast.arguments) -> str:
        out = []
        defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
        for a, d in zip(args.args, defaults):
            if a.arg == "self":
                continue
            piece = f"{a.arg}: {self.ann(a.annotation)}"
            if d is not None:
                piece += f" = {self.expr(d)}"
            out.append(piece)
        if args.vararg:
            out.append(f"...{args.vararg.arg}: any[]")
        return ", ".join(out)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [self.expr(b) for b in node.bases]
        ext = f" extends {bases[0]}" if bases else ""
        self.emit(f"class {node.name}{ext} {{")
        self.indent += 1
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                self._method(stmt)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                init = f" = {self.expr(stmt.value)}" if stmt.value else ""
                self.emit(f"{stmt.target.id}: {self.ann(stmt.annotation)}{init};")
            else:
                self.visit(stmt)
        self.indent -= 1
        self.emit("}")

    def _method(self, node: ast.FunctionDef) -> None:
        name = "constructor" if node.name == "__init__" else node.name
        params = self._params(node.args)
        ret = "" if name == "constructor" else f": {self.ann(node.returns)}"
        self.emit(f"{name}({params}){ret} {{")
        self.block(node.body)
        self.emit("}")

    # ---------- statements ----------
    def visit_Assign(self, node: ast.Assign) -> None:
        value = self.expr(node.value)
        for tgt in node.targets:
            if isinstance(tgt, ast.Tuple):
                names = ", ".join(self.expr(e) for e in tgt.elts)
                self.emit(f"let [{names}] = {value};")
            else:
                kw = "let " if isinstance(tgt, ast.Name) else ""
                self.emit(f"{kw}{self.expr(tgt)} = {value};")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        tgt = self.expr(node.target)
        typ = self.ann(node.annotation)
        if node.value is not None:
            self.emit(f"let {tgt}: {typ} = {self.expr(node.value)};")
        else:
            self.emit(f"let {tgt}: {typ};")

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        op = BINOP.get(type(node.op), "?")
        self.emit(f"{self.expr(node.target)} {op}= {self.expr(node.value)};")

    def visit_Expr(self, node: ast.Expr) -> None:
        self.emit(self.expr(node.value) + ";")

    def visit_Return(self, node: ast.Return) -> None:
        self.emit("return" + (f" {self.expr(node.value)}" if node.value else "") + ";")

    def visit_If(self, node: ast.If) -> None:
        self.emit(f"if ({self.expr(node.test)}) {{")
        self.block(node.body)
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                inner = node.orelse[0]
                self.emit(f"}} else if ({self.expr(inner.test)}) {{")
                self.block(inner.body)
                if inner.orelse:
                    self.emit("} else {")
                    self.block(inner.orelse)
            else:
                self.emit("} else {")
                self.block(node.orelse)
        self.emit("}")

    def visit_While(self, node: ast.While) -> None:
        self.emit(f"while ({self.expr(node.test)}) {{")
        self.block(node.body)
        self.emit("}")

    def visit_For(self, node: ast.For) -> None:
        tgt = self.expr(node.target)
        it = self.expr(node.iter)
        # range(...) → classic for-loop
        if isinstance(node.iter, ast.Call) and getattr(node.iter.func, "id", None) == "range":
            a = node.iter.args
            start = self.expr(a[0]) if len(a) > 1 else "0"
            stop = self.expr(a[1] if len(a) > 1 else a[0])
            step = self.expr(a[2]) if len(a) == 3 else "1"
            self.emit(f"for (let {tgt} = {start}; {tgt} < {stop}; {tgt} += {step}) {{")
        else:
            self.emit(f"for (const {tgt} of {it}) {{")
        self.block(node.body)
        self.emit("}")

    def visit_Pass(self, node: ast.Pass) -> None:
        self.emit("// pass")

    def visit_Break(self, node: ast.Break) -> None:
        self.emit("break;")

    def visit_Continue(self, node: ast.Continue) -> None:
        self.emit("continue;")

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = self.expr(node.exc) if node.exc else "new Error()"
        self.emit(f"throw {exc};")

    def visit_Try(self, node: ast.Try) -> None:
        self.emit("try {")
        self.block(node.body)
        for h in node.handlers:
            name = h.name or "e"
            self.emit(f"}} catch ({name}) {{")
            self.block(h.body)
        if node.finalbody:
            self.emit("} finally {")
            self.block(node.finalbody)
        self.emit("}")

    # ---------- expressions ----------
    def expr(self, node: Optional[ast.expr]) -> str:
        if node is None:
            return "undefined"
        method = getattr(self, f"e_{type(node).__name__}", None)
        return method(node) if method else f"/* ?{type(node).__name__} */"

    def e_Name(self, n: ast.Name) -> str:
        if n.id == "self":
            return "this"
        if n.id == "None":
            return "null"
        if n.id == "True":
            return "true"
        if n.id == "False":
            return "false"
        return n.id

    def e_Constant(self, n: ast.Constant) -> str:
        if n.value is None:
            return "null"
        if isinstance(n.value, bool):
            return "true" if n.value else "false"
        if isinstance(n.value, str):
            return '"' + n.value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return repr(n.value)

    def e_BinOp(self, n: ast.BinOp) -> str:
        op = BINOP.get(type(n.op), "?")
        s = f"{self.expr(n.left)} {op} {self.expr(n.right)}"
        return f"Math.floor({s})" if isinstance(n.op, ast.FloorDiv) else f"({s})"

    def e_BoolOp(self, n: ast.BoolOp) -> str:
        op = BOOLOP[type(n.op)]
        return "(" + f" {op} ".join(self.expr(v) for v in n.values) + ")"

    def e_UnaryOp(self, n: ast.UnaryOp) -> str:
        return f"({UNARYOP[type(n.op)]}{self.expr(n.operand)})"

    def e_Compare(self, n: ast.Compare) -> str:
        parts = [self.expr(n.left)]
        for op, c in zip(n.ops, n.comparators):
            if isinstance(op, ast.In):
                return f"{self.expr(c)}.includes({self.expr(n.left)})"
            if isinstance(op, ast.NotIn):
                return f"!{self.expr(c)}.includes({self.expr(n.left)})"
            parts.append(CMPOP.get(type(op), "?"))
            parts.append(self.expr(c))
        return "(" + " ".join(parts) + ")"

    def e_Call(self, n: ast.Call) -> str:
        # builtin remaps
        if isinstance(n.func, ast.Name):
            args = [self.expr(a) for a in n.args]
            name = n.func.id
            if name == "print":
                return f"console.log({', '.join(args)})"
            if name == "len":
                return f"{args[0]}.length"
            if name == "str":
                return f"String({args[0]})"
            if name == "int":
                return f"parseInt({args[0]} as any, 10)"
            if name == "float":
                return f"parseFloat({args[0]} as any)"
            if name == "list":
                return f"Array.from({args[0]})" if args else "[]"
            if name == "range":
                start = args[0] if len(args) > 1 else "0"
                stop = args[1] if len(args) > 1 else args[0]
                return f"Array.from({{length: {stop} - {start}}}, (_, i) => i + {start})"
        func = self.expr(n.func)
        call_args = ", ".join(self.expr(a) for a in n.args)
        return f"{func}({call_args})"

    def e_Attribute(self, n: ast.Attribute) -> str:
        return f"{self.expr(n.value)}.{n.attr}"

    def e_Subscript(self, n: ast.Subscript) -> str:
        if isinstance(n.slice, ast.Slice):
            lo = self.expr(n.slice.lower) if n.slice.lower else "0"
            hi = f", {self.expr(n.slice.upper)}" if n.slice.upper else ""
            return f"{self.expr(n.value)}.slice({lo}{hi})"
        return f"{self.expr(n.value)}[{self.expr(n.slice)}]"

    def e_List(self, n: ast.List) -> str:
        return "[" + ", ".join(self.expr(e) for e in n.elts) + "]"

    e_Tuple = e_List

    def e_Dict(self, n: ast.Dict) -> str:
        items = [f"{self.expr(k)}: {self.expr(v)}" for k, v in zip(n.keys, n.values)]
        return "{" + ", ".join(items) + "}"

    def e_Set(self, n: ast.Set) -> str:
        return f"new Set([{', '.join(self.expr(e) for e in n.elts)}])"

    def e_JoinedStr(self, n: ast.JoinedStr) -> str:
        parts = []
        for v in n.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value).replace("`", "\\`"))
            elif isinstance(v, ast.FormattedValue):
                parts.append("${" + self.expr(v.value) + "}")
        return "`" + "".join(parts) + "`"

    def e_ListComp(self, n: ast.ListComp) -> str:
        gen = n.generators[0]
        body = self.expr(n.elt)
        src = self.expr(gen.iter)
        tgt = self.expr(gen.target)
        result = f"{src}.map(({tgt}) => {body})"
        for cond in gen.ifs:
            result = f"{src}.filter(({tgt}) => {self.expr(cond)}).map(({tgt}) => {body})"
        return result

    def e_IfExp(self, n: ast.IfExp) -> str:
        return f"({self.expr(n.test)} ? {self.expr(n.body)} : {self.expr(n.orelse)})"

    def e_Lambda(self, n: ast.Lambda) -> str:
        params = self._params(n.args)
        return f"(({params}) => {self.expr(n.body)})"


def transpile(source: str) -> str:
    tree = ast.parse(source)
    t = Transpiler()
    t.visit(tree)
    return "\n".join(t.lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python pyts.py <input.py>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        print(transpile(f.read()))
