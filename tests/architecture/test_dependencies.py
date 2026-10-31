"""Тест напрямку залежностей: доменний шар імпортує лише стандартну бібліотеку та сам себе."""

import ast
import sys
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "ticketing" / "domain"


def imported_modules(path: Path) -> list[tuple[str, int]]:
    """Повертає абсолютні імпорти файлу разом із номерами рядків."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.append((node.module, node.lineno))
    return modules


def is_allowed_in_domain(module: str) -> bool:
    top_level = module.split(".")[0]
    is_domain = module == "ticketing.domain" or module.startswith("ticketing.domain.")
    return top_level in sys.stdlib_module_names or is_domain


def test_domain_imports_only_standard_library_and_itself():
    domain_files = sorted(DOMAIN_DIR.glob("*.py"))
    violations = [
        f"{path.name}:{line} імпортує {module}"
        for path in domain_files
        for module, line in imported_modules(path)
        if not is_allowed_in_domain(module)
    ]

    assert domain_files, f"Не знайдено файлів доменного шару в {DOMAIN_DIR}"
    assert not violations, "Доменний шар порушує напрямок залежностей:\n" + "\n".join(violations)