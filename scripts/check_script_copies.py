#!/usr/bin/env python3
"""Проверяет, что копии скриптов внутри навыка совпадают с rightech-plugin/scripts.

Скрипты `validate.py` и `make_import_file.py` лежат дважды: в `scripts/` и в
`skills/rightech-output/scripts/`, потому что Claude Desktop запускает код в
песочнице отдельного навыка. Копии расходятся при правке одной из них, а ошибка
проявляется уже у пользователя. Скрипт сравнивает содержимое (с точностью до
переводов строк) и падает при расхождении.

Пример:
  python3 scripts/check_script_copies.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPTS = REPO_ROOT / "rightech-plugin" / "scripts"
SKILL_SCRIPTS = REPO_ROOT / "rightech-plugin" / "skills" / "rightech-output" / "scripts"
IGNORED_PARTS = {"__pycache__"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}


def scripts(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir():
        raise SystemExit(f"нет каталога {directory.relative_to(REPO_ROOT)}")
    return {
        path.name: path.read_bytes().replace(b"\r\n", b"\n")
        for path in sorted(directory.iterdir())
        if path.is_file() and not IGNORED_PARTS.intersection(path.parts) and path.name not in IGNORED_NAMES
    }


def main() -> int:
    main_scripts = scripts(MAIN_SCRIPTS)
    copies = scripts(SKILL_SCRIPTS)
    if not copies:
        raise SystemExit("в навыке rightech-output нет копий скриптов")

    problems = []
    for name, content in copies.items():
        if name not in main_scripts:
            problems.append(f"{name}: есть в навыке, но нет в rightech-plugin/scripts")
        elif main_scripts[name] != content:
            problems.append(f"{name}: копия в навыке отличается от rightech-plugin/scripts")

    if problems:
        print("копии скриптов разошлись:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "синхронизируйте: cp rightech-plugin/scripts/<файл> "
            "rightech-plugin/skills/rightech-output/scripts/",
            file=sys.stderr,
        )
        return 1

    shared = ", ".join(sorted(copies))
    print(f"копии скриптов совпадают: {shared}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
