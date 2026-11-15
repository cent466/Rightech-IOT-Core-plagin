---
name: rightech-models
description: Создание и правка JSON моделей Rightech (дерево подсистем, аргументов, действий). Использовать, когда нужна модель устройства, добавление параметра/команды/события, разбор экспорта модели, а также по запросам «модель устройства», «параметры модели», "rightech model", "add argument", "model json".
---

# Модели

## Перед генерацией

Сначала пройди `rightech-research`: самостоятельно найди официальную документацию на точную модель устройства и протокол. Затем `rightech-questions` — спроси только то, чего документация, образцы и описание пользователя не разрешили. Загрузи навык `rightech-samples` и попроси его подобрать ближайший образец модели; образцы и правила встроены в ресурсы этого навыка для Claude Desktop.

## Оболочка файла

Модель отдаётся файлом-экспортом с обёрткой:

```json
{"version": 1, "origin": "dev.rightech.io", "time": "2026-11-14T12:00:00.000Z", "store": "models", "data": { ... }}
```

`version` всегда `1`; `origin` — хост платформы (`--origin` для своего сервера); `store` — `models`. В `data`: `name`, `base`, `data` (дерево), `props`, `description`. `_id`, `user`, `group`, `time` внутри `data` — служебные: в export они есть, при создании их выдаёт платформа.

`props` в рабочих экспортах: `bots`, `hardwareEvents`, `idPattern`, `order`, `prefix`, `protocol`, `helper`; в модели пользователя дополнительно `typeInput`, `statusInput`, `descriptionInput`. `props.protocol` повторяет `base`.

## Дерево `data.data`

Корень: `id: "root"`, `type: "subsystem"`, `active: true`, `_inactive: false`, `name` (= имени модели), `children`. В части экспортов у корня есть `base` (совпадает с `base` модели) и `description`.

**Первый дочерний элемент обязателен** — блок внешних модулей; далее идут содержательные подсистемы:

```json
{
  "id": "external-software-modules",
  "name": "Внешние программные модули",
  "active": true,
  "copy": true,
  "type": "subsystem",
  "children": [],
  "_inactive": false
}
```

Блок стоит первым во всех 11 образцах моделей; у Teltonika встречается вариант `id` через подчёркивания. Не переименовывай и не удаляй его, не клади в него параметры.

| Тип | Обязательные поля | Обычно ещё |
|---|---|---|
| `subsystem` | `id`, `type`, `active`, `children`, `_inactive` | `name`, `description` |
| `argument` | `id`, `name`, `type`, `active`, `_inactive`, `source: "state"`, `dataType`, `reference` | `unit`, `factor`, `linear`, `description`, `usage`, `levels`, `display`, `decimalPlaces` |
| `action` | `id`, `name`, `type`, `active`, `_inactive`, `service`, `command`, `params` | `source: "state"`, `dataType`, `description`, `confirm`, `children: []` |
| `config` | `id`, `type`, `active`, `dataType`, `ctrl`, `opts`, `source` | `defaultValue`, `name`, `description` |
| `event-logic` | `id`, `type`, `active` | `name` |

`dataType`: `number`, `string`, `boolean`, `object`. Команды — обычные дочерние узлы подсистемы (например, «Команды управления»), а не массив верхнего уровня.

## Аргумент

`source` всегда `"state"`. `reference` — ключ параметра в данных устройства (`well/telemetry/level`, `in_out_1`); у части образцов он совпадает с `id`. `unit` — из подтверждённого набора платформы: `temperature-celsius`, `speed-kilometer-per-hour`, `electric-volt`, `electric-ampere`, `percent`, `length-meter`, `volume-liter`, `duration-millisecond`, `duration-microsecond`. Единицу не выдумывать: искать в документации устройства, в `GET /api/v1/locale` (поле `units`) или в образце той же величины; если не подтверждено — спросить.

`factor` и `linear` — только при масштабировании: `linear: true` для пропорционального пересчёта, `factor` — коэффициент. Не добавляй их «на всякий случай» с выдуманным значением; если масштаб неизвестен, спроси.

## Действие

```json
{
  "id": "pump_on",
  "name": "Включить насос",
  "active": true,
  "type": "action",
  "source": "state",
  "dataType": "string",
  "params": {"command": "{\"pump_control\": \"ON\"}"},
  "command": "text_command",
  "service": "ric-gate",
  "children": [],
  "description": "Команда на запуск скважинного насоса",
  "_inactive": false
}
```

`service: "ric-gate"`; `command: "text_command"` — текстовая команда, её тело лежит строкой JSON в `params.command`. Для публикации в топик используется `command: "publish"` с `params: {"topic": "...", "payload": "..."}` (+ `qos`). Топик, тело и `command` берутся из документации устройства; не подставляй `publish` вместо `text_command` и наоборот без подтверждения.

## Имена и идентификаторы

- `id` — уникальный в модели, латиница `snake_case` (`liquid_level`, `pump_on`), без пробелов. Исключение — фиксированный `external-software-modules`. Набор `id` должен совпадать с тем, что присылает устройство.
- `name` — понятное человеку название **на русском** (`Уровень жидкости`, `Включить насос`), как в созданной модели и всех рабочих экспортах.
- `description` — назначение и диапазоны значений **на русском** (`0 - выкл, 1 - вкл`); не переводи существующие названия и описания без просьбы.
- `_inactive: false` — по правилу на каждом узле. В части платформенных экспортов (`model_automatic_aqwa.json`, `model_smart_home.json`) поле отсутствует, поэтому оно не признак корректности платформы, но в генерируемых моделях ставится везде.

## Запрещено

- Копировать служебные поля экспорта: `_parentId`, `_isRoot`, `_levels`, `_dataPath`, `user`, `group`, `owner`, `time`.
- Придумывать `reference`, `unit`, `base` или тело команды: только подтверждённые значения либо вопрос пользователю.
- Менять `base` на «похожий» протокол: подтверждены `mqtt`, `nidd`, `teltonika`, `lora`; для остальных нужен эталон или документация.
- Удалять блок `external-software-modules` и складывать в него параметры.

## Проверка

Проверку запускай bundled-валидатором `scripts/validate.py` навыка `rightech-output`; если кодовый инструмент не видит ресурс другого навыка, сообщи об этом и выполни только структурную проверку, не утверждая, что скрипт запускался.

Покажи пользователю: ближайший образец, отличия от него, число узлов и список параметров. Готовый файл для импорта собирает навык `rightech-output`.
