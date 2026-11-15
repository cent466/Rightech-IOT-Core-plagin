"""Local utilities shared by model replay and SVG quality checks."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MISSING = object()
VARIABLE = re.compile(r"{{\s*([^{}]+?)\s*}}")


class InputError(ValueError):
    pass


class DependencyUnavailable(RuntimeError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise InputError("duplicate JSON key")
        result[key] = value
    return result


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError("nonfinite JSON value")))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError("input unreadable or invalid") from exc


def write(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def unwrap_model(value):
    if isinstance(value, dict) and "store" in value:
        if value["store"] != "models" or type(value.get("version")) is not int or value["version"] != 1:
            raise InputError("expected a version 1 model export")
        value = value.get("data")
    if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
        raise InputError("model tree unavailable")
    return value


def walk(node, active=True, in_action=False):
    if not isinstance(node, dict):
        raise InputError("model node must be an object")
    active = active and node.get("active", True) is not False
    yield node, active, in_action
    children = node.get("children", [])
    if not isinstance(children, list):
        raise InputError("children must be an array")
    for child in children:
        yield from walk(child, active, in_action or node.get("type") == "action")


def lookup(value, path, *, bit_source=False):
    if not isinstance(path, str):
        return MISSING
    if isinstance(value, dict) and path in value:
        return value[path]
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, MISSING)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else MISSING
        elif isinstance(current, int) and not isinstance(current, bool) and part.isdigit():
            if not bit_source or current < 0:
                raise NotImplementedError
            current = bool((current >> int(part)) & 1)
        else:
            return MISSING
        if current is MISSING:
            return MISSING
    return current


def type_matches(value, dtype):
    if dtype == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if dtype == "boolean":
        return isinstance(value, bool)
    if dtype == "string":
        return isinstance(value, str)
    if dtype == "object":
        return isinstance(value, dict)
    if dtype in ("number[]", "string[]", "boolean[]"):
        return isinstance(value, list) and all(type_matches(v, dtype[:-2]) for v in value)
    return False


def template(text, context, inputs):
    if not isinstance(text, str):
        return text

    def replace(match):
        expression = match.group(1)
        value = lookup(context, expression) if expression.startswith("object.") else lookup(inputs, expression)
        if value is MISSING or value is None:
            raise InputError("template variable unresolved")
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return "true" if value is True else "false" if value is False else str(value)

    rendered = VARIABLE.sub(replace, text)
    if "{{" in rendered or "}}" in rendered:
        raise InputError("template syntax invalid")
    return rendered


def schema_check(value, filename):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise DependencyUnavailable("jsonschema unavailable") from exc
    if list(Draft202012Validator(load(ROOT/"schemas"/filename)).iter_errors(value)):
        raise InputError("input does not match schema")
