#!/usr/bin/env python3
"""Локальная проверка JSON сущностей Rightech IoT Core до отправки в API.

Правила взяты из references/rules.md (выведены из 25 рабочих образцов, созданной модели smart_well_mqtt
и проверок на живом аккаунте 2026-11-16: круглая геозона, узел event с eventParams,
унаследованный event-logic, сценарий без processId).
Скрипт не обращается к сети и не требует зависимостей.

Режимы:
  export  объект как в экспорте платформы (служебные поля допустимы);
  new     объект, подготовленный к POST (служебные поля запрещены).

Уровни сообщений:
  ERROR  объект заведомо некорректен (нарушает структуру или ссылки);
  WARN   подозрительно, требует решения пользователя;
  INFO   наблюдавшееся в рабочих образцах расхождение, не ошибка.

Код возврата: 0 — ошибок нет; 1 — есть ERROR; 2 — есть WARN при --strict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_FIELDS = ("_id", "_at", "owner", "group", "time", "user", "store", "origin")
NODE_SERVICE_FIELDS = ("_parentId", "_isRoot", "_levels", "_dataPath")
NODE_TYPES = {"subsystem", "argument", "action", "config", "level", "event", "event-logic"}
DATA_TYPES = {"number", "string", "boolean", "object", "number[]"}
# dataType параметра события в редакторе: number, boolean, string, object (2026-11-16).
EVENT_PARAM_TYPES = {"number", "boolean", "string", "object"}
# Пары base/props.protocol и остальные значения — references/base-models.md (16 базовых моделей, 2026-11-16).
BASE_VALUES = {
    "arnavi3", "autofon8", "coap", "egts", "galileosky", "http-ric", "lora", "lwm2m",
    "mqtt", "navtelecom", "nidd", "smpp", "teltonika", "websocket", "wialon-combine", "wialon-ips",
}
ACTION_SERVICES = {"ric-gate", "ric-logic-v3.user-event"}
LANGUAGES = {"javascript", "typescript"}
STATE_TYPES = {"init", "state", "final"}
# Формы подтверждены запросами к API живого аккаунта 2026-11-16: полигон, круг и маршрут
# прочитаны из GET /api/v1/geofences; multiPolygon и marker — из кода фронтенда
# платформы (shape.union[].points, shape.center).
GEOFENCE_SHAPES = {"polygon", "multiPolygon", "circle", "marker", "route"}
# trips[].type маршрута: прямой и обратный рейсы (код редактора и проверка на аккаунте).
ROUTE_TRIP_TYPES = {"direct", "return"}
# processId необязателен; у старых сценариев это 8 символов [a-z0-9] (например, w1ub6xm2).
PROCESS_ID = re.compile(r"[a-z0-9]{8}")
EXTERNAL_MODULE_IDS = {"external-software-modules", "external_software_modules"}
SNAKE_CASE_ID = re.compile(r"[a-z][a-z0-9_]*")
LEVEL_ID = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.\d+")
CONFIG_ID = re.compile(r"@[a-z0-9]+\.[A-Za-z0-9_]+")
VAGUE_ID = re.compile(r"(?:param|arg|argument|value|val|data|field|node|item|p|a)\d*", re.IGNORECASE)
CYRILLIC_TEXT = re.compile(r"[\u0400-\u04FF]")

SECRET_PATTERNS = (
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("password literal", re.compile(r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]+['\"]")),
)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def info(self, message: str) -> None:
        self.infos.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_entity(path: Path, store_hint: str | None, report: "Report | None" = None) -> tuple[str, dict]:
    """Возвращает (тип сущности, объект сущности) из экспорта или из голого JSON."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("ожидался JSON-объект")
    if isinstance(raw.get("data"), dict) and raw.get("store"):
        if report is not None:
            check_envelope(raw, report)
        return str(raw["store"]), raw["data"]
    if store_hint is None:
        raise ValueError("не удалось определить тип сущности: укажите --store")
    return store_hint, raw


def check_envelope(raw: dict, report: "Report") -> None:
    """Оболочка файла-экспорта: version=1, origin и store."""
    version = raw.get("version")
    if version != 1:
        report.error(f"оболочка: version={version!r}, ожидается 1")
    origin = raw.get("origin")
    if not isinstance(origin, str) or not origin.strip():
        report.error("оболочка: не заполнен origin (dev.rightech.io или хост пользователя)")
    if not raw.get("store"):
        report.error("оболочка: не заполнен store")
    if not isinstance(raw.get("time"), str):
        report.info("оболочка: нет time — платформа обычно пишет ISO-время экспорта")


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def scan_secrets(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]


def contains_transition_event_payload(value: object) -> bool:
    """Ищет transitionEvent.payload в строковых значениях аргументов действия."""
    if isinstance(value, str):
        return "transitionEvent.payload" in value
    if isinstance(value, dict):
        return any(contains_transition_event_payload(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_transition_event_payload(item) for item in value)
    return False


# --------------------------------------------------------------------------- модели


def validate_model(entity: dict, mode: str, report: Report) -> None:
    if not isinstance(entity.get("name"), str) or not entity.get("name", "").strip():
        report.error("models: не заполнено имя (name)")
    if mode == "new" and not str(entity.get("description") or "").strip():
        report.error("models: не заполнено краткое описание (description)")
    base = entity.get("base")
    if not isinstance(base, str) or not base.strip():
        report.error("models: не заполнено base")
    elif base not in BASE_VALUES:
        report.warn(f"models: base={base!r} не встречался в образцах — подтвердите по документации")

    tree = entity.get("data")
    if not isinstance(tree, dict):
        report.error("models: нет дерева data")
        return
    for key in ("id", "type", "active"):
        if key not in tree:
            report.error(f"models: корневой узел не содержит {key}")
    if tree.get("type") != "subsystem":
        report.warn("models: корневой узел обычно type=subsystem")

    children = tree.get("children")
    module_block = children[0] if isinstance(children, list) and children else None
    if not isinstance(module_block, dict) or module_block.get("id") not in EXTERNAL_MODULE_IDS:
        message = "models: первым дочерним узлом должен быть блок external-software-modules"
        if mode == "new":
            report.error(message)
        else:
            report.info(message)
    else:
        if module_block.get("type") != "subsystem":
            report.error("models: блок external-software-modules должен быть type=subsystem")
        if module_block.get("copy") is not True:
            report.warn("models: у блока external-software-modules обычно copy=true")

    seen: dict[str, str] = {}

    def walk(node: object, path: str) -> None:
        if not isinstance(node, dict):
            report.error(f"models: {path} — узел не объект")
            return
        node_type = node.get("type")
        if node_type == "event":
            params = node.get("eventParams")
            if params is not None and not isinstance(params, list):
                report.error(f"models: {path} — eventParams должен быть списком")
                params = []
            seen_params: set[str] = set()
            for index, param in enumerate(params or []):
                param_path = f"{path}.eventParams[{index}]"
                if not isinstance(param, dict):
                    report.error(f"models: {param_path} — параметр события не объект")
                    continue
                param_id = param.get("id")
                if not isinstance(param_id, str) or not param_id.strip():
                    report.error(f"models: {param_path} — нет id параметра события")
                elif param_id in seen_params:
                    report.error(f"models: {param_path} — повторяющийся id параметра {param_id!r}")
                else:
                    seen_params.add(param_id)
                if "name" in param and not isinstance(param["name"], str):
                    report.error(f"models: {param_path} — name должен быть строкой")
                if param.get("dataType") is not None and param["dataType"] not in EVENT_PARAM_TYPES:
                    report.error(
                        f"models: {param_path} — dataType={param['dataType']!r} "
                        f"вне {sorted(EVENT_PARAM_TYPES)}"
                    )
        elif node_type == "event-logic":
            if mode == "new":
                report.info(
                    f"models: {path} — type=event-logic унаследован; "
                    "для новых моделей используй type=event"
                )
        elif node_type not in NODE_TYPES:
            report.error(f"models: {path} — неизвестный type={node_type!r}")
        for key in ("id", "type", "active"):
            if key not in node:
                report.error(f"models: {path} — нет поля {key}")
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            if node_id in seen and node_id != "root":
                report.error(f"models: повторяющийся id={node_id!r} ({seen[node_id]} и {path})")
            seen.setdefault(node_id, path)
        elif node_type is not None:
            report.error(f"models: {path} — пустой или нестроковый id")

        name = node.get("name")
        if "name" not in node:
            if mode == "new":
                report.warn(f"models: {path} — нет name: по имени должно быть понятно, что это за параметр")
            else:
                report.info(f"models: {path} — узел без name (встречается в рабочих экспортах)")
        elif mode == "new" and isinstance(node_id, str) and str(name).strip() == node_id:
            report.warn(f"models: {path} — name повторяет id={node_id!r}; нужно человекочитаемое название")
        if mode == "new" and node_type in {"argument", "action"}:
            if not str(node.get("description") or "").strip():
                report.warn(f"models: {path} — нет description: укажи назначение и диапазон/расшифровку")
        if mode == "new" and "_inactive" not in node:
            report.warn(f"models: {path} — нет _inactive (в генерируемых моделях ставится false)")
        if mode == "new" and isinstance(node_id, str) and node_id not in EXTERNAL_MODULE_IDS | {"root"}:
            if node_type == "level":
                if not LEVEL_ID.fullmatch(node_id):
                    report.warn(f"models: {path} — id={node_id!r}; для шкалы ожидается <argument_id>.levels.<n>")
            elif node_type == "config":
                if not CONFIG_ID.fullmatch(node_id):
                    report.warn(f"models: {path} — id={node_id!r}; для настройки ожидается @<protocol>.<key>")
            elif node_type == "subsystem" and node_id.startswith("@"):
                pass
            else:
                if not SNAKE_CASE_ID.fullmatch(node_id):
                    report.warn(f"models: {path} — id={node_id!r} не в snake_case")
                if VAGUE_ID.fullmatch(node_id):
                    report.warn(f"models: {path} — id={node_id!r} невнятный: назови параметр по смыслу")
        if node_type == "argument":
            if node.get("dataType") not in DATA_TYPES:
                report.error(
                    f"models: {path} — dataType={node.get('dataType')!r} вне {sorted(DATA_TYPES)}"
                )
            if "unit" in node and node["unit"] is not None and not str(node["unit"]).strip():
                report.error(f"models: {path} — пустая единица измерения unit")
            if mode == "new":
                if node.get("source") != "state":
                    report.warn(f"models: {path} — у аргумента ожидается source=\"state\"")
                if not node.get("reference"):
                    report.warn(f"models: {path} — у аргумента нет reference (ключ параметра устройства)")
        if node_type == "action":
            service = node.get("service")
            if service not in ACTION_SERVICES:
                report.warn(f"models: {path} — service={service!r} не встречался в образцах")
            if service == "ric-gate":
                params = node.get("params")
                if not node.get("command"):
                    report.warn(f"models: {path} — действие ric-gate без command")
                if not isinstance(params, dict):
                    report.warn(f"models: {path} — действие ric-gate без params")
                elif "topic" not in params and "command" not in params:
                    report.info(f"models: {path} — params без topic/command (встречается в экспортах)")
                if mode == "new" and node.get("source") != "state":
                    report.info(f"models: {path} — у действия нет source=\"state\" (в базовых моделях встречается и без него)")
            if not isinstance(node.get("params", {}), dict):
                report.error(f"models: {path} — params должен быть объектом")

        if mode == "new":
            for key in NODE_SERVICE_FIELDS:
                if key in node:
                    report.warn(f"models: {path} — служебное поле {key} перед отправкой")

        children = node.get("children", [])
        if not isinstance(children, list):
            report.error(f"models: {path} — children должен быть списком")
            return
        for index, child in enumerate(children):
            walk(child, f"{path}.children[{index}]")

    walk(tree, "data")


# ------------------------------------------------------------------------- сценарии


def _scenario_segment_hits_rect(start: tuple[float, float], end: tuple[float, float], rect: tuple[float, float, float, float]) -> bool:
    """True when a route segment passes through the strict interior of a state card."""
    x1, y1 = start
    x2, y2 = end
    left, top, right, bottom = rect
    epsilon = 1e-7
    left += epsilon
    top += epsilon
    right -= epsilon
    bottom -= epsilon
    dx, dy = x2 - x1, y2 - y1
    lower, upper = 0.0, 1.0
    for p, q in ((-dx, x1 - left), (dx, right - x1), (-dy, y1 - top), (dy, bottom - y1)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        ratio = q / p
        if p < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return False
    return upper >= 0 and lower <= 1 and upper >= lower


def _scenario_segments_overlap_interior(a: tuple[tuple[float, float], tuple[float, float]], b: tuple[tuple[float, float], tuple[float, float]]) -> bool:
    """Detect proper route crossings or positive-length collinear overlap, not endpoint joins."""
    (ax, ay), (bx, by) = a
    (cx, cy), (dx, dy) = b
    abx, aby = bx - ax, by - ay
    cdx, cdy = dx - cx, dy - cy
    cross = abx * cdy - aby * cdx
    acx, acy = cx - ax, cy - ay
    epsilon = 1e-8
    if abs(cross) > epsilon:
        t = (acx * cdy - acy * cdx) / cross
        u = (acx * aby - acy * abx) / cross
        return epsilon < t < 1 - epsilon and epsilon < u < 1 - epsilon
    if abs(acx * aby - acy * abx) > epsilon:
        return False
    if abs(abx) >= abs(aby):
        a0, a1, b0, b1 = sorted((ax, bx))[0], sorted((ax, bx))[1], sorted((cx, dx))[0], sorted((cx, dx))[1]
    else:
        a0, a1, b0, b1 = sorted((ay, by))[0], sorted((ay, by))[1], sorted((cy, dy))[0], sorted((cy, dy))[1]
    return min(a1, b1) - max(a0, b0) > epsilon


def validate_scenario(entity: dict, mode: str, report: Report) -> None:
    if not isinstance(entity.get("name"), str) or not entity.get("name", "").strip():
        report.error("automatons: не заполнено имя (name)")
    if mode == "new" and not str(entity.get("description") or "").strip():
        report.error("automatons: не заполнено краткое описание (description)")

    model_id = entity.get("model")
    models = entity.get("models")
    cross_scenario = entity.get("elementType") == "cross"
    missing_link = report.warn if mode == "new" and cross_scenario else report.error
    if not isinstance(model_id, str) or not model_id:
        missing_link("automatons: не заполнено model (для cross-сценария модель назначается/сопоставляется при импорте; не выдумывай ID)")
    if not isinstance(models, list) or not models:
        missing_link("automatons: не заполнен список models (для cross-сценария модели назначаются при импорте)")
    elif isinstance(model_id, str) and model_id and model_id not in models:
        report.error("automatons: model отсутствует в models")

    encoded = entity.get("data")
    if not isinstance(encoded, str):
        report.error("automatons: data должен быть строкой с вложенным JSON")
        return
    try:
        scene = json.loads(encoded)
    except json.JSONDecodeError as exc:
        report.error(f"automatons: вложенный JSON в data не разбирается: {exc}")
        return
    if not isinstance(scene, dict):
        report.error("automatons: вложенный JSON должен быть объектом")
        return

    states = scene.get("states")
    transitions = scene.get("transitions")
    if not isinstance(states, dict) or not states:
        report.error("automatons: во вложенном JSON нет непустых states")
        return
    if not isinstance(transitions, dict):
        report.error("automatons: во вложенном JSON нет transitions")
        return

    state_ids: set[str] = set()
    state_rects: dict[str, tuple[float, float, float, float]] = {}
    has_init = False
    has_final = False
    for state_key, state in states.items():
        if not isinstance(state, dict):
            report.error(f"automatons: states.{state_key} — не объект")
            continue
        state_ids.add(state_key)
        data = state.get("data")
        if not isinstance(data, dict):
            report.error(f"automatons: states.{state_key}.data отсутствует")
            continue
        state_type = data.get("type")
        if state_type not in STATE_TYPES:
            report.error(f"automatons: states.{state_key} — type={state_type!r} вне {sorted(STATE_TYPES)}")
        has_init |= state_type == "init"
        has_final |= state_type == "final"
        if data.get("id") != state_key:
            report.warn(f"automatons: states.{state_key} — data.id={data.get('id')!r} не совпадает с ключом")
        for dimension in ("width", "height"):
            value = data.get(dimension)
            if not is_number(value) or value <= 0:
                message = f"automatons: states.{state_key}.data.{dimension} должен быть положительным числом"
                if mode == "new":
                    report.error(message)
                else:
                    report.warn(message)
        state_name = str(data.get("name") or "").strip()
        if mode == "new":
            if not state_name:
                report.error(f"automatons: states.{state_key} — не задано имя состояния на русском")
            elif not CYRILLIC_TEXT.search(state_name):
                report.error(f"automatons: states.{state_key}.data.name должно быть на русском")
        position = state.get("position")
        if not isinstance(position, dict) or not is_number(position.get("left")) or not is_number(position.get("top")):
            if mode == "new":
                report.error(f"automatons: states.{state_key}.position должен задавать числовые left и top")
        elif is_number(data.get("width")) and data["width"] > 0 and is_number(data.get("height")) and data["height"] > 0:
            left, top = float(position["left"]), float(position["top"])
            state_rects[state_key] = (left, top, left + float(data["width"]), top + float(data["height"]))
        for hook in ("onenter", "onexit"):
            actions = data.get(hook, [])
            if not isinstance(actions, list):
                report.error(f"automatons: states.{state_key}.{hook} должен быть списком")
                continue
            for index, action in enumerate(actions):
                if not isinstance(action, dict) or not action.get("id"):
                    report.error(f"automatons: states.{state_key}.{hook}[{index}] без id действия")
                else:
                    if mode == "new" and not str(action.get("name") or "").strip():
                        report.warn(f"automatons: states.{state_key}.{hook}[{index}] ({action.get('id')}) — добавь понятное имя действия")
                    args = action.get("args", {})
                    if not isinstance(args, dict):
                        report.error(f"automatons: states.{state_key}.{hook}[{index}].args должен быть объектом")
                    elif contains_transition_event_payload(args):
                        report.warn(
                            f"automatons: states.{state_key}.{hook}[{index}] ({action.get('id')}) — "
                            "transitionEvent.payload в строковых аргументах действия подставляется как undefined "
                            "(проверено 2026-11-16); используй проверенный шаблон объекта или event.payload в условии перехода"
                        )
    if not has_init:
        (report.error if mode == "new" else report.warn)("automatons: нет состояния type=init")
    if not has_final:
        report.warn("automatons: нет состояния type=final — допустимо для циклического сценария; подтверди, что автомат должен работать бесконечно")
    if mode == "new":
        for index, (state_id, rect) in enumerate(state_rects.items()):
            for other_id, other_rect in list(state_rects.items())[index + 1:]:
                if max(rect[0], other_rect[0]) < min(rect[2], other_rect[2]) and max(rect[1], other_rect[1]) < min(rect[3], other_rect[3]):
                    report.error(f"automatons: карточки состояний {state_id!r} и {other_id!r} перекрываются по position/width/height")

    route_segments: list[tuple[str, tuple[tuple[float, float], tuple[float, float]]]] = []
    transition_block_rects: dict[str, tuple[float, float, float, float]] = {}
    for transition_key, transition in transitions.items():
        if not isinstance(transition, dict):
            report.error(f"automatons: transitions.{transition_key} — не объект")
            continue
        data = transition.get("data")
        if not isinstance(data, dict):
            report.error(f"automatons: transitions.{transition_key}.data отсутствует")
            continue
        if data.get("id") != transition_key:
            report.warn(
                f"automatons: transitions.{transition_key} — data.id={data.get('id')!r} не совпадает с ключом"
            )
        if mode == "new" and not str(data.get("name") or "").strip():
            report.warn(f"automatons: transitions.{transition_key} — добавь понятное имя перехода")
        if not isinstance(data.get("event"), str) or not data.get("event").strip():
            report.error(f"automatons: transitions.{transition_key} — нет event")
        for side in ("owner", "target"):
            ref = data.get(side)
            if not isinstance(ref, dict) or "id" not in ref:
                report.error(f"automatons: transitions.{transition_key} — нет {side}.id")
                continue
            if ref["id"] not in state_ids:
                report.error(
                    f"automatons: transitions.{transition_key} — {side}.id={ref['id']!r} отсутствует в states"
                )
        points = transition.get("points")
        if not isinstance(points, list) or len(points) < 2:
            if mode == "new":
                report.error(f"automatons: transitions.{transition_key}.points должен содержать маршрут минимум из двух координат")
            elif points is not None and not isinstance(points, list):
                report.error(f"automatons: transitions.{transition_key}.points должен быть списком")
        elif any(not isinstance(point, dict) or not is_number(point.get("x")) or not is_number(point.get("y")) for point in points):
            report.error(f"automatons: transitions.{transition_key}.points — каждая координата должна иметь числовые x и y")
        else:
            route = [(float(point["x"]), float(point["y"])) for point in points]
            segments = list(zip(route, route[1:]))
            route_segments.extend((transition_key, segment) for segment in segments)
            if mode == "new":
                owner_id = data.get("owner", {}).get("id") if isinstance(data.get("owner"), dict) else None
                target_id = data.get("target", {}).get("id") if isinstance(data.get("target"), dict) else None
                for other_state_id, rect in state_rects.items():
                    if other_state_id in {owner_id, target_id}:
                        continue
                    if any(_scenario_segment_hits_rect(segment[0], segment[1], rect) for segment in segments):
                        report.error(f"automatons: маршрут transitions.{transition_key} проходит через карточку несвязанного состояния {other_state_id!r}")

        block = transition.get("block")
        layout = block.get("layout") if isinstance(block, dict) else None
        block_position = layout.get("position") if isinstance(layout, dict) else None
        block_ok = (
            isinstance(layout, dict)
            and isinstance(block_position, dict)
            and all(is_number(block_position.get(key)) for key in ("x", "y"))
            and is_number(layout.get("width")) and layout["width"] > 0
            and is_number(layout.get("height")) and layout["height"] > 0
        )
        if not block_ok:
            if mode == "new":
                report.error(f"automatons: transitions.{transition_key}.block.layout должен иметь собственные position.x/y и положительные width/height")
        else:
            # block.layout is stored in grid units; one layout unit is 20 editor pixels.
            x, y = float(block_position["x"]) * 20, float(block_position["y"]) * 20
            block_width, block_height = float(layout["width"]) * 20, float(layout["height"]) * 20
            block_rect = (x, y, x + block_width, y + block_height)
            transition_block_rects[transition_key] = block_rect
            if mode == "new":
                for state_id, state_rect in state_rects.items():
                    if max(block_rect[0], state_rect[0]) < min(block_rect[2], state_rect[2]) and max(block_rect[1], state_rect[1]) < min(block_rect[3], state_rect[3]):
                        report.error(f"automatons: метка перехода {transition_key!r} перекрывает карточку состояния {state_id!r}")
        condition = data.get("condition")
        if condition is not None and not isinstance(condition, str):
            report.error(f"automatons: transitions.{transition_key}.condition должен быть строкой")
        if isinstance(data.get("userCode"), str):
            for name in scan_secrets(data["userCode"]):
                report.error(f"automatons: transitions.{transition_key}.userCode содержит секрет ({name})")
        for field_name in ("condition", "userCode"):
            expression = data.get(field_name)
            if isinstance(expression, str) and "transitionEvent.payload" in expression:
                report.warn(
                    f"automatons: transitions.{transition_key}.{field_name} использует transitionEvent.payload; "
                    "в условии перехода параметры события доступны как event.payload.<param-id> "
                    "(проверено 2026-11-16)"
                )

    if mode == "new":
        block_items = list(transition_block_rects.items())
        for index, (transition_id, rect) in enumerate(block_items):
            for other_id, other_rect in block_items[index + 1:]:
                if max(rect[0], other_rect[0]) < min(rect[2], other_rect[2]) and max(rect[1], other_rect[1]) < min(rect[3], other_rect[3]):
                    report.error(f"automatons: метки переходов {transition_id!r} и {other_id!r} перекрываются по block.layout.position")
        for index, (transition_id, segment) in enumerate(route_segments):
            for other_id, other_segment in route_segments[index + 1:]:
                if transition_id != other_id and _scenario_segments_overlap_interior(segment, other_segment):
                    report.error(f"automatons: маршруты переходов {transition_id!r} и {other_id!r} пересекаются или идут по одному участку")

    if mode == "new":
        # Проверено 2026-11-16: сценарий, созданный в интерфейсе (тип «По кросс-элементам»),
        # и сценарий, импортированный из файла без processId, сохраняются платформой без этого поля.
        process_id = entity.get("processId")
        if process_id is not None:
            if not isinstance(process_id, str) or not process_id.strip():
                report.warn("automatons: processId пустой — удали поле, платформа создаёт сценарий и без него")
            elif not PROCESS_ID.fullmatch(process_id):
                report.info(f"automatons: processId={process_id!r} не вида <8 символов a-z0-9> — у платформенных сценариев так")


# --------------------------------------------------------------------------- геозоны


def validate_geofence(entity: dict, mode: str, report: Report) -> None:
    if not isinstance(entity.get("name"), str) or not entity.get("name", "").strip():
        report.error("geofences: не заполнено имя (name)")
    color = entity.get("color")
    if color is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color)):
        report.warn(f"geofences: color={color!r} не в формате #RRGGBB")

    shape = entity.get("shape")
    if not isinstance(shape, dict):
        report.error("geofences: нет shape")
        return
    shape_type = shape.get("type")
    if shape_type not in GEOFENCE_SHAPES:
        report.error(
            f"geofences: shape.type={shape_type!r}; подтверждены {', '.join(sorted(GEOFENCE_SHAPES))}. "
            "Прямоугольник из интерфейса сохраняется как polygon; для другой формы нужен эталон из аккаунта"
        )

    def check_point(point: object, path: str) -> None:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not all(is_number(value) for value in point)
        ):
            report.error(f"geofences: {path} должен быть парой чисел [широта, долгота]")
            return
        lat, lon = point
        if not -90 <= lat <= 90:
            report.error(f"geofences: {path} широта {lat} вне -90..90")
        if not -180 <= lon <= 180:
            report.error(f"geofences: {path} долгота {lon} вне -180..180")

    def check_ring(points: object, path: str) -> None:
        if not isinstance(points, list) or not points:
            report.error(f"geofences: {path} должен быть непустым списком точек")
            return
        for index, point in enumerate(points):
            check_point(point, f"{path}[{index}]")
        if len(points) < 3:
            report.warn(f"geofences: {path} содержит меньше трёх точек")

    if shape_type == "polygon":
        check_ring(shape.get("points"), "shape.points")
    elif shape_type == "multiPolygon":
        union = shape.get("union")
        if not isinstance(union, list) or not union:
            report.error("geofences: shape.union должен быть непустым списком полигонов")
        else:
            for index, part in enumerate(union):
                if not isinstance(part, dict) or part.get("type") != "polygon":
                    report.error(f"geofences: shape.union[{index}] должен быть polygon")
                    continue
                check_ring(part.get("points"), f"shape.union[{index}].points")
    elif shape_type == "circle":
        check_point(shape.get("center"), "shape.center")
        radius = shape.get("radius")
        if not is_number(radius) or radius <= 0:
            report.error("geofences: shape.radius должен быть положительным числом метров")
        if "points" in shape:
            report.warn("geofences: у круга есть shape.points — платформа хранит только center и radius")
    elif shape_type == "marker":
        check_point(shape.get("center"), "shape.center")
        if "radius" in shape:
            report.warn("geofences: у маркера нет shape.radius")
    elif shape_type == "route":
        trips = shape.get("trips")
        if not isinstance(trips, list) or not trips:
            report.error("geofences: shape.trips должен быть непустым списком маршрутов")
        else:
            for index, trip in enumerate(trips):
                path = f"shape.trips[{index}]"
                if not isinstance(trip, dict):
                    report.error(f"geofences: {path} должен быть объектом")
                    continue
                if trip.get("type") not in ROUTE_TRIP_TYPES:
                    report.warn(f"geofences: {path}.type={trip.get('type')!r} вне {sorted(ROUTE_TRIP_TYPES)}")
                points = trip.get("points")
                if not isinstance(points, list) or len(points) < 2:
                    report.error(f"geofences: {path}.points должен содержать минимум две точки [широта, долгота]")
                else:
                    for point_index, point in enumerate(points):
                        check_point(point, f"{path}.points[{point_index}]")
                waypoints = trip.get("waypoints")
                if not isinstance(waypoints, list) or len(waypoints) < 2:
                    report.error(f"geofences: {path}.waypoints должен содержать минимум две точки")
                else:
                    for waypoint_index, waypoint in enumerate(waypoints):
                        waypoint_path = f"{path}.waypoints[{waypoint_index}]"
                        if not isinstance(waypoint, dict):
                            report.error(f"geofences: {waypoint_path} должен быть объектом")
                            continue
                        check_point(waypoint.get("center"), f"{waypoint_path}.center")
                        if not str(waypoint.get("name") or "").strip():
                            report.warn(f"geofences: {waypoint_path}.name пустой — в интерфейсе точка называется по умолчанию")
                        if not str(waypoint.get("pointId") or "").strip():
                            report.warn(f"geofences: {waypoint_path}.pointId пустой — интерфейс сопоставляет точки по нему")
        if "points" in shape:
            report.warn("geofences: у маршрута нет shape.points — геометрия лежит в shape.trips[].points")

    cutouts = shape.get("cutouts", [])
    if not isinstance(cutouts, list):
        report.error("geofences: shape.cutouts должен быть списком")
    else:
        for index, cutout in enumerate(cutouts):
            if not isinstance(cutout, dict) or cutout.get("type") != "polygon":
                report.error(f"geofences: shape.cutouts[{index}] должен быть polygon")
                continue
            check_ring(cutout.get("points"), f"shape.cutouts[{index}].points")

    if not isinstance(entity.get("floors", []), list):
        report.error("geofences: floors должен быть списком")
    if not isinstance(entity.get("props", {}), dict):
        report.error("geofences: props должен быть объектом")


# ----------------------------------------------------------------------- обработчики


REGEX_PRECEDERS = set("([{=,:;!&|?+*-%~^<>")


def js_bracket_balance(code: str) -> str | None:
    """Проверяет баланс скобок, пропуская строки, шаблоны, комментарии и regex-литералы."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    index = 0
    length = len(code)
    while index < length:
        char = code[index]
        nxt = code[index + 1] if index + 1 < length else ""
        if char == "/" and nxt not in ("/", "*"):
            previous = index - 1
            while previous >= 0 and code[previous].isspace():
                previous -= 1
            opener = code[previous] if previous >= 0 else ""
            is_regex = previous < 0 or opener in REGEX_PRECEDERS or code[: previous + 1].rstrip().endswith("return")
            if is_regex:
                index += 1
                in_class = False
                while index < length:
                    current = code[index]
                    if current == "\\":
                        index += 2
                        continue
                    if current == "[":
                        in_class = True
                    elif current == "]":
                        in_class = False
                    elif current == "/" and not in_class:
                        break
                    elif current == "\n":
                        return "незакрытый regex-литерал"
                    index += 1
                else:
                    return "незакрытый regex-литерал"
                index += 1
                continue
        if char == "/" and nxt == "/":
            end = code.find("\n", index)
            index = length if end == -1 else end
            continue
        if char == "/" and nxt == "*":
            end = code.find("*/", index + 2)
            if end == -1:
                return "незакрытый блочный комментарий"
            index = end + 2
            continue
        if char in "\"'`":
            quote = char
            index += 1
            while index < length:
                current = code[index]
                if current == "\\":
                    index += 2
                    continue
                if current == quote:
                    break
                index += 1
            else:
                return f"незакрытая строка {quote}"
            index += 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                return f"лишняя или перепутанная скобка {char!r} на позиции {index}"
            stack.pop()
        index += 1
    if stack:
        return f"не закрыто {len(stack)} скобок"
    return None


def validate_handler(entity: dict, mode: str, report: Report) -> None:
    if not isinstance(entity.get("name"), str) or not entity.get("name", "").strip():
        report.error("handlers: не заполнено имя (name)")
    if mode == "new" and not str(entity.get("description") or "").strip():
        report.error("handlers: не заполнено краткое описание (description)")
    language = entity.get("language")
    if language not in LANGUAGES:
        report.error(f"handlers: language={language!r} вне {sorted(LANGUAGES)}")
    code = entity.get("userCode")
    if not isinstance(code, str) or not code.strip():
        report.error("handlers: не заполнен userCode")
        return
    for name in scan_secrets(code):
        report.error(f"handlers: в userCode найден секрет ({name})")
    problem = js_bracket_balance(code)
    if problem:
        report.error(f"handlers: синтаксическая проблема в userCode — {problem}")
    if not re.search(r"export\s+(?:async\s+)?function\s+process\s*\(", code):
        report.error("handlers: нет точки входа export function process(...)")

    parameters = entity.get("parameters")
    cross_mappings = entity.get("crossMappings")
    if parameters is None and cross_mappings is None:
        report.warn("handlers: нет ни parameters, ни crossMappings — связь с моделью не задана")
    if mode == "new" and entity.get("elementType") == "model" and not isinstance(parameters, dict):
        report.warn("handlers: elementType=model без parameters — проверь привязку к существующей модели")
    if mode == "new" and entity.get("elementType") == "cross" and (
        not isinstance(entity.get("crossElements"), list) or not entity.get("crossElements")
        or not isinstance(cross_mappings, dict) or not cross_mappings
    ):
        report.warn("handlers: elementType=cross без crossElements/crossMappings — проверь кросс-привязки")
    if parameters is not None and not isinstance(parameters, dict):
        report.error("handlers: parameters должен быть объектом")
    if cross_mappings is not None and not isinstance(cross_mappings, dict):
        report.error("handlers: crossMappings должен быть объектом")
    for index, element in enumerate(entity.get("crossElements", []) or []):
        if not isinstance(element, dict) or not element.get("id"):
            report.error(f"handlers: crossElements[{index}] без id")
    if mode == "new" and isinstance(parameters, dict):
        for model_key, handlers in parameters.items():
            if not re.fullmatch(r"m-[0-9a-f]{24}", str(model_key)):
                report.warn(f"handlers: ключ parameters {model_key!r} не вида m-<id модели>")
            if not isinstance(handlers, dict):
                report.error(f"handlers: parameters[{model_key!r}] должен быть объектом")


VALIDATORS = {
    "models": validate_model,
    "automatons": validate_scenario,
    "geofences": validate_geofence,
    "handlers": validate_handler,
}


def validate_entity(store: str, entity: dict, mode: str = "export") -> Report:
    report = Report()
    validator = VALIDATORS.get(store)
    if validator is None:
        report.error(f"неизвестный тип сущности {store!r}; ожидается один из {sorted(VALIDATORS)}")
        return report
    if mode == "new":
        present = [key for key in SERVICE_FIELDS if key in entity]
        if present:
            report.error(f"{store}: служебные поля нужно удалить перед отправкой: {', '.join(present)}")
    validator(entity, mode, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка JSON сущностей Rightech")
    parser.add_argument("paths", nargs="+", help="файлы или каталоги с JSON")
    parser.add_argument("--store", choices=sorted(VALIDATORS), help="тип сущности для голого JSON")
    parser.add_argument("--mode", choices=("export", "new"), default="export")
    parser.add_argument("--strict", action="store_true", help="считать WARN ошибками")
    parser.add_argument("--quiet", action="store_true", help="не печатать INFO")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        else:
            files.append(path)
    if not files:
        print("не найдено JSON-файлов", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0
    for path in files:
        try:
            report = Report()
            store, entity = load_entity(path, args.store, report)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[ERROR] {path}: {exc}")
            total_errors += 1
            continue
        entity_report = validate_entity(store, entity, args.mode)
        report.errors.extend(entity_report.errors)
        report.warnings.extend(entity_report.warnings)
        report.infos.extend(entity_report.infos)
        total_errors += len(report.errors)
        total_warnings += len(report.warnings)
        if not report.errors and not report.warnings:
            print(f"[OK]    {path} ({store})")
            continue
        status = "ERROR" if report.errors else "WARN "
        print(f"[{status}] {path} ({store})")
        for message in report.errors:
            print(f"        ERROR: {message}")
        for message in report.warnings:
            print(f"        WARN:  {message}")
        if not args.quiet:
            for message in report.infos:
                print(f"        INFO:  {message}")

    print(f"\nфайлов: {len(files)}, ошибок: {total_errors}, предупреждений: {total_warnings}")
    if total_errors:
        return 1
    if args.strict and total_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
