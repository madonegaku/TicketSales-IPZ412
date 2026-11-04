"""Показники коду для ЛР 4 (табл. 4.2 методички): гілки виконання, рядки, вихідні залежності.

Запуск: python tools/measure.py <файл.py> [<файл.py> ...]

Для кожного методу й функції виводить:
- гілки – кількість точок розгалуження (if, elif, for, while, except, тернарний оператор,
  умова в генераторі, кожен додатковий операнд and/or); цикломатична складність = гілки + 1;
- рядки – кількість рядків коду без docstring.
Для кожного класу – вихідні залежності: імена, імпортовані модулем на верхньому рівні,
до яких звертається код класу (зокрема сторонні модулі – redis, httpx, json).
"""

import ast
import sys
from pathlib import Path

BRANCH_NODES = (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp, ast.AsyncFor)


def branches(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, BRANCH_NODES):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            count += len(child.ifs)
    return count


def code_lines(node: ast.AST) -> int:
    body = list(getattr(node, "body", []))
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if not body:
        return 0
    return body[-1].end_lineno - body[0].lineno + 1


def imported_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def used_names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def report(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = imported_names(tree)
    print(f"\n{path.as_posix()}")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            print(f"  {node.name}(): гілки {branches(node)}, рядки {code_lines(node)}")
        elif isinstance(node, ast.ClassDef):
            deps = sorted(used_names(node) & imports)
            total = branches(node)
            print(f"  клас {node.name}: гілки разом {total}, вихідні залежності {len(deps)} – {', '.join(deps) or '–'}")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    print(f"    {item.name}(): гілки {branches(item)}, рядки {code_lines(item)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for arg in sys.argv[1:]:
        report(Path(arg))
