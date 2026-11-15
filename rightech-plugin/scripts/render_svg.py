"""Render real pixels plus a portable HTML contact sheet for SVG QA."""
from __future__ import annotations

import argparse
import html
import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from model_tools import InputError, DependencyUnavailable, write
from validate_svg import validate

COLORS = ["#2a9d64", "#d89b16", "#de4c55"]
BACKGROUNDS = ["#ffffff", "#20262e"]


def paint(text, color):
    root = ET.fromstring(text)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root.set("fill", color)
    root.set("color", color)
    return ET.tostring(root, encoding="unicode")


def raster(text, size):
    try:
        import cairosvg
    except (ImportError, OSError) as exc:
        raise DependencyUnavailable("CairoSVG unavailable") from exc
    return cairosvg.svg2png(bytestring=text.encode(), output_width=size, output_height=size)


def render(paths, out, sizes=(16, 24, 32)):
    if not paths or not sizes or any(type(s) is not int or not 8 <= s <= 512 for s in sizes):
        raise InputError("icons or render sizes invalid")
    sources = [(p.stem, p.read_text(encoding="utf-8")) for p in paths]
    for _, text in sources:
        if any(f["severity"] == "error" for f in validate(text)):
            raise InputError("SVG does not satisfy portable profile")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cards = []
    for name, text in sources:
        tiles = []
        for bg in BACKGROUNDS:
            for color in COLORS:
                images = ""
                for size in sizes:
                    root = ET.fromstring(paint(text, color))
                    root.set("width", str(size))
                    root.set("height", str(size))
                    images += "<span>" + ET.tostring(root, encoding="unicode") + "</span>"
                tiles.append(f'<div style="background:{bg}">{images}</div>')
        cards.append(f'<section><b>{html.escape(name)}</b><div class="tiles">{"".join(tiles)}</div></section>')
    html_path = out.with_suffix(".html")
    html_path.write_text('<!doctype html><html><meta charset="utf-8"><title>SVG preview</title><style>'
                         'body{font:14px sans-serif;margin:24px}section{margin:16px 0}.tiles{display:flex;gap:4px}'
                         '.tiles>div{padding:10px;display:flex;align-items:center;gap:8px}span{display:inline-flex}'
                         '</style>' + "".join(cards) + '</html>', encoding="utf-8")
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise DependencyUnavailable("Pillow unavailable") from exc
    tile_width = sum(sizes) + 4 * (len(sizes) + 3)
    width = max(920, 180 + 6 * tile_width)
    row_height = max(sizes) + 45
    sheet = Image.new("RGB", (width, 38 + len(sources)*row_height), "#f0f2f4")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), "SVG at actual pixel sizes; light/dark; normal/warning/alarm", fill="#20262e")
    metrics = []
    for i, (name, text) in enumerate(sources):
        y = 38 + i*row_height
        draw.text((12, y+15), name, fill="#20262e")
        x = 160
        for bg in BACKGROUNDS:
            for color in COLORS:
                draw.rectangle((x, y+5, x+tile_width-3, y+row_height-8), fill=bg)
                offset = 4
                for size in sizes:
                    icon = Image.open(io.BytesIO(raster(paint(text, color), size))).convert("RGBA")
                    alpha = icon.getchannel("A")
                    bbox = alpha.getbbox()
                    pixels = sum(v > 0 for v in alpha.tobytes())
                    metrics.append({"icon": name, "size_px": size, "color": color,
                                    "background": bg, "visible_pixels_count": pixels,
                                    "boundary_ink": bool(bbox and (bbox[0] == 0 or bbox[1] == 0 or bbox[2] == size or bbox[3] == size))})
                    sheet.paste(icon, (x+offset, y+12+(max(sizes)-size)//2), icon)
                    offset += size + 4
                x += tile_width
    sheet.save(out, format="PNG")
    failed = any(m["visible_pixels_count"] == 0 or m["boundary_ink"] for m in metrics)
    report = {"scope": "local_svg_raster", "status": "failed" if failed else "passed", "ric_verified": False, "samples": metrics}
    write(out.with_suffix(".json"), report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--sizes", nargs="+", type=int, default=[16, 24, 32])
    args = ap.parse_args()
    if not args.sizes or any(not 8 <= s <= 512 for s in args.sizes):
        print(json.dumps({"status": "failed", "reason": "render size invalid"}))
        return 2
    files = sorted(Path(args.directory).glob("*.svg"))
    if not files:
        print(json.dumps({"status": "failed", "reason": "icons unavailable"}))
        return 2
    try:
        report = render(files, args.out, args.sizes)
    except DependencyUnavailable:
        report = {"scope": "local_svg_raster", "status": "not_tested", "ric_verified": False, "reason": "PNG renderer unavailable"}
        write(Path(args.out).with_suffix(".json"), report)
        print(json.dumps(report))
        return 2
    except (OSError, InputError, ImportError, ET.ParseError, ValueError, KeyError):
        print(json.dumps({"scope": "local_svg_raster", "status": "failed", "reason": "render rejected", "ric_verified": False}))
        return 2
    print(json.dumps(report))
    return int(report["status"] != "passed")


if __name__ == "__main__":
    sys.exit(main())
