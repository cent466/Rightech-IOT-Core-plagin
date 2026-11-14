#!/usr/bin/env python3
"""Собрать полигон геозоны из выгрузки Overpass / GeoJSON любого вида.

Rightech принимает во вкладке «Код» одну геометрию Polygon, а выгрузка Overpass
обычно содержит FeatureCollection: дорогу как MultiLineString и ещё отдельные
точки. Скрипт берёт самый длинный контур, замыкает его и выдаёт GeoJSON Feature
с Polygon в парах [долгота, широта] — в том виде, который сохраняется в Rightech.

Примеры:
    python geojson-zone.py МКАД.json -o mkad-geozone.json
    python geojson-zone.py МКАД.json -o mkad.geojson --simplify 0.0002
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Iterable, List, Sequence

Point = List[float]
Ring = List[Point]


def _iter_geometries(obj):
    """Обойти все geometry в файле: FeatureCollection, Feature, массив или голая геометрия."""
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_geometries(item)
        return
    if not isinstance(obj, dict):
        return
    kind = obj.get("type")
    if kind == "FeatureCollection":
        for feature in obj.get("features") or []:
            yield from _iter_geometries(feature)
    elif kind == "Feature":
        yield from _iter_geometries(obj.get("geometry"))
    elif kind == "GeometryCollection":
        for geometry in obj.get("geometries") or []:
            yield from _iter_geometries(geometry)
    elif kind in {
        "Polygon",
        "MultiPolygon",
        "LineString",
        "MultiLineString",
        "LinearRing",
    }:
        yield obj


def _rings(geometry) -> Iterable[Ring]:
    """Выдать все кольца и линии геометрии как списки точек."""
    kind = geometry["type"]
    coords = geometry.get("coordinates")
    if kind in ("LineString", "LinearRing"):
        yield coords or []
    elif kind == "MultiLineString":
        for line in coords or []:
            yield line
    elif kind == "Polygon":
        for ring in coords or []:
            yield ring
    elif kind == "MultiPolygon":
        for polygon in coords or []:
            for ring in polygon or []:
                yield ring


def _clean(ring: Sequence[Point]) -> Ring:
    """Убрать подряд идущие дубли, привести точки к [lon, lat] (2 числа)."""
    out: Ring = []
    for point in ring or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        lon, lat = float(point[0]), float(point[1])
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        if out and out[-1][0] == lon and out[-1][1] == lat:
            continue
        out.append([lon, lat])
    return out


def _close(ring: Ring) -> Ring:
    """Замкнуть контур: первая точка должна совпадать с последней."""
    if len(ring) < 2:
        return ring
    if ring[0] != ring[-1]:
        ring = ring + [list(ring[0])]
    return ring


def _signed_area(ring: Ring) -> float:
    area = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _perpendicular_distance(point: Point, start: Point, end: Point) -> float:
    if start == end:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    x, y = point
    x1, y1 = start
    x2, y2 = end
    return abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / math.hypot(y2 - y1, x2 - x1)


def _simplify(ring: Ring, epsilon: float) -> Ring:
    """Дуглас—Пекер без рекурсии: оставить только значимые вершины контура."""
    if epsilon <= 0 or len(ring) < 5:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        worst, index = 0.0, None
        for i in range(first + 1, last):
            distance = _perpendicular_distance(ring[i], ring[first], ring[last])
            if distance > worst:
                worst, index = distance, i
        if index is not None and worst > epsilon:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [point for point, flagged in zip(ring, keep) if flagged]


def _polygon_rings(geometry) -> List[Ring]:
    """Только внешние контуры полигонов: дырки геозоной быть не должны."""
    kind = geometry["type"]
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [polygon[0] for polygon in coords if polygon]
    return []


def build_polygon(data, epsilon: float) -> Ring:
    polygons, lines = [], []
    for geometry in _iter_geometries(data):
        if geometry["type"] in ("Polygon", "MultiPolygon"):
            for ring in _polygon_rings(geometry):
                cleaned = _clean(ring)
                if len(cleaned) >= 3:
                    polygons.append(_close(cleaned))
            continue
        for ring in _rings(geometry):
            cleaned = _clean(ring)
            if len(cleaned) >= 3:
                lines.append(_close(cleaned))

    if polygons:
        ring = max(polygons, key=lambda item: abs(_signed_area(item)))
    elif lines:
        ring = max(lines, key=len)
    else:
        raise SystemExit("В файле нет ни одного контура или линии с тремя и более точками.")
    ring = _simplify(ring, epsilon)
    if len(ring) < 4:
        raise SystemExit(f"После упрощения осталось {len(ring)} точек — уменьшите --simplify.")
    if ring[0] != ring[-1]:
        ring = _close(ring)
    if _signed_area(ring) < 0:
        ring = list(reversed(ring))
    return ring


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Собрать геозону-полигон из GeoJSON/выгрузки Overpass.")
    parser.add_argument("input", help="входной файл GeoJSON")
    parser.add_argument("-o", "--output", help="куда записать результат (по умолчанию рядом с входным)")
    parser.add_argument("--name", default=None, help="имя в properties (для себя; Rightech его игнорирует)")
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.0,
        help="допуск упрощения контура в градусах, например 0.0002 (~20 м); по умолчанию без упрощения",
    )
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as handle:
        data = json.load(handle)

    ring = build_polygon(data, args.simplify)
    feature = {
        "type": "Feature",
        "properties": {"name": args.name} if args.name else {},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }

    output = args.output or args.input.rsplit(".", 1)[0] + "-geozone.json"
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(feature, handle, ensure_ascii=False)
        handle.write("\n")

    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    print(f"points: {len(ring)} (without closing repeat: {len(ring) - 1})")
    print(f"bounds: lon {min(lons):.5f}..{max(lons):.5f}, lat {min(lats):.5f}..{max(lats):.5f}")
    print(f"closed: {'yes' if ring[0] == ring[-1] else 'no'}")
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
