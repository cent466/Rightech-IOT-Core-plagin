#!/usr/bin/env python3
"""Готовит файлы для ручного импорта в Rightech из JSON сущности.

Скрипт ничего не отправляет в сеть. Он:
  1) проверяет сущность валидатором (режим new — служебных полей быть не должно);
  2) заворачивает её в оболочку экспорта Rightech (`version`, `origin`, `time`, `store`, `data`);
  3) сохраняет файл с именем как у платформенного экспорта:
     `<дата>_<Тип>_<имя>.json`;
  4) для обработчика дополнительно сохраняет файл кода `.js`/`.ts`.

Почему оболочка: импорт в Rightech выполняется файлом при создании сущности, а
официальные примеры импорта используют именно формат экспорта.

Примеры:
  python make_import_file.py entity.json --store models
  python make_import_file.py handler.json --store handlers --out-dir out
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate  # noqa: E402

TYPE_LABELS = {
    "models": "Модель",
    "automatons": "Сценарий",
    "geofences": "Геозона",
    "handlers": "Обработчик",
}
DEFAULT_ORIGIN = "dev.rightech.io"
TOP_SERVICE_FIELDS = ("_id", "_at", "owner", "group", "time", "user", "store", "origin", "version")
NODE_SERVICE_FIELDS = ("_parentId", "_isRoot", "_levels", "_dataPath")
UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def detect_store(entity: dict) -> str:
    keys = set(entity)
    if "userCode" in keys:
        return "handlers"
    if "shape" in keys:
        return "geofences"
    if "base" in keys:
        return "models"
    if "model" in keys or "processId" in keys:
        return "automatons"
    raise ValueError("не удалось определить тип сущности: укажите --store")


def clean_entity(store: str, entity: dict) -> dict:
    """Убирает служебные поля, оставляя содержательные."""
    cleaned = json.loads(json.dumps(entity, ensure_ascii=False))
    for key in TOP_SERVICE_FIELDS:
        cleaned.pop(key, None)
    if store == "models":
        _strip_node_fields(cleaned.get("data"))
    return cleaned


def _strip_node_fields(node: object) -> None:
    if isinstance(node, dict):
        for key in NODE_SERVICE_FIELDS:
            node.pop(key, None)
        for child in node.get("children", []) or []:
            _strip_node_fields(child)
    elif isinstance(node, list):
        for item in node:
            _strip_node_fields(item)


def safe_name(name: str, limit: int = 80) -> str:
    cleaned = UNSAFE_FILENAME.sub("-", str(name)).strip().replace(" ", "_")
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("._")
    return (cleaned or "без_имени")[:limit]


def build_envelope(store: str, entity: dict, *, origin: str = DEFAULT_ORIGIN, moment: dt.datetime | None = None) -> dict:
    stamp = (moment or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    return {
        "version": 1,
        "origin": origin,
        "time": stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "store": store,
        "data": clean_entity(store, entity),
    }


def output_filename(store: str, name: str, moment: dt.datetime | None = None) -> str:
    stamp = (moment or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    label = TYPE_LABELS.get(store, store)
    return f"{stamp.date().isoformat()}_{label}_{safe_name(name)}.json"


def write_files(store: str, entity: dict, out_dir: Path, *, origin: str = DEFAULT_ORIGIN) -> list[Path]:
    envelope = build_envelope(store, entity, origin=origin)
    name = str(entity.get("name", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    json_path = out_dir / output_filename(store, name)
    json_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(json_path)

    if store == "handlers":
        code = str(entity.get("userCode", ""))
        extension = "ts" if entity.get("language") == "typescript" else "js"
        code_path = out_dir / f"{safe_name(name)}.{extension}"
        code_path.write_text(code, encoding="utf-8")
        written.append(code_path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Собрать файл для ручного импорта в Rightech")
    parser.add_argument("file", help="JSON сущности (голый объект или экспорт)")
    parser.add_argument("--store", choices=sorted(TYPE_LABELS))
    parser.add_argument("--out-dir", default="rightech-output", help="каталог для готовых файлов")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="хост Rightech для поля origin")
    parser.add_argument("--json-only", action="store_true", help="не сохранять файл кода обработчика")
    args = parser.parse_args(argv)

    path = Path(args.file)
    try:
        store, entity = validate.load_entity(path, args.store)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"не удалось прочитать {path}: {exc}", file=sys.stderr)
        return 1
    if store not in TYPE_LABELS:
        try:
            store = detect_store(entity)
        except ValueError as exc:
            print(f"не удалось определить тип сущности: {exc}", file=sys.stderr)
            return 1

    report = validate.validate_entity(store, clean_entity(store, entity), "new")
    for message in report.errors:
        print(f"ERROR: {message}")
    for message in report.warnings:
        print(f"WARN:  {message}")
    if report.errors:
        print("файл не собран: сначала исправьте ошибки", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    if args.json_only and store == "handlers":
        envelope = build_envelope(store, entity, origin=args.origin)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / output_filename(store, str(entity.get("name", "")))
        json_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        written = [json_path]
    else:
        written = write_files(store, entity, out_dir, origin=args.origin)

    for item in written:
        print(f"готово: {item}")
    print(f"тип: {store}; имя: {entity.get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
