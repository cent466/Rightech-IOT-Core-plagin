#!/usr/bin/env python3
"""Подготовить существующий GeoJSON Polygon для поля кода геозоны Rightech.

Берёт однозначный Polygon из Feature/FeatureCollection или выбранную часть
MultiPolygon, сохраняет порядок [долгота, широта] и не меняет контур молча.
LineString/MultiLineString не превращаются в полигоны автоматически: для этого
нужно отдельно определить семантику зоны (внутри кольца или коридор/буфер).

Примеры:
    python geojson_zone.py zone.json -o rightech-zone.json
    python geojson_zone.py export.json --feature "Название" -o zone.json
    python geojson_zone.py export.json --feature relation/123 --polygon-index 0 -o zone.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import List, Sequence

Point = List[float]
Ring = List[Point]


def _iter_features(obj):
    """Выдать GeoJSON Feature из FeatureCollection, Feature или голой геометрии."""
    if not isinstance(obj, dict):
        return
    kind = obj.get("type")
    if kind == "FeatureCollection":
        for feature in obj.get("features") or []:
            if isinstance(feature, dict) and feature.get("type") == "Feature":
                yield feature
    elif kind == "Feature":
        yield obj
    elif kind in {"Polygon", "MultiPolygon", "LineString", "MultiLineString", "Point", "MultiPoint", "GeometryCollection"}:
        yield {"type": "Feature", "properties": {}, "geometry": obj}


def _feature_labels(feature) -> set[str]:
    labels = set()
    if feature.get("id") is not None:
        labels.add(str(feature["id"]).casefold())
    properties = feature.get("properties") or {}
    for key in ("name", "name:ru", "short_name", "loc_ref", "@id"):
        value = properties.get(key)
        if value is not None:
            labels.add(str(value).casefold())
    return labels


def _polygon_parts(geometry):
    """Вернуть Polygon-координаты; MultiPolygon остаётся неоднозначным до выбора части."""
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords]
    if kind == "MultiPolygon":
        return coords
    return []


def _clean(ring: Sequence[Point]) -> Ring:
    """Проверить позиции GeoJSON и привести их к [lon, lat], не меняя значения."""
    if not isinstance(ring, (list, tuple)):
        raise SystemExit("Polygon содержит кольцо координат неверного типа.")
    out: Ring = []
    for index, point in enumerate(ring):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise SystemExit(f"Некорректная позиция в кольце, индекс {index}: ожидалась [долгота, широта].")
        if len(point) != 2:
            raise SystemExit(f"Позиция #{index} содержит {len(point)} измерения; скрипт безопасно обрабатывает только 2D, данные не будут усечены.")
        try:
            lon, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            raise SystemExit(f"Некорректная позиция в кольце, индекс {index}: координаты должны быть числами.")
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise SystemExit(f"Некорректная позиция в кольце, индекс {index}: координаты должны быть конечными числами.")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit(f"Координата вне диапазона GeoJSON, индекс {index}: [{lon}, {lat}].")
        out.append([lon, lat])
    return out


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


def build_polygon(data, feature_selector: str | None, polygon_index: int | None, epsilon: float):
    features = list(_iter_features(data))
    if isinstance(data, dict) and data.get("type") == "FeatureCollection" and len(data.get("features") or []) > 1 and not feature_selector:
        raise SystemExit(
            f"FeatureCollection содержит {len(data.get('features') or [])} объектов. "
            "Укажите целевой объект явно через --feature (id или имя); скрипт не выберет feature за вас."
        )
    if feature_selector:
        wanted = feature_selector.casefold()
        features = [feature for feature in features if wanted in _feature_labels(feature)]
        if not features:
            raise SystemExit(f"Feature '{feature_selector}' не найден по id/name/name:ru/short_name/loc_ref/@id.")
        if len(features) > 1:
            raise SystemExit(f"По селектору '{feature_selector}' найдено несколько объектов ({len(features)}). Уточните id Feature.")

    candidates = []
    geometry_types = set()
    for feature in features:
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type", "unknown")
        geometry_types.add(kind)
        parts = _polygon_parts(geometry)
        for index, rings in enumerate(parts):
            candidates.append((feature, kind, index, rings))

    if not candidates:
        found = ", ".join(sorted(geometry_types)) or "нет геометрий"
        if any(kind in geometry_types for kind in ("LineString", "MultiLineString")):
            raise SystemExit(
                f"В выбранной геометрии нет Polygon (найдены: {found}). "
                "LineString/MultiLineString — линии, а не полигон. Не замыкайте дорогу автоматически: "
                "уточните, нужна ли область внутри кольца или полоса/буфер вокруг дороги, "
                "и укажите источник готового контура или ширину буфера."
            )
        raise SystemExit(f"В выбранных данных нет Polygon/MultiPolygon (найдено: {found}).")

    if len(candidates) > 1 and not feature_selector and polygon_index is None:
        raise SystemExit(
            f"Найдено {len(candidates)} полигональных контуров. Уточните нужный feature через --feature "
            "(id или имя), а для MultiPolygon дополнительно выберите --polygon-index."
        )

    if polygon_index is not None:
        if not feature_selector:
            raise SystemExit("--polygon-index можно использовать только вместе с --feature.")
        selected = [item for item in candidates if item[2] == polygon_index]
        if len(selected) != 1:
            raise SystemExit(f"Для выбранного feature нет единственного Polygon с индексом {polygon_index}.")
        feature, kind, index, rings = selected[0]
    else:
        if len(candidates) != 1:
            raise SystemExit("В выбранном feature несколько полигонов. Укажите --polygon-index.")
        feature, kind, index, rings = candidates[0]

    if not isinstance(rings, list) or not rings:
        raise SystemExit("Polygon не содержит колец координат.")

    clean_rings = []
    for ring_index, raw_ring in enumerate(rings):
        ring = _clean(raw_ring)
        if len(ring) < 4:
            raise SystemExit(f"Polygon ring #{ring_index} needs at least 4 positions including closure.")
        if ring[0] != ring[-1]:
            raise SystemExit(
                f"Polygon ring #{ring_index} is not closed. Fix the source GeoJSON explicitly; "
                "the script will not alter this contour automatically."
            )
        if epsilon > 0:
            ring = _simplify(ring, epsilon)
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise SystemExit(f"Simplification damaged polygon ring #{ring_index}; lower --simplify.")
        clean_rings.append(ring)

    return clean_rings, feature.get("properties") or {}, kind, index


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Подготовить однозначный Polygon GeoJSON для кода геозоны Rightech.")
    parser.add_argument("input", help="входной файл GeoJSON")
    parser.add_argument("-o", "--output", help="куда записать результат (по умолчанию рядом с входным)")
    parser.add_argument("--name", default=None, help="имя в properties (для себя; Rightech его игнорирует)")
    parser.add_argument("--feature", help="точный id или имя Feature при выборе из FeatureCollection")
    parser.add_argument("--polygon-index", type=int, help="индекс части MultiPolygon (начиная с 0; требует --feature)")
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.0,
        help="допуск упрощения контура в градусах, например 0.0002 (~20 м); по умолчанию без упрощения",
    )
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as handle:
        data = json.load(handle)

    rings, properties, source_type, polygon_index = build_polygon(
        data, args.feature, args.polygon_index, args.simplify
    )
    properties = dict(properties)
    if args.name:
        properties["name"] = args.name
    feature = {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Polygon", "coordinates": rings},
    }

    output = args.output or args.input.rsplit(".", 1)[0] + "-geozone.json"
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(feature, handle, ensure_ascii=False)
        handle.write("\n")

    outer = rings[0]
    lons = [point[0] for point in outer]
    lats = [point[1] for point in outer]
    print(f"source: {source_type}; polygon index: {polygon_index}")
    print(f"rings: {len(rings)}; exterior points: {len(outer)} (without closing repeat: {len(outer) - 1})")
    print(f"bounds: lon {min(lons):.5f}..{max(lons):.5f}, lat {min(lats):.5f}..{max(lats):.5f}")
    print(f"closed: {'yes' if outer[0] == outer[-1] else 'no'}")
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
