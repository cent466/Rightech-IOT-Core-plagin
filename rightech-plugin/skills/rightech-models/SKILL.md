---
name: rightech-models
description: Создание и правка JSON моделей Rightech (дерево подсистем, аргументов, действий). Использовать, когда нужна модель устройства, добавление параметра/команды/события, разбор экспорта модели, а также по запросам «модель устройства», «параметры модели», "rightech model", "add argument", "model json".
---

# Модели

## Перед генерацией

Сначала пройди `rightech-research`: самостоятельно найди официальную документацию на точную модель устройства и протокол. Затем `rightech-questions` — спроси только то, чего документация, образцы и описание пользователя не разрешили. Загрузи навык `rightech-samples` и попроси его подобрать ближайший образец модели; образцы и правила встроены в ресурсы этого навыка для Claude Desktop.

## Структура (подтверждено образцами)

Верхний уровень сущности: `name`, `base`, `description`, `props`, `data` (дерево). `props` содержит `bots`, `hardwareEvents`, `idPattern`, `order`, `prefix`, `protocol`.

Корень дерева: `id: "root"`, `type: "subsystem"`, `active`, `name` (= имени модели), `description`, `children`.

Типы узлов, встречающиеся в образцах: `subsystem`, `argument`, `action`, `config`, `event-logic`. Тип `event` в образцах отсутствует — если он нужен, сначала получи эталон из аккаунта.

| Тип | Обязательные поля | Часто встречаются |
|---|---|---|
| `subsystem` | `id`, `type`, `active`, `children` | `name`, `description` |
| `argument` | `id`, `type`, `active`, `dataType` | `unit`, `reference`, `source`, `factor`, `linear`, `levels`, `display`, `decimalPlaces` |
| `action` | `id`, `type`, `active`, `service`, `command`, `params` | `confirm`, `description`, `source` |
| `config` | `id`, `type`, `active`, `dataType`, `ctrl`, `opts`, `source` | `defaultValue` |

## Правила

- `dataType`: `number`, `string`, `boolean`, `object`.
- `unit` не выдумывать: искать в официальной документации устройства и справке Rightech; брать из образца той же физической величины или из документации `GET /api/v1/locale` (поле `units`). Если после поиска значение не подтверждено — спросить пользователя.
- `base` выбирать из подтверждённых: `mqtt`, `nidd`, `teltonika`, `lora`. Для нового протокола сначала найти его в официальной справке Rightech; если не найден — попросить экспорт/ссылку из аккаунта. Не подставлять ближайшее значение автоматически.
- `id` узлов — латиница `kebab-case`, уникальны в пределах модели. Набор `id` должен совпадать с тем, что реально присылает устройство.
- Действие MQTT: `service: "ric-gate"`, `command: "publish"`, `params: {"topic": "...", "payload": "..."}`; `qos` при необходимости.
- Не копировать служебные поля: `_id`, `_at`, `owner`, `group`, `time`, `_parentId`, `_inactive`, `copy`, `_isRoot`, `_levels`, `_dataPath`.

## Проверка

Проверку запускай bundled-валидатором `scripts/validate.py` навыка `rightech-output`; если кодовый инструмент не видит ресурс другого навыка, сообщи об этом и выполни только структурную проверку, не утверждая, что скрипт запускался.

Покажи пользователю: ближайший образец, отличия от него, число узлов и список параметров. Готовый файл для импорта собирает навык `rightech-output`.
