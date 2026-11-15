"""Compose arbitrary agent-designed vector geometry; not a fixed icon picker."""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from model_tools import InputError, DependencyUnavailable, load, schema_check
import json
from validate_svg import validate


def draw(spec):
    schema_check(spec, "drawing.schema.json")
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": " ".join(map(str, spec["viewBox"]))})

    def append(parent, elements):
        for item in elements:
            child = ET.SubElement(parent, item["tag"], {k: str(v) for k, v in item.get("attrs", {}).items()})
            if "text" in item:
                child.text = item["text"]
            append(child, item.get("children", []))

    append(root, spec["elements"])
    text = ET.tostring(root, encoding="unicode")
    if any(f["severity"] == "error" for f in validate(text)):
        raise InputError("drawing violates portable SVG profile")
    return text + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("drawing")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    try:
        text = draw(load(args.drawing))
        path = Path(args.out)
        if path.resolve() == Path(args.drawing).resolve():
            raise InputError("output must differ from input")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except DependencyUnavailable:
        print(json.dumps({"status": "not_tested", "reason": "jsonschema unavailable"}))
        return 2
    except (InputError, OSError, ImportError):
        print(json.dumps({"status": "failed", "reason": "drawing rejected"}))
        return 2
    print(json.dumps({"status": "passed", "output": str(path), "ric_verified": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
