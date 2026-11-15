# Правила Rightech, выведенные из образцов

Документ составлен 2026-11-14 по 24 файлам из `primer_model`, `primer_scena`, `primer_geo`, `primer_obrabotka` (инвентарь — `references/samples-index.md`). Каждое правило сопровождается ссылкой на образец и путь к полю.

## Как читать этот документ

- **Наблюдалось во всех образцах** — поле присутствует во всех файлах типа. Это статистика экспортов, **не** доказательство, что API требует поле при `POST`.
- **Наблюдалось частично** — поле есть в части файлов; считать необязательным.
- **Не подтверждено** — формат отсутствует в образцах; требуется эталон из аккаунта или документация. Выдумывать значение запрещено.
- Все 24 файла имеют внешнюю оболочку экспорта с полями `version`, `origin`, `time`, `user`, `group`, `store`, `data`. Во всех 24: `version = 1`, `origin = "dev.rightech.io"`, а `store` совпадает с типом (`models`, `automatons`, `geofences`, `handlers`). Оболочка — формат экспорта; **не подтверждено**, что она отправляется в `POST` целиком.

## Служебные поля (удалять при создании)

При создании новой сущности из образца удалять: `_id`, `_at`, `owner`, `group`, `time`, а также `user`, `store`, `origin`, `version` внешней оболочки. Наблюдения:

| Поле | Модели | Сценарии | Геозоны | Обработчики |
|---|---|---|---|---|
| `_id` | 10/10 | 6/6 | 2/2 | 6/6 |
| `_at` | 6/10 | 6/6 | 2/2 | 0/6 |
| `owner` | 10/10 | 6/6 | 2/2 | 0/6 |
| `group` | 10/10 | 6/6 | 2/2 | 0/6 |
| `time` | 10/10 | 6/6 | 2/2 | 0/6 |

Внутри дерева модели дополнительно встречаются платформенные/редакторские поля узлов: `_parentId` (365 вхождений), `_inactive` (272), `copy` (10), `_isRoot` (9), `_levels` (6), `_dataPath` (5). **Не подтверждено**, какие из них API принимает, а какие восстанавливает сам. До проверки на тестовом проекте их нельзя ни слепо отправлять, ни слепо удалять: `_parentId` может быть нужен для сборки дерева.

---

## 1. Модели (`store = "models"`)

### Обязательные поля (наблюдались во всех 10)

`name`, `base`, `description`, `props`, `data` — верхний уровень `data`-объекта.
Ссылки: `primer_model/model_mqtt3.json → $.name, $.base, $.description, $.props, $.data`.

`props` во всех 10 содержит: `bots` (bool), `hardwareEvents` (bool), `idPattern` (str), `order` (int), `prefix` (str), `protocol` (str); `helper` — 10/10, но типом различается (`dict` в 5, `str` в 5) — противоречие, см. «Нерешённые вопросы».

### Необязательные / частично

`links` (4/10), `mixins` (7/10), `_at` (6/10).

### Корень дерева `data`

Во всех 10: `data.id = "root"`, `data.type = "subsystem"`, `data.active` (bool), `data.children` (list), `data.name` (совпадает с `name` модели в 10/10), `data.description`.
Один образец содержит `_isRoot: true` (`primer_model/model_avton_dynamograph.json → $.data._isRoot`).

### Типы узлов, реально встречающиеся в дереве

| `type` | Кол-во | Все поля узла (варианты) |
|---|---:|---|
| `subsystem` | 96 | `id`, `name`, `type`, `active`, `children`, иногда `description`, `_inactive`, `_parentId`, `copy`, `_isRoot` |
| `argument` | 439 | обязательно `id`, `name`, `type`, `active`, `dataType`; часто `children`, `unit`, `reference`, `source`, `factor`, `linear`, `levels`, `display`, `decimalPlaces`, `description` |
| `action` | 34 | `id`, `name`, `type`, `active`, `service`, `command`, `params`; иногда `confirm`, `dataType`, `description`, `source`, `children` |
| `config` | 6 | `id`, `name`, `type`, `active`, `dataType`, `ctrl`, `opts`, `source`, `defaultValue` (3), `_dataPath`, `_inactive`, `_parentId` |
| `event-logic` | 4 | только `id`, `name`, `type`, `active` (`primer_model/model_smart_home.json`) |

**Тип `event`, упомянутый в ТЗ, в образцах не встретился ни разу.** События в сценариях ссылаются на узлы по `id`, но узел-событие надо получить эталоном.

### Допустимые значения (наблюдались)

- `base`: `mqtt` (5), `nidd` (3), `teltonika` (1), `lora` (1). В ТЗ упомянуты `lorawan`, `http` — в образцах их нет; **не подтверждено**. Обратите внимание: в образцах именно `lora`, а не `lorawan`.
- `dataType` аргументов: `number` (366), `string` (54), `boolean` (29), `object` (4).
- `source`: `state` (305), `config` (5).
- `action.service`: `ric-gate` (30), `ric-logic-v3.user-event` (4).
- `action.command` для `ric-gate`: `publish` (27), `text_command` (5) + устройства-специфичные `getinfo`, `getio`, `setdigout …` (Teltonika).
- `params` действия: `topic` и `payload` (27/27 с `params`), `qos` (11).

### Идентификаторы

- Дубликатов `id` внутри одной модели не обнаружено (проверены все 10). Требование уникальности подтверждается практикой образцов.
- Стиль преимущественно латиница в `kebab-case` (`external-software-modules`, `online`, `_ts`), но встречаются суффиксы-хэши (`tds-jc5be`) и даже кириллица (`Пример`) — формат не валидируется платформой, поэтому плагин генерирует латиницу `kebab-case`, а валидатор проверяет только уникальность и непустоту.
- `reference` у аргумента в 216 случаях совпадает с `id` аргумента; смысл расхождения не установлен.

### Связи

Модель → узлы по `id`. Сценарии ссылаются на модель через `model`/`models` (см. раздел 2), обработчики — через `parameters`/`crossMappings` (раздел 4).

### Типовые шаблоны

- Простейшая модель для разбора: `primer_model/model_avton_a845_a855_thermometer_nidd.json` (15 узлов).
- Модель с действиями MQTT: `primer_model/model_automatic_aqwa.json`.
- Модель с `config`/`event-logic`: `primer_model/model_smart_home.json`.

### Запрещено / опасно

- Отправлять `_id`, `owner`, `group`, `time`, `_at` из экспорта.
- Придумывать `unit`: единицы брать из `GET /api/v1/locale` (ТЗ) или из образца.
- Угадывать `base` для протокола, которого нет в образцах.

### Нерешённые вопросы

1. `props.helper`: `dict` или `str`? Оба варианта в рабочих моделях.
2. `props.protocol` в образцах повторяет `base` (`mqtt`, `nidd`, `teltonika`, `lora`); совпадает ли он с `base` всегда и какие ещё значения допустимы — неизвестно.
3. Нужны ли `_parentId`/`_inactive`/`copy`/`_isRoot` в `POST /models`, или дерево собирается только через `/nodes?attachTo=`? ТЗ описывает оба пути.
4. Формат узла `event` отсутствует в образцах.

---

## 2. Сценарии / автоматизации (`store = "automatons"`)

### Обязательные поля (6/6)

`name`, `description`, `model`, `models`, `processId`, `data`, а также служебные `_id`, `_at`, `owner`, `group`, `time`.
Ссылки: `primer_scena/*.json → $.name, $.description, $.model, $.models, $.processId, $.data`.

`models` — список идентификаторов моделей, в 6/6 совпадает с `[model]`. `model` — строка `_id` модели.

### Ключевая особенность

`$.data` — **строка**, внутри которой лежит JSON-документ с ключами `states` и `transitions` (6/6). Пример: `primer_scena/scenario_day_night.json → $.data`.
Валидатор обязан: распарсить строку, проверить вложенный JSON, и только потом проверять ссылки. Отправлять `data` нужно строкой (это то, что видно в экспорте), но **не подтверждено** API-контрактом.

### Структура вложенного JSON

```
{
  "states": { "<stateId>": { "data": {...}, "position": {"top": int, "left": int} } },
  "transitions": { "<transitionId>": { "drawMode": str, "points": [...], "data": {...}, "version": int, "block": {...} } }
}
```

**Состояния** — `states.<id>.data`:

- обязательные во всех 6: `type`, `id`, `width`, `height`;
- `type`: `init` (6), `final` (6), `state` (22);
- часто `name`, `description`, `onenter`, `onexit`, `showDescription`, `stateType`;
- `stateType` — пустая строка (20) или отсутствует (14): семантика не установлена;
- `onenter`/`onexit` — список действий вида `{id, name, args}`;
- `position` — координаты в редакторе (`top`, `left`).

**Переходы** — `transitions.<id>.data`:

- обязательные во всех 6: `id`, `event`, `owner`, `target`; в 39/51 переходах также `name`, `description`;
- `owner`/`target`: `{id: <stateId>, point: {location: "left"|"right"|"top", id: int}}` — ссылки на состояния;
- `condition` (строка) — 7 переходов; `userCode` — 8; `commandId` — 2 (значение пустой строкой); `eventParameters` — 4; `showCondition`, `showDescription` — частично;
- техническая обвязка: `drawMode` (`"rou"` во всех), `points` (геометрия линии в редакторе), `version: 3`, `block` (`{data:{type:"connectionBlock", connectionKey}, layout:{width,height,position:{x,y}}, key}`).

### Значения `event`, встреченные в образцах

`init` (6), `es-recive-device-data` (7), `immediate-transition` (5), `1st` (6), `3st` (5), `Canteen` (5), `2st` (5), `in_admin_office` (2), `1st_exit`, `3st_exit`, `Canteen_exit`, `2st_exit`, `out_admin_office`, `schedule-timer#1-done`, `schedule-timer#2-done`, `es-control-timer#2-done`, `xn5wl`, `u89d3`.

Это **не полный каталог**: часть значений — пользовательские идентификаторы. Источник полного списка системных событий — документация, а не образцы.

### Действия в `onenter`/`onexit`

Наблюдались `id`: `send-push-message` (13), `send-telegram` (5), `change-value` (7), `create-task` (3), `gen-user-event` (2), `timer#N-start`/`-stop`, `schedule-timer#N-start`/`-stop`, а также пользовательские `<node-id>-<суффикс>` (`output_controlon-vq8f6`), соответствующие действиям модели.

Аргументы действий в `args` всегда в форме `{ "<argName>": { "id": ..., "value": ..., "dataType": ... } }`; для строковых аргументов без метаданных встречается `{"value": ...}`. Пример: `primer_scena/scenario_day_night.json → states.2.data.onenter[0].args.period`.

### Cross-сценарий (1/6)

`primer_scena/scenario_a555_10_2581_alarm.json` содержит `elementType: "cross"` и `crossElements: [{type:"argument", tag:"import", id, name, dataType}]`. Отличие от «по параметрам модели» — именно эти поля; `model`/`models` присутствуют и там.

### Необязательные

`version` (1/6), `elementType` (1/6), `crossElements` (1/6).

### Запрещено / опасно

- Считать `data` объектом: это строка.
- Переносить координаты редактора (`position`, `points`, `block.layout`) как «логику» — они влияют только на отображение, но менять их формат нельзя без эталона.
- Ссылаться на `stateId`, отсутствующий в `states`, или на `model`, отсутствующий в проекте.

### Нерешённые вопросы

1. Полный каталог `event` и `args` системных действий (`send-telegram`, `send-push-message`, `create-task`, `change-value`, `gen-user-event`, таймеры) — нужен справочник или эталон на каждое действие.
2. Обязателен ли `processId` и как он генерируется? Во всех 6 это короткая строка (`plc3gjqs`), но правило формирования неизвестно.
3. Нужны ли `position`/`points`/`block` при создании через API.
4. `stateType` — какие значения допустимы, кроме пустой строки.

---

## 3. Геозоны (`store = "geofences"`)

### Обязательные поля (2/2)

`name`, `color`, `style`, `shape`, `floors`, `props` (+ служебные).
Ссылки: `primer_geo/geo_leningradskaya_oblast.json → $.name, $.color, $.style, $.shape, $.floors, $.props`.

### Формат

- `style`: `{fillOpacity: 0.2, opacity: 0.75, weight: 2}` — одинаково в 2/2.
- `shape.type`: `"polygon"` (2/2).
- `shape.points`: список пар `[широта, долгота]`.
- `shape.cutouts` (1/2): список `{type: "polygon", points: [...]}`.
- `floors`: пустой список (2/2).
- `props`: пустой объект (2/2).
- `color`: hex-строка (`#2986FF`, `#932df2`).

### Порядок координат — подтверждён данными

`[55.2336963, 41.2944163]` для Владимирской области и `[59.6683027, 30.0650571]` для Ленинградской: первая компонента — широта (55–60), вторая — долгота (30–42). Диапазоны обеих пар проверены по всем точкам обоих файлов: широта 55.10–59.68, долгота 30.06–42.98.
Ссылки: `primer_geo/*.json → $.shape.points[0]`.

### Полигон внутреннего формата `shape` не замкнут

В обоих образцах **внутреннего Rightech-формата** первая точка не равна последней. Не дописывай замыкающую точку в `shape.points`. Это правило не относится к GeoJSON во вкладке «Код»: там пользователь подтвердил сохранение `Feature/Polygon` с замкнутым кольцом и парами `[долгота, широта]` (см. `skills/rightech-geofences/SKILL.md`).

### Запрещено / опасно

- Для внутреннего `shape.points` менять порядок координат на `[долгота, широта]`: это перевернёт геозону; там используется `[широта, долгота]`.
- Для внутреннего `shape.points` требовать замыкания или автоматически дописывать первую точку.
- Смешивать правила внутреннего `shape` с GeoJSON во вкладке «Код»: в GeoJSON стандартный порядок `[долгота, широта]` и замкнутые кольца.
- Генерировать круг: формата нет в образцах.

### Нерешённые вопросы

1. Формат круга (`shape.type` + центр/радиус) — **отсутствует**, нужен эталон.
2. Нужны ли `floors`/`props`/`style` при создании или платформа подставляет значения по умолчанию.
3. Ограничение на количество точек: полигон в 8 636 точек весит 551 394 байта; лимит API неизвестен.
4. Привязка к объектам и события входа/выхода в образцах не представлены — только сама геометрия.

---

## 4. Обработчики (`store = "handlers"`)

### Обязательные поля (6/6)

`name`, `language`, `userCode`, `props`.
Ссылки: `primer_obrabotka/*.json → $.name, $.language, $.userCode, $.props`.

### Необязательные / частично

- `description` — 5/6;
- `parameters` — 5/6;
- `elementType` — 4/6 (`"model"` в 3, `"cross"` в 1);
- `crossElements` и `crossMappings` — 1/6.

### Допустимые значения (наблюдались)

- `language`: `javascript` (2), `typescript` (4).
- `props.setUndefinedParamTo`: `"prev"` (5/6) — платформа не затирает параметр значением `undefined`.
- `crossElements[]`: `{type:"argument", tag:"import", id, name, dataType, system:bool}`.
- `crossMappings`: объект с ключом `_id` модели, значение — список `{tag:"import", elementId, nodeId}`.

### `parameters` — связь обработчика с моделью

Структура: `parameters["m-<modelId>"]["h-<handlerId>"].import|export`, где значения — строки вида `"model.payload"` (импорт) и `"temperature"` (экспорт, имя аргумента модели).
Ссылка: `primer_obrabotka/handler_aqwa_control.json → $.parameters`.
В 1/6 (`cross`-вариант) `parameters` отсутствует, его роль выполняют `crossMappings`.

### Стиль кода (подтверждён 6/6)

- Точка входа — `export function process(...)`.
  - JavaScript: `export function process(payload)` — `primer_obrabotka/handler_aqwa_control.json`.
  - TypeScript: `export function process(payload: string, topic: string)` или `process(payload: unknown, topic = "")`.
- JS-обработчики парсят JSON: `JSON.parse(payload)`; отсутствующие поля удаляются, чтобы не затирать состояние (`Object.keys(result).forEach(k => result[k] === undefined && delete result[k])`).
- TS-обработчики декодируют бинарные пакеты: `ric.base64.decode(payload)`, `DataView`, чтение little-endian (`getUint32(offset, true)`), диспетчеризация по `classId`.
- Эпоха устройств: `new Date("1980-01-01T00:00:00.000+03:00")`, время = эпоха + секунды × 1000.
- Фрагментация: состояние между пакетами хранится в `ric.localStore.forObject.set({...})`; операции `OP_FRAGMENT = 10`, `OP_LAST_FRAGMENT = 11`.
- Защита от лишних данных: `hasBytes(view, offset, length)` перед чтением; неизвестный `classId` → возврат `{}`.
- Комментарии и типы — на русском, со ссылками на `https://rightech.io/developers/handlers` и `github.com/rightech/handler-libs`.

### Запрещено / опасно

- Обращаться к аргументам, которых нет в модели и пейлоаде.
- Возвращать поля со значением `undefined` при `props.setUndefinedParamTo = "prev"` (затрёт состояние) — см. приём в `AQWA_control`.
- Хардкодить секреты, адреса внешних сервисов и ключи в `userCode`.

### Нерешённые вопросы

1. Как формируются `h-<handlerId>` и `m-<modelId>` при создании нового обработчика: по `_id` ещё не созданной сущности? Нужен эталон `POST` из аккаунта.
2. Полный API `ric` (кроме `base64.decode` и `localStore.forObject`) — по образцам видно только два вызова; остальное нужно из `github.com/rightech/handler-libs`.
3. Допустимые `language` и версии TypeScript.
4. Как задавать `parameters` при создании, если модель ещё не имеет `_id`.

---

## Сводка противоречий с текстом ТЗ

| № | ТЗ утверждает | Образцы показывают | Что делать |
|---|---|---|---|
| 1 | Контур геозоны должен быть замкнут | Внутренний `shape` незамкнут; GeoJSON в Code — замкнутый Polygon (проверено пользователем) | Применять правило по конкретному формату: `shape` не замыкать; GeoJSON Polygon сохранять замкнутым |
| 2 | Тип узла `event` | Ни одного `event` | Получить эталон или убрать из поддерживаемых |
| 3 | `base`: mqtt, lorawan, http и др. | `lora`, а не `lorawan`; есть `nidd`, `teltonika` | Список `base` брать из документации/аккаунта |
| 4 | Сценарий — JSON со `states`/`transitions` | `data` — строка с вложенным JSON | Валидировать дважды (строка → JSON) |
| 5 | Минимальный узел модели: `type`, `id`, `name`, `active` | У `argument` ещё `dataType`; у `action` — `service`, `command`, `params`; есть `config`, `event-logic` | Расширить правила по типам |
| 6 | Образцы — эталон структуры | Внутри есть `_parentId`, `_inactive`, `copy`, `_isRoot` | Решить до `POST`, что удаляется |
| 7 | Обработчик: `name` + `userCode` | Также `language` и `props` во всех 6 | Считать `language`/`props` практически обязательными |
| 8 | Геозона: круг или многоугольник | Только полигоны | Круг — получить эталон |
