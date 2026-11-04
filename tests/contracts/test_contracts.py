"""Тести контрактів: специфікації в contracts/ коректні, посилання $ref ведуть на наявні описи,
а приклади повідомлень відповідають власним схемам."""

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator, FormatChecker
from openapi_spec_validator import validate

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
CONTRACT_FILES = sorted(CONTRACTS_DIR.glob("*.yaml"))
OPENAPI_FILES = sorted(CONTRACTS_DIR.glob("*.openapi.yaml"))
ASYNCAPI_FILES = sorted(CONTRACTS_DIR.glob("*.asyncapi.yaml"))


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def local_refs(node) -> list[str]:
    """Повертає всі локальні посилання $ref («#/…») з будь-якої глибини документа."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        refs = [ref] if isinstance(ref, str) and ref.startswith("#/") else []
        return refs + [r for value in node.values() for r in local_refs(value)]
    if isinstance(node, list):
        return [r for item in node for r in local_refs(item)]
    return []


def resolves(document: dict, ref: str) -> bool:
    """Перевіряє, що за шляхом «#/components/schemas/Назва» у документі є опис."""
    node = document
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def asyncapi_messages(path: Path) -> list[tuple[dict, str, dict]]:
    """Повертає (документ, посилання на схему корисного навантаження, повідомлення)."""
    document = load(path)
    return [
        (document, message["payload"]["$ref"], message)
        for message in document["components"]["messages"].values()
    ]


def test_contracts_exist():
    assert OPENAPI_FILES, f"Не знайдено OpenAPI-контрактів у {CONTRACTS_DIR}"
    assert ASYNCAPI_FILES, f"Не знайдено AsyncAPI-контрактів у {CONTRACTS_DIR}"


@pytest.mark.parametrize("path", OPENAPI_FILES, ids=lambda p: p.name)
def test_openapi_contract_is_valid(path):
    validate(load(path))


@pytest.mark.parametrize("path", CONTRACT_FILES, ids=lambda p: p.name)
def test_all_local_refs_resolve(path):
    document = load(path)
    broken = [ref for ref in local_refs(document) if not resolves(document, ref)]
    assert not broken, "Посилання ведуть на неіснуючі описи: " + ", ".join(broken)


@pytest.mark.parametrize("path", ASYNCAPI_FILES, ids=lambda p: p.name)
def test_asyncapi_examples_match_payload_schema(path):
    for document, payload_ref, message in asyncapi_messages(path):
        schema = {"$ref": payload_ref, "components": document["components"]}
        validator = Draft7Validator(schema, format_checker=FormatChecker())
        assert message.get("examples"), f"Повідомлення {message['name']} не має прикладів"
        for example in message["examples"]:
            errors = [error.message for error in validator.iter_errors(example["payload"])]
            assert not errors, f"Приклад {example['name']} не відповідає схемі: {errors}"