#!/usr/bin/env python3
"""Сверяет rightech-plugin-claude.zip с папкой rightech-plugin.

Архив для Claude Desktop собирается из каталога плагина, поэтому он легко
расходится с исходниками: поправили навык или скрипт, а ZIP остался старым.
Скрипт сравнивает состав и содержимое файлов, ничего не отправляя в сеть.

Режимы:
  (по умолчанию) проверить архив, код возврата 1 при расхождении;
  --write        пересобрать архив из текущего состояния плагина.

Примеры:
  python3 scripts/check_zip.py
  python3 scripts/check_zip.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "rightech-plugin"
ARCHIVE = REPO_ROOT / "rightech-plugin-claude.zip"
IGNORED_PARTS = {"__pycache__"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
# Текстовые файлы в репозитории хранятся с LF, а рабочая копия на Windows может
# иметь CRLF. Архив собирается в LF, сравнение тоже идёт по LF, иначе CI на Linux
# ругается на переводы строк вместо реальных расхождений.
TEXT_SUFFIXES = {
    ".md", ".json", ".jsonc", ".py", ".js", ".ts", ".txt", ".yml", ".yaml", ".sh", ".svg",
}


def normalize(name: str, data: bytes) -> bytes:
    if Path(name).suffix.lower() in TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n")
    return data


def collect_files() -> list[Path]:
    return sorted(
        path
        for path in PLUGIN_DIR.rglob("*")
        if path.is_file()
        and not IGNORED_PARTS.intersection(path.parts)
        and path.name not in IGNORED_NAMES
    )


def archive_members() -> dict[str, bytes]:
    if not ARCHIVE.exists():
        raise SystemExit(f"нет архива {ARCHIVE.relative_to(REPO_ROOT)}")
    with ZipFile(ARCHIVE) as archive:
        names = [info.filename for info in archive.infolist()]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise SystemExit(f"в архиве повторяются записи: {', '.join(duplicates)}")
        return {name: archive.read(name) for name in names}


def write_archive(files: list[Path]) -> None:
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED) as archive:
        for path in files:
            name = path.relative_to(REPO_ROOT).as_posix()
            archive.writestr(name, normalize(name, path.read_bytes()))


def check(files: list[Path]) -> list[str]:
    members = archive_members()
    expected = {}
    for path in files:
        name = path.relative_to(REPO_ROOT).as_posix()
        expected[name] = normalize(name, path.read_bytes())
    problems: list[str] = []
    for name in sorted(set(members) - set(expected)):
        problems.append(f"лишний файл в архиве: {name}")
    for name in sorted(set(expected) - set(members)):
        problems.append(f"нет в архиве: {name}")
    for name in sorted(set(expected) & set(members)):
        if expected[name] != normalize(name, members[name]):
            problems.append(f"устаревшее содержимое в архиве: {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сверить ZIP плагина с папкой rightech-plugin")
    parser.add_argument("--write", action="store_true", help="пересобрать архив из текущих файлов")
    args = parser.parse_args(argv)

    files = collect_files()
    if args.write:
        write_archive(files)
        print(f"архив пересобран: {ARCHIVE.relative_to(REPO_ROOT)} ({len(files)} файлов)")
        return 0

    problems = check(files)
    if problems:
        print("архив расходится с папкой rightech-plugin:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("пересоберите архив: python3 scripts/check_zip.py --write", file=sys.stderr)
        return 1
    print(f"архив совпадает с папкой rightech-plugin ({len(files)} файлов)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
