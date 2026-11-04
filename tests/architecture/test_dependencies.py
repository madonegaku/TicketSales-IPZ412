"""Тест напрямку залежностей: доменний шар кожного сервісу імпортує лише стандартну бібліотеку та сам себе."""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVICES = sorted(path.parent.parent.name for path in ROOT.glob("*/domain/__init__.py"))


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


def is_allowed_in_domain(module: str, service: str) -> bool:
    top_level = module.split(".")[0]
    own_domain = f"{service}.domain"
    is_own_domain = module == own_domain or module.startswith(own_domain + ".")
    return top_level in sys.stdlib_module_names or is_own_domain


def test_services_are_found():
    assert SERVICES, f"Не знайдено жодного сервісу з доменним шаром у {ROOT}"


@pytest.mark.parametrize("service", SERVICES)
def test_domain_imports_only_standard_library_and_itself(service):
    domain_files = sorted((ROOT / service / "domain").glob("*.py"))
    violations = [
        f"{service}/domain/{path.name}:{line} імпортує {module}"
        for path in domain_files
        for module, line in imported_modules(path)
        if not is_allowed_in_domain(module, service)
    ]

    assert not violations, "Доменний шар порушує напрямок залежностей:\n" + "\n".join(violations)