"""Execute an explicit local subset of model mappings, not the RIC runtime."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from model_tools import MISSING, InputError, DependencyUnavailable, load, lookup, template, type_matches, walk, write, unwrap_model, schema_check
from validate import validate_entity


def decode(value, dtype):
    if isinstance(value, str) and dtype != "string":
        try:
            value = json.loads(value)
        except ValueError:
            pass
    if not type_matches(value, dtype):
        raise InputError("input type mismatch")
    return value


def mapped_state(model, case):
    packet = case.get("packet", {})
    context = {"object": case.get("object", {})}
    kind = case["kind"]
    state = {}
    pending = [n for n, active, in_action in walk(model["data"])
               if active and not in_action and n.get("type") == "argument" and n.get("source", "state") == "state"]
    unresolved = set()
    for _ in range(len(pending) + 1):
        remaining = []
        progressed = False
        for node in pending:
            ref = node.get("reference")
            if not ref or node.get("parser") or node.get("dataType") not in {"number", "boolean", "string", "object", "number[]", "string[]", "boolean[]"}:
                unresolved.add(node["id"])
                progressed = True
                continue
            if any(ref.startswith(key + ".") for key in unresolved):
                unresolved.add(node["id"])
                progressed = True
                continue
            ref = template(ref, context, {})
            value = MISSING
            if kind == "mqtt":
                if ref == packet.get("topic"):
                    value = packet.get("payload", MISSING)
                else:
                    prefixes = [key for key in state if ref.startswith(key + ".")]
                    if prefixes:
                        key = max(prefixes, key=len)
                        value = lookup(state[key], ref[len(key)+1:])
            elif kind == "decoded":
                data = packet.get("data", {})
                # The caller must declare which integer sources use bit indexing.
                bit_roots = case.get("bit_sources", [])
                value = lookup(data, ref, bit_source=any(ref.startswith(key + ".") for key in bit_roots))
            else:
                raise NotImplementedError
            if value is MISSING:
                remaining.append(node)
                continue
            value = decode(value, node.get("dataType"))
            factor = node.get("factor", 1)
            if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not math.isfinite(factor):
                raise InputError("numeric factor invalid")
            if node.get("dataType") == "number":
                value *= factor
                if not math.isfinite(value):
                    raise InputError("numeric result is nonfinite")
            elif factor != 1:
                raise InputError("factor used with nonnumeric input")
            state[node["id"]] = value
            progressed = True
        pending = remaining
        if not progressed:
            break
    return state, unresolved


def command(model, case):
    node = next((n for n, active, _ in walk(model["data"]) if active and n.get("type") == "action" and n["id"] == case["action"]), None)
    if node is None:
        raise InputError("command unavailable")
    inputs = dict(case.get("inputs", {}))
    aliases = {}
    for child, active, _ in walk(node):
        if not active or child.get("type") != "argument" or child.get("source") != "config":
            continue
        value = lookup(inputs, child["id"])
        if value is MISSING:
            value = lookup(inputs, child["id"].rsplit(".", 1)[-1])
        if value is MISSING or not type_matches(value, child.get("dataType")):
            raise InputError("command argument missing or type invalid")
        alias = child["id"].rsplit(".", 1)[-1]
        if alias in aliases and aliases[alias] != child["id"]:
            raise InputError("command input aliases are ambiguous")
        if alias in inputs and child["id"] in inputs and not equal(inputs[alias], inputs[child["id"]]):
            raise InputError("command input aliases disagree")
        aliases[alias] = child["id"]
        inputs[child["id"]] = inputs[alias] = value
        opts = child.get("opts", {})
        if child.get("dataType") == "number":
            if "min" in opts and value < opts["min"] or "max" in opts and value > opts["max"]:
                raise InputError("command argument outside bounds")
    context = {"object": case.get("object", {})}
    params = {k: template(v, context, inputs) for k, v in node.get("params", {}).items()}
    if case.get("payload_format") == "json":
        key = "payload" if node.get("command") == "publish" else "command" if node.get("command") == "text_command" else None
        if key is None:
            raise NotImplementedError
        try:
            json.loads(params.get(key, ""), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, TypeError):
            raise InputError("rendered command payload is not JSON")
    return {"service": node.get("service"), "command": node.get("command"), "params": params}


def equal(actual, expected):
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(equal(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def run(model, cases):
    model = unwrap_model(model)
    if validate_entity("models", model, "export").errors:
        raise InputError("model validation rejected input")
    schema_check(cases, "cases.schema.json")
    report = {"scope": "local_mapping_subset", "ric_verified": False, "cases": []}
    known = {n["id"] for n, _, in_action in walk(model["data"]) if not in_action and n.get("type") == "argument"}
    inherited = bool(model.get("disabled") or model.get("removed")) or any(
        n.get("base") and (n is not model["data"] or n["base"] != model.get("base"))
        for n, _, _ in walk(model["data"]))
    for case in cases["cases"]:
        result = {"name": case["name"], "status": "passed", "mismatched_ids": []}
        try:
            if inherited:
                raise NotImplementedError
            if case["kind"] == "command":
                if not equal(command(model, case), case["expected_command"]):
                    result["status"] = "failed"
                    result["reason"] = "command output mismatch"
            elif case["kind"] in {"mqtt", "decoded"}:
                packet = case.get("packet", {})
                if case["kind"] == "mqtt" and (not isinstance(packet.get("topic"), str) or not packet["topic"].strip() or "payload" not in packet):
                    raise InputError("MQTT topic and payload are required")
                if case["kind"] == "decoded" and not isinstance(packet.get("data"), dict):
                    raise InputError("decoded input requires a data object")
                if model.get("base") != "mqtt" and case["kind"] == "mqtt":
                    raise NotImplementedError
                payload = case.get("packet", {}).get("payload")
                if case["kind"] == "mqtt" and (isinstance(payload, list) or isinstance(payload, str) and payload.lstrip().startswith("[")):
                    raise NotImplementedError
                expected = case.get("expected", {})
                if not expected and not case.get("absent"):
                    raise InputError("case has no assertions")
                referenced = set(expected) | set(case.get("absent", []))
                if not referenced.issubset(known):
                    raise InputError("case refers to unknown node")
                state, unresolved = mapped_state(model, case)
                if referenced & unresolved:
                    raise NotImplementedError
                for id, value in expected.items():
                    actual = state.get(id, MISSING)
                    # Python considers False == 0; tests must not.
                    if actual is MISSING or not equal(actual, value):
                        result["mismatched_ids"].append(id)
                result["mismatched_ids"].extend(id for id in case.get("absent", []) if id in state)
                if result["mismatched_ids"]:
                    result["status"] = "failed"
            else:
                raise NotImplementedError
        except NotImplementedError:
            result.update(status="not_tested", reason="behavior is outside local replay subset")
        except (InputError, KeyError, TypeError, ValueError, OverflowError):
            result.update(status="failed", reason="input or template contract invalid")
        report["cases"].append(result)
    report["passed_count"] = sum(c["status"] == "passed" for c in report["cases"])
    report["failed_count"] = sum(c["status"] == "failed" for c in report["cases"])
    report["not_tested_count"] = sum(c["status"] == "not_tested" for c in report["cases"])
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model")
    ap.add_argument("cases")
    ap.add_argument("--out")
    args = ap.parse_args()
    try:
        report = run(load(args.model), load(args.cases))
        if args.out:
            if Path(args.out).resolve() in {Path(args.model).resolve(), Path(args.cases).resolve()}:
                raise InputError("report must differ from input")
            write(args.out, report)
    except DependencyUnavailable:
        print(json.dumps({"scope": "local_mapping_subset", "status": "not_tested", "ric_verified": False, "reason": "jsonschema unavailable"}))
        return 2
    except (InputError, ImportError, OSError, KeyError, TypeError, ValueError, RecursionError):
        print(json.dumps({"scope": "local_mapping_subset", "status": "failed", "ric_verified": False, "reason": "replay input rejected"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["failed_count"] or report["not_tested_count"]))


if __name__ == "__main__":
    sys.exit(main())
