"""Тесты валидатора Rightech на синтетических фикстурах.

Данных аккаунта здесь нет: все идентификаторы, координаты и значения придуманы.
Запуск из корня репозитория:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rightech-plugin" / "scripts"))

import validate  # noqa: E402  (путь к скрипту добавляется выше)

MODEL_ID = "0123456789abcdef01234567"


def model_entity() -> dict:
    """Минимальная модель, собранная по правилам references/rules.md."""
    return {
        "name": "Тестовая модель",
        "description": "Модель для проверки валидатора",
        "base": "mqtt",
        "props": {"protocol": "mqtt"},
        "data": {
            "id": "root",
            "name": "Тестовая модель",
            "type": "subsystem",
            "active": True,
            "description": "Корень модели",
            "_inactive": False,
            "children": [
                {
                    "id": "external-software-modules",
                    "name": "Внешние программные модули",
                    "type": "subsystem",
                    "active": True,
                    "copy": True,
                    "_inactive": False,
                    "children": [],
                },
                {
                    "id": "liquid_level",
                    "name": "Уровень жидкости",
                    "type": "argument",
                    "active": True,
                    "dataType": "number",
                    "source": "state",
                    "reference": "well/level",
                    "unit": "мм",
                    "description": "Уровень в скважине, 0–1000 мм",
                    "_inactive": False,
                    "children": [],
                },
            ],
        },
    }


def scenario_entity() -> dict:
    """Сценарий с init и final; processId намеренно отсутствует."""
    scene = {
        "states": {
            "0": {
                "data": {"type": "init", "id": "0", "width": 120, "height": 60, "name": "Начало"},
                "position": {"left": 0, "top": 0},
            },
            "1": {
                "data": {"type": "final", "id": "1", "width": 120, "height": 60, "name": "Конец"},
                "position": {"left": 400, "top": 0},
            },
        },
        "transitions": {
            "0": {
                "data": {
                    "id": "0",
                    "event": "init",
                    "name": "Запуск",
                    "owner": {"id": "0", "point": {"id": 0, "location": "right"}},
                    "target": {"id": "1", "point": {"id": 1, "location": "left"}},
                },
                "points": [{"x": 120, "y": 30}, {"x": 400, "y": 30}],
                "block": {"layout": {"width": 4, "height": 2, "position": {"x": 12, "y": 4}}},
            }
        },
    }
    return {
        "name": "Сценарий проверки",
        "description": "Сценарий для проверки валидатора",
        "model": MODEL_ID,
        "models": [MODEL_ID],
        "data": json.dumps(scene, ensure_ascii=False),
    }


def geofence_entity(shape: dict) -> dict:
    return {
        "name": "Тестовая геозона",
        "color": "#2986FF",
        "style": {"fillOpacity": 0.2, "opacity": 0.75, "weight": 2},
        "shape": shape,
        "floors": [],
        "props": {},
    }


POLYGON = {
    "type": "polygon",
    "points": [[55.70, 37.60], [55.70, 37.70], [55.80, 37.70], [55.80, 37.60]],
}

ROUTE = {
    "type": "route",
    "trips": [
        {
            "tripId": "tripdirect",
            "type": "direct",
            "points": [[55.75, 37.60], [55.755, 37.61], [55.76, 37.62]],
            "waypoints": [
                {"pointId": "p1", "center": [55.75, 37.60], "name": "Точка 1"},
                {"pointId": "p2", "center": [55.76, 37.62], "name": "Точка 2"},
            ],
        }
    ],
}


class ModelTests(unittest.TestCase):
    def test_valid_model_has_no_findings(self) -> None:
        report = validate.validate_entity("models", model_entity(), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_unknown_data_type(self) -> None:
        entity = model_entity()
        entity["data"]["children"][1]["dataType"] = "float"
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("dataType" in message for message in report.errors))

    def test_event_node_is_accepted_with_event_params(self) -> None:
        entity = model_entity()
        entity["data"]["children"].append(
            {
                "id": "device_online",
                "name": "Устройство онлайн",
                "type": "event",
                "active": True,
                "eventParams": [{"id": "value", "name": "Значение", "dataType": "number"}],
            }
        )
        report = validate.validate_entity("models", entity, "new")
        self.assertEqual(report.errors, [])

    def test_event_param_requires_id(self) -> None:
        entity = model_entity()
        entity["data"]["children"].append(
            {
                "id": "device_online",
                "name": "Устройство онлайн",
                "type": "event",
                "active": True,
                "eventParams": [{"name": "Значение", "dataType": "number"}],
            }
        )
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("id параметра события" in message for message in report.errors))

    def test_event_param_rejects_unknown_data_type(self) -> None:
        entity = model_entity()
        entity["data"]["children"].append(
            {
                "id": "device_online",
                "name": "Устройство онлайн",
                "type": "event",
                "active": True,
                "eventParams": [{"id": "value", "dataType": "number[]"}],
            }
        )
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("dataType" in message for message in report.errors))

    def test_event_param_rejects_duplicate_ids(self) -> None:
        entity = model_entity()
        entity["data"]["children"].append(
            {
                "id": "device_online",
                "name": "Устройство онлайн",
                "type": "event",
                "active": True,
                "eventParams": [{"id": "value"}, {"id": "value"}],
            }
        )
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("повторяющийся id параметра" in message for message in report.errors))

    def test_event_logic_node_is_accepted_with_info(self) -> None:
        entity = model_entity()
        entity["data"]["children"].append(
            {
                "id": "device_online",
                "name": "Устройство онлайн",
                "type": "event-logic",
                "active": True,
                "children": [],
            }
        )
        report = validate.validate_entity("models", entity, "new")
        self.assertEqual(report.errors, [])
        self.assertTrue(any("event-logic" in message for message in report.infos))

    def test_duplicate_node_ids(self) -> None:
        entity = model_entity()
        duplicate = dict(entity["data"]["children"][1])
        entity["data"]["children"].append(duplicate)
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("повторяющийся id" in message for message in report.errors))

    def test_missing_external_module_block(self) -> None:
        entity = model_entity()
        entity["data"]["children"] = entity["data"]["children"][1:]
        report = validate.validate_entity("models", entity, "new")
        self.assertTrue(any("external-software-modules" in message for message in report.errors))


class ScenarioTests(unittest.TestCase):
    def test_valid_scenario_has_no_findings(self) -> None:
        report = validate.validate_entity("automatons", scenario_entity(), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_data_must_be_string(self) -> None:
        entity = scenario_entity()
        entity["data"] = json.loads(entity["data"])
        report = validate.validate_entity("automatons", entity, "new")
        self.assertTrue(any("строкой" in message for message in report.errors))

    def test_process_id_is_optional(self) -> None:
        report = validate.validate_entity("automatons", scenario_entity(), "new")
        self.assertFalse(any("processId" in message for message in report.errors + report.warnings))

    def test_platform_style_process_id_is_accepted(self) -> None:
        entity = scenario_entity()
        entity["processId"] = "w1ub6xm2"
        report = validate.validate_entity("automatons", entity, "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_unusual_process_id_is_information_only(self) -> None:
        entity = scenario_entity()
        entity["processId"] = "PROCESS-1"
        report = validate.validate_entity("automatons", entity, "new")
        self.assertEqual(report.errors, [])
        self.assertTrue(any("processId" in message for message in report.infos))

    def test_empty_process_id_warns(self) -> None:
        entity = scenario_entity()
        entity["processId"] = ""
        report = validate.validate_entity("automatons", entity, "new")
        self.assertTrue(any("processId" in message for message in report.warnings))

    def test_transition_to_missing_state(self) -> None:
        entity = scenario_entity()
        scene = json.loads(entity["data"])
        scene["transitions"]["0"]["data"]["target"]["id"] = "missing"
        entity["data"] = json.dumps(scene, ensure_ascii=False)
        report = validate.validate_entity("automatons", entity, "new")
        self.assertTrue(any("отсутствует в states" in message for message in report.errors))


class GeofenceTests(unittest.TestCase):
    def test_polygon_is_valid(self) -> None:
        report = validate.validate_entity("geofences", geofence_entity(POLYGON), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_polygon_with_two_points_warns(self) -> None:
        shape = {"type": "polygon", "points": [[55.70, 37.60], [55.80, 37.70]]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertEqual(report.errors, [])
        self.assertTrue(any("меньше трёх" in message for message in report.warnings))

    def test_circle_is_valid(self) -> None:
        shape = {"type": "circle", "center": [55.75, 37.61], "radius": 1500.5}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_circle_requires_positive_radius(self) -> None:
        for radius in (None, 0, -10, "500"):
            with self.subTest(radius=radius):
                shape = {"type": "circle", "center": [55.75, 37.61]}
                if radius is not None:
                    shape["radius"] = radius
                report = validate.validate_entity("geofences", geofence_entity(shape), "new")
                self.assertTrue(any("radius" in message for message in report.errors))

    def test_circle_center_is_checked(self) -> None:
        shape = {"type": "circle", "center": [137.6, 55.75], "radius": 500}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("широта" in message for message in report.errors))

    def test_circle_with_points_warns(self) -> None:
        shape = {
            "type": "circle",
            "center": [55.75, 37.61],
            "radius": 500,
            "points": [[55.75, 37.61], [55.76, 37.62], [55.74, 37.63]],
        }
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("shape.points" in message for message in report.warnings))

    def test_marker_is_valid_without_radius(self) -> None:
        shape = {"type": "marker", "center": [55.75, 37.61]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_multi_polygon_is_valid(self) -> None:
        shape = {"type": "multiPolygon", "union": [POLYGON, POLYGON]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertEqual(report.errors, [])

    def test_multi_polygon_requires_union(self) -> None:
        report = validate.validate_entity("geofences", geofence_entity({"type": "multiPolygon"}), "new")
        self.assertTrue(any("union" in message for message in report.errors))

    def test_rectangle_type_is_rejected(self) -> None:
        shape = {"type": "rectangle", "points": POLYGON["points"]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("polygon" in message for message in report.errors))

    def test_route_with_two_trips_is_valid(self) -> None:
        return_trip = {
            "tripId": "tripreturn",
            "type": "return",
            "points": list(reversed(ROUTE["trips"][0]["points"])),
            "waypoints": list(reversed(ROUTE["trips"][0]["waypoints"])),
        }
        shape = {"type": "route", "trips": [ROUTE["trips"][0], return_trip]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_route_requires_trips(self) -> None:
        report = validate.validate_entity("geofences", geofence_entity({"type": "route"}), "new")
        self.assertTrue(any("trips" in message for message in report.errors))

    def test_route_trip_requires_two_points(self) -> None:
        shape = {"type": "route", "trips": [{"tripId": "a", "type": "direct", "points": [[55.75, 37.60]], "waypoints": ROUTE["trips"][0]["waypoints"]}]}
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("points" in message for message in report.errors))

    def test_route_waypoint_center_is_checked(self) -> None:
        shape = {
            "type": "route",
            "trips": [
                {
                    "tripId": "a",
                    "type": "direct",
                    "points": [[55.75, 37.60], [55.76, 37.62]],
                    "waypoints": [
                        {"pointId": "p1", "center": [55.75, 210.0], "name": "Точка 1"},
                        {"pointId": "p2", "center": [55.76, 37.62], "name": "Точка 2"},
                    ],
                }
            ],
        }
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("долгота" in message for message in report.errors))

    def test_route_with_shape_points_warns(self) -> None:
        shape = dict(ROUTE)
        shape["points"] = POLYGON["points"]
        report = validate.validate_entity("geofences", geofence_entity(shape), "new")
        self.assertTrue(any("trips" in message and "points" in message for message in report.warnings))


class HandlerTests(unittest.TestCase):
    def valid_handler(self) -> dict:
        return {
            "name": "Обработчик проверки",
            "description": "Разбирает тестовый payload",
            "language": "javascript",
            "userCode": (
                "export function process(payload) {\n"
                "  const data = JSON.parse(payload);\n"
                "  return { temperature: data.t };\n"
                "}\n"
            ),
        }

    def test_valid_handler(self) -> None:
        report = validate.validate_entity("handlers", self.valid_handler(), "new")
        self.assertEqual(report.errors, [])

    def test_unbalanced_code(self) -> None:
        entity = self.valid_handler()
        entity["userCode"] = "export function process(payload) {\n  return {;\n"
        report = validate.validate_entity("handlers", entity, "new")
        self.assertTrue(any("скоб" in message for message in report.errors))

    def test_missing_process_entry_point(self) -> None:
        entity = self.valid_handler()
        entity["userCode"] = "function handle(payload) {\n  return {};\n}"
        report = validate.validate_entity("handlers", entity, "new")
        self.assertTrue(any("process" in message for message in report.errors))


class ServiceFieldTests(unittest.TestCase):
    def test_new_mode_rejects_export_fields(self) -> None:
        entity = scenario_entity()
        entity["_id"] = MODEL_ID
        report = validate.validate_entity("automatons", entity, "new")
        self.assertTrue(any("служебные поля" in message for message in report.errors))


if __name__ == "__main__":
    unittest.main()
