"""How the add-on's modules import each other: never in a circle, counting the imports made
inside functions too, which only the modules a release can ship without (see dev/package.py)
may use."""

from __future__ import annotations

import ast
import os
import unittest

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"tests", "dev", "dist", "node_modules", "web", "docs", "user_files", "__pycache__"}
# imported where they are used, since a release may not have them
OPTIONAL = {"debug_events", "fake_forest", "settings.debug"}


def modules() -> dict:
    """{dotted name: path} of every module of the add-on ("" is the package itself)."""
    found = {}
    for folder, dirs, files in os.walk(ADDON):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(folder, name)
                parts = os.path.relpath(path, ADDON)[:-3].split(os.sep)
                found[".".join(parts[:-1] if parts[-1] == "__init__" else parts)] = path
    return found


def imports(name: str, path: str, known: dict) -> list:
    """[(module imported, inside a function?)] for the add-on's own modules `name` imports."""
    package = name.split(".") if path.endswith("__init__.py") else name.split(".")[:-1]
    if package == [""]:
        package = []
    found = []

    def visit(node, inside: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ImportFrom) and child.level:
                base = package[:len(package) - (child.level - 1)] + (child.module.split(".") if child.module else [])
                for alias in child.names:
                    sub = ".".join(base + [alias.name])
                    found.append((sub if sub in known else ".".join(base), inside))
            visit(child, inside or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))

    with open(path, encoding="utf-8") as f:
        visit(ast.parse(f.read()), False)
    return found


def cycle(graph: dict) -> list:
    """One circle of imports in `graph` ({module: {modules it imports}}), or []."""
    done, path = set(), []

    def walk(node):
        if node in path:
            return path[path.index(node):] + [node]
        if node in done:
            return []
        path.append(node)
        for nxt in sorted(graph.get(node, ())):
            found = walk(nxt)
            if found:
                return found
        path.pop()
        done.add(node)
        return []

    for start in sorted(graph):
        found = walk(start)
        if found:
            return found
    return []


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.known = modules()
        self.graph = {name: imports(name, path, self.known) for name, path in self.known.items()}

    def test_no_module_imports_itself_round_a_circle(self):
        graph = {name: {m for m, _inside in found if m != name} for name, found in self.graph.items()}
        self.assertEqual(cycle(graph), [], "these modules import each other in a circle")

    def test_only_optional_modules_are_imported_inside_functions(self):
        late = sorted(f"{name} -> {m}" for name, found in self.graph.items() for m, inside in found
                      if inside and m not in OPTIONAL)
        self.assertEqual(late, [], "import these at the top of the module (and break any circle that makes)")

    def test_it_finds_a_circle(self):
        self.assertEqual(cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}), ["a", "b", "c", "a"])
        self.assertEqual(cycle({"a": {"b"}, "b": set()}), [])


if __name__ == "__main__":
    unittest.main()
