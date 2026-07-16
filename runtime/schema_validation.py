"""Small JSON schema subset validator for PooleOS artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    path: str
    message: str


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate_json(value: Any, schema: dict[str, Any], *, path: str = "$") -> list[ValidationError]:
    errors: list[ValidationError] = []

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _type_ok(value, expected_type):
        return [ValidationError(path, f"expected {expected_type}, got {type(value).__name__}")]

    if "const" in schema and value != schema["const"]:
        errors.append(ValidationError(path, f"expected const {schema['const']!r}"))

    if "enum" in schema and value not in schema["enum"]:
        errors.append(ValidationError(path, f"not in enum {schema['enum']!r}"))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(ValidationError(f"{path}.{key}", "required field missing"))

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            allowed = set(properties)
            for key in value:
                if key not in allowed:
                    errors.append(ValidationError(f"{path}.{key}", "additional property not allowed"))

        for key, subschema in properties.items():
            if key in value and isinstance(subschema, dict):
                errors.extend(validate_json(value[key], subschema, path=f"{path}.{key}"))

    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(ValidationError(path, f"expected at least {min_items} item(s)"))
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(ValidationError(path, f"expected at most {max_items} item(s)"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_json(item, item_schema, path=f"{path}[{index}]"))

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(ValidationError(path, f"expected length >= {min_length}"))

    return errors

