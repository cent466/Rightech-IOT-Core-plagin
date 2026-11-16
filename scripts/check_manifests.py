#!/usr/bin/env python3
"""Проверяет манифесты плагина и маркетплейсов.

`claude plugin validate` проверяет только `.claude-plugin/plugin.json`.
Codex использует свой манифест, а оба маркетплейса — отдельные файлы, поэтому
здесь проверяется, что они читаются как JSON и содержат обязательные поля.

Пример:
  python3 scripts/check_manifests.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PLUGIN_MANIFESTS = (
    "rightech-plugin/.claude-plugin/plugin.json",
    "rightech-plugin/.codex-plugin/plugin.json",
)
MARKETPLACES = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
)


def load(relative: str) -> dict:
    path = REPO_ROOT / relative
    if not path.exists():
        raise ValueError(f"{relative}: файла нет")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{relative}: ожидался JSON-объект")
    return data


def non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_plugin(relative: str, data: dict) -> list[str]:
    problems = []
    if not non_empty(data.get("name")):
        problems.append(f"{relative}: не заполнено name")
    if not non_empty(data.get("version")):
        problems.append(f"{relative}: не заполнено version")
    if not non_empty(data.get("description")):
        problems.append(f"{relative}: не заполнено description")
    if not isinstance(data.get("keywords", []), list):
        problems.append(f"{relative}: keywords должен быть списком")
    return problems


def check_marketplace(relative: str, data: dict) -> list[str]:
    problems = []
    if not non_empty(data.get("name")):
        problems.append(f"{relative}: не заполнено name")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        problems.append(f"{relative}: нет списка plugins")
        return problems
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            problems.append(f"{relative}: plugins[{index}] не объект")
            continue
        if not non_empty(plugin.get("name")):
            problems.append(f"{relative}: plugins[{index}] без name")
        if not plugin.get("source"):
            problems.append(f"{relative}: plugins[{index}] без source")
    return problems


def main() -> int:
    problems: list[str] = []
    for relative in PLUGIN_MANIFESTS:
        try:
            problems.extend(check_plugin(relative, load(relative)))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(str(exc))
    for relative in MARKETPLACES:
        try:
            problems.extend(check_marketplace(relative, load(relative)))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(str(exc))

    if problems:
        print("манифесты некорректны:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"манифесты в порядке: {len(PLUGIN_MANIFESTS)} плагина, {len(MARKETPLACES)} маркетплейса")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
