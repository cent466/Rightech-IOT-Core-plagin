"""Validate the deliberately small portable SVG profile for newly drawn icons."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "title", "desc"}
ATTRS = {"viewBox", "width", "height", "x", "y", "cx", "cy", "r", "rx", "ry", "x1", "x2", "y1", "y2",
         "d", "points", "fill", "stroke", "stroke-width", "fill-rule", "clip-rule", "stroke-linecap",
         "stroke-linejoin", "transform", "opacity", "fill-opacity", "stroke-opacity", "id", "role", "aria-label"}


def validate(text, *, legacy=False):
    findings = []

    def add(code, message, severity="error"):
        if legacy and code in {"SVG_VIEWBOX", "SVG_ELEMENT", "SVG_ATTRIBUTE", "SVG_PATH", "SVG_FIXED_COLOR", "SVG_REFERENCE", "SVG_GEOMETRY"}:
            severity = "warning"
        findings.append({"severity": severity, "code": code, "message": message})

    if not isinstance(text, str) or not text.strip():
        add("SVG_EMPTY", "SVG string is empty")
        return findings
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?(?!xml\s)", text, re.I):
        add("SVG_DECLARATION", "XML declarations with entities are outside the icon profile")
        return findings
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        add("SVG_XML", "SVG XML is invalid")
        return findings
    if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
        add("SVG_ROOT", "root element must be SVG")
    try:
        box = [float(v) for v in re.split(r"[\s,]+", root.attrib.get("viewBox", "").strip())]
        if len(box) != 4 or not all(math.isfinite(v) for v in box) or box[2] <= 0 or box[3] <= 0:
            raise ValueError
    except ValueError:
        add("SVG_VIEWBOX", "viewBox must contain four finite numbers with positive dimensions")
    geometries = 0
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag.lower() in {"script", "foreignobject", "image", "use", "a", "style", "animate", "animatetransform", "set", "iframe", "object", "embed"}:
            add("SVG_UNSAFE", "active or resource-loading elements are not allowed")
        if "}" in element.tag and not element.tag.startswith("{http://www.w3.org/2000/svg}"):
            add("SVG_NAMESPACE", "foreign XML namespaces are not allowed")
        if tag not in TAGS or ("}" in element.tag and not element.tag.startswith("{http://www.w3.org/2000/svg}")):
            add("SVG_ELEMENT", "element is outside the portable icon profile")
        if tag in TAGS - {"svg", "g", "title", "desc"}:
            geometries += 1
        if tag == "path" and not element.attrib.get("d", "").strip():
            add("SVG_PATH", "path geometry is empty")
        for attr, value in element.attrib.items():
            local_attr = attr.rsplit("}", 1)[-1].lower()
            if local_attr.startswith("on") or local_attr in {"href", "src"}:
                add("SVG_UNSAFE", "event handlers and resource references are not allowed")
            if attr not in ATTRS:
                add("SVG_ATTRIBUTE", "attribute is outside the portable icon profile")
            if attr in {"fill", "stroke"}:
                if value not in {"none", "currentColor", "inherit"}:
                    add("SVG_FIXED_COLOR", "fixed paint prevents inherited state color")
                if attr == "stroke" and value != "none":
                    add("SVG_STROKE", "stroke recoloring must be checked on target RIC", "warning")
            if re.search(r"url\s*\(|https?:|data:|javascript:", value, re.I):
                add("SVG_REFERENCE", "icon must not depend on external resources")
            if re.search(r"(?:https?:|file:|data:|javascript:|//)", value, re.I):
                add("SVG_EXTERNAL", "external resources are not allowed")
            if attr in {"opacity", "fill-opacity", "stroke-opacity"}:
                try:
                    if not 0 < float(value) <= 1:
                        raise ValueError
                except ValueError:
                    add("SVG_OPACITY", "opacity must be positive and at most one")
    if not geometries:
        add("SVG_GEOMETRY", "icon has no vector geometry")
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    report = []
    files = []
    for raw in args.paths:
        path = Path(raw)
        files.extend(sorted(path.glob("*.svg")) if path.is_dir() else [path])
    if not files:
        print(json.dumps({"status": "failed", "reason": "icons unavailable"}))
        return 2
    try:
        for path in files:
            report.append({"file": path.name, "findings": validate(path.read_text(encoding="utf-8"))})
    except (OSError, UnicodeError):
        print(json.dumps({"status": "failed", "reason": "icon unreadable"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(f["severity"] == "error" or args.strict for r in report for f in r["findings"]))


if __name__ == "__main__":
    sys.exit(main())
