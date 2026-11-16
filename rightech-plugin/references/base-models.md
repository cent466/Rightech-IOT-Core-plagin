# Базовые модели платформы: протоколы и правила генерации

Документ составлен 2026-11-16 по 16 базовым моделям, выгруженным из платформы Rightech (папка `base_models/` рабочего проекта, в публичный репозиторий и ZIP не входит). Это не пользовательские данные, а платформенные каталоги параметров, поэтому в них нет описаний и русских названий — брать из них нужно **каркас**, а не готовое содержимое.

Задача документа: по описанию устройства и его документации выбрать правильные `base`/`props`/`protocol` и собрать модель, которая пройдёт `validate.py --mode new` и импортируется в платформу.

## Как читать

- **Наблюдалось во всех 16** — общая часть формата, её можно повторять.
- **Наблюдалось в части** — свойство конкретного протокола; переносить только вместе с этим протоколом.
- **Не подтверждено** — в базовых моделях нет; не выдумывать.

Значения `base`, `props.protocol`, `idPattern`, `prefix`, `order`, `root.base` ниже — точные, скопированы из экспортов.

---

## 1. Каталог протоколов

| `base` | `props.protocol` | `idPattern` | `prefix` | `order` | `root.base` | `mixins` | Узлы (подсистем / аргументов / действий) | Особенности каркаса |
|---|---|---|---|---:|---|---|---|---|
| `mqtt` | `mqtt` | `mqtt-$tagname-$nanoid` | `""` | 1 | — | `[]` | 6 / 7 / 2 | `bots: true`, `helper: {"nostate": "@ric-docs/docs/helpers/mqtt.md"}`, `auth` (username/password), `x509`, `parserParams`, `defaultNode: "temperature"`, `defaultGateCommandTimeout: 45` |
| `wialon-ips` | `wialon` | `wialon:<imei>` | `wialon:` | 2 | — | `[]` | 9 / 55 / 4 | `bots: true`, `defaultGateCommandTimeout: 45`, команды `text_command` вида `#setout1=1#\r\n` |
| `wialon-combine` | `wialon` | `wialon:<imei>` | `wialon:` | 2.2 | `base` | `[]` | 23 / 86 / 6 | `defaultGateCommandTimeout: 45` |
| `arnavi3` | `arnavi3` | `arnavi3:<imei>` | `arnavi3:` | 2.4 | `base` | `[]` | 25 / 128 / 6 | `defaultGateCommandTimeout: 45`, команды — байтовые строки и `data:text/plain;base64,…` |
| `egts` | `egts` | `egts:<terminalid>` | `egts:` | 2.5 | — | `[]` | 15 / 56 / 0 | только параметры |
| `websocket` | `websocket` | `ws-$tagname-$nanoid` | `""` | 2.9 | `base` | `[]` | 8 / 17 / 2 | `auth`, `idInput: {"label": "ID"}`, `namePattern: "ws-$tagname-$nanoid"` |
| `http-ric` | `http` | `http-$tagname-$nanoid` | `""` | 3 | — | `[]` | 4 / 2 / 0 | `defaultNode: "temperature"`; в `base` суффикс `-ric`, в `protocol` — `http` |
| `galileosky` | `galileosky` | `galileosky:<imei>` | `galileosky:` | 4 | `galileosky` | `[]` | 130 / 500 / 26 | `defaultGateCommandTimeout: 45`, текстовые команды (`Status`, `IMEI`, `inall`) |
| `teltonika` | `teltonika` | `teltonika:<imei>` | `teltonika:` | 5 | `wialon-ips` | `[]` | 15 / 49 / 13 | `defaultGateCommandTimeout: 45`, команды `getinfo`, `getio`, `setdigout 1???` |
| `navtelecom` | `ntcb` | `ntcb:<imei>` | `ntcb:` | 8 | `navtelecom` | `[]` | 51 / 313 / 46 | `text_command` кладёт тело в `params.text` (а не `params.command`); `dataType: "number[]"` |
| `autofon8` | `autofon8` | `autofon8:<imei>` | `autofon8:` | 8.2 | `wialon-ips` | `[]` | 65 / 226 / 0 | только параметры |
| `lora` | `lora` | `eui:$randhex` | `eui:` | 9 | — | `[]` | 6 / 4 / 0 (+5 `config`) | `disableOnline: true`, `defaultNode: "payload"`, `idInput` DevEUI (`HexInput`, 8 байт), узлы `config` `@lora.*` |
| `nidd` | `nidd` | `""` + `idValidate: false` | `""` | 10 | — | `[]` | 4 / 1 / 0 | `disableOnline: true`, `defaultNode: "payload"`, `idInput: {"label": "External ID"}` |
| `coap` | `coap` | `coap-$tagname-$nanoid` | `""` | 12 | `base` | `[]` | 6 / 44 / 0 | ответы CoAP целиком в параметрах |
| `lwm2m` | `lwm2m` | `lwm2m-$tagname-$nanoid` | `""` | 13 | `base` | `[]` | 19 / 106 / 20 (+4 `level`) | команды `coap_command` с `params.method/path/data` |
| `smpp` | `smpp` | `smpp:<number>` | `smpp:` | 30 | `smpp` | `["smpp-mixin"]` | 4 / 2 / 0 | `icon` (SVG), `defaultNode: "root"`; `mixins` непустые |

Правила, которые видны из таблицы:

- **`base` ≠ `props.protocol` у семи моделей**: `wialon-ips`/`wialon-combine` → `wialon`, `http-ric` → `http`, `navtelecom` → `ntcb`. Не «исправляй» эти пары и не подставляй `base` в `protocol`.
- **`lora`, а не `lorawan`**; `http-ric`, а не `http`; `nidd` без `idPattern` (пустая строка и `idValidate: false`). Идентификаторы устройств: `<imei>`, `<terminalid>`, `<number>`, `eui:$randhex` или `$tagname-$nanoid` — это шаблоны платформы, а не значения устройства.
- `root.base` — отдельное поле, не копия `base` модели. Встречается `base`, `wialon-ips`, `galileosky`, `navtelecom`, `smpp` или отсутствует. Смысл не подтверждён: если протокол есть в таблице — оставь значение как в таблице, иначе не добавляй поле.

## 2. Как выбрать `base`

1. Определи **протокол обмена устройства с платформой**, а не производителя. Один производитель может иметь несколько протоколов (Wialon IPS и Wialon Combine), а одна модель устройства — работать через шлюз.
2. Соотнеси с таблицей: MQTT → `mqtt`; HTTP-интеграция Rightech → `http-ric`; LoRaWAN (OTAA/ABP, DevEUI/AppKey) → `lora`; NB-IoT NIDD → `nidd`; CoAP → `coap`; LwM2M → `lwm2m`; WebSocket → `websocket`; SMPP → `smpp`; EGTS → `egts`; Wialon IPS → `wialon-ips`; Wialon Combine/AGPS → `wialon-combine`; Teltonika FMB/FMC → `teltonika`; Galileosky → `galileosky`; Arnavi → `arnavi3`; Автофон → `autofon8`; Navtelecom Flex → `navtelecom`.
3. Если протокола нет в таблице — **не подставляй похожий**. Запроси экспорт модели этого протокола из аккаунта или документацию платформы; до подтверждения генерация не начинается.
4. Если устройство отправляет данные JSON по MQTT, но с собственными топиками — это `mqtt`; топик и `payload` задаются в командах и `reference`, `base` от них не зависит.

## 3. Паспорт модели и `props`

Обязательный минимум `data`: `name`, `description`, `base`, `props`, `data` (дерево). `name` и `description` — по-русски, оба непустые (валидатор `--mode new` без них падает).

`props`, общие для всех 16:

```json
{
  "bots": false,
  "hardwareEvents": false,
  "helper": "",
  "prefix": "",
  "order": 1,
  "typeInput": {"hidden": false},
  "statusInput": {"hidden": false},
  "descriptionInput": {"hidden": false},
  "protocol": "mqtt",
  "idPattern": "mqtt-$tagname-$nanoid"
}
```

- `bots`: `true` только у `mqtt` и `wialon-ips`, у остальных `false`.
- `hardwareEvents`: `false` во всех 16.
- `helper`: пустая строка во всех, кроме `mqtt` (`{"nostate": "@ric-docs/docs/helpers/mqtt.md"}`). Оба варианта допустимы.
- `prefix`, `order`, `idPattern`, `protocol` — из таблицы протокола. `order` — порядок сортировки в списке моделей, значение не влияет на работу.
- Дополнительные ключи добавляй **только** из строки своего протокола: `defaultGateCommandTimeout`, `auth`, `x509`, `parserParams`, `defaultNode`, `disableOnline`, `idInput`, `idValidate`, `namePattern`, `icon`. Например, `auth`/`x509`/`parserParams` подтверждены у `mqtt`, `auth` — у `websocket`, `idInput` — у `lora`, `nidd`, `websocket`.
- `mixins`: пустой список, кроме `smpp` (`["smpp-mixin"]`).

## 4. Дерево `data.data`

Во всех 16:

- корень: `id: "root"`, `type: "subsystem"`, `active: true`, `_inactive: false`, `name` (у платформенных каталогов совпадает с именем модели, у своей модели может отличаться), `children`;
- **первый дочерний узел — всегда `external-software-modules`**, `type: "subsystem"`, `active: true`, `copy: true`, `children: []`;
- дальше — содержательные подсистемы: `params`/`parameters`, `times`, `server-info`, `navigation`, `commands`/`cmd`, `config` и т. п. Названия подсистем задавай по-русски и по смыслу задачи, а не копируй платформенные.

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

В платформенных экспортах у этого блока иногда `name: null` или английское `External software modules` — в новых моделях ставь русское название. Параметры в него не кладут.

## 5. Типы узлов

| `type` | Обязательные поля | Что ещё встречается |
|---|---|---|
| `subsystem` | `id`, `name`, `type`, `active`, `children`, `_inactive` | `description`, `copy` (только у блока внешних модулей) |
| `argument` | `id`, `name`, `type`, `active`, `_inactive`, `dataType`, `reference` | `source`, `unit`, `factor`, `linear`, `levels`, `display`, `description`, `children` |
| `action` | `id`, `name`, `type`, `active`, `_inactive`, `service`, `command`, `params` | `source`, `dataType`, `description`, `children` |
| `config` | `id`, `name`, `type`, `active`, `_inactive`, `dataType`, `ctrl`, `opts`, `source: "config"` | `defaultValue`, `_dataPath` (служебное) |
| `level` | `id`, `name`, `type`, `active`, `_inactive`, `index`, `value`, `color` | — |

Узел `event-logic` встречался в других рабочих моделях, но ни в одной из 16 базовых нет. Узел `event` не существует в платформе (проверено на живом аккаунте 2026-11-16): событие модели задаётся `event-logic` с полями `id`, `name`, `active`, `children`.

### Аргумент

```json
{
  "id": "liquid_level",
  "name": "Уровень жидкости",
  "type": "argument",
  "active": true,
  "source": "state",
  "dataType": "number",
  "reference": "well/telemetry/level",
  "unit": "length-meter",
  "factor": 1,
  "linear": true,
  "description": "Уровень жидкости в скважине, м",
  "children": [],
  "_inactive": false
}
```

- `dataType`: `number` (1111 вхождений), `boolean` (310), `string` (160), `object` (6), `number[]` (9, только Navtelecom). `number[]` подтверждён как значение поля — используй его, если документация описывает массив чисел.
- `source: "state"` у параметров телеметрии; `config` — только у узлов `config`.
- `factor`/`linear`: `factor: 1` и `linear: true` — обычный случай; в базовых моделях встречаются `0.001`, `0.01`, `0.1`, `10`, `1000` с `linear: true`, а также `linear: false` без пересчёта (координаты). Коэффициент берётся из документации, не выдумывается.
- `unit`: 24 подтверждённых значения — `angle-degree`, `angle-revolution-per-minute`, `temperature-celsius`, `electric-volt`, `electric-millivolt`, `electric-ampere`, `electric-milliampere`, `electric-milliampere-hour`, `duration-millisecond`, `duration-second`, `duration-minute`, `duration-hour`, `percent`, `decibel`, `frequency-hertz`, `speed-kilometer-per-hour`, `speed-meter-per-second`, `mass-kilogram`, `length-meter`, `length-kilometer`, `volume-liter`, `digital-byte`, `digital-kilobyte`, `currency-rub`. Другое значение — только если оно подтверждено документацией или `GET /api/v1/locale`.
- Группы: `argument` с `children` — это объект/набор (`dataType: "object"` для JSON-объекта, `number` для группы входов). У дочерних — свой `reference` (`pos.lat`, `tag_9.in.0`).
- `levels` (словарь) — шкала отображения: `{"type": null}` (пустая), `{"type": "numeric", "value": [...]}`, `{"type": "range", "value": [...]}`; элементы — `{color, name, value}`. Отдельные узлы `level` — дочерние у числового аргумента, `id` вида `<argument_id>.levels.<n>`, поля `index`, `value`, `color`. Шкалы не выдумывай: нужны значения из документации или от пользователя.
- `display`: `{}` (обычный), `{"hints": ["hex"]}`, `{"svg": "<svg…>"}` — оформление, не влияет на разбор. Не обязательно.

### Действие

`service: "ric-gate"`. `params` завязаны на `command`:

| `command` | `params` | Где подтверждено |
|---|---|---|
| `text_command` | `{"command": "Status"}` — тело как строка; байты могут быть `"\u0001\u0001"`, base64 — `"data:text/plain;charset=utf-8;base64,AQc="` | Galileosky, Wialon IPS/Combine, Teltonika, Arnavi3 |
| `text_command` | `{"text": "*?V"}` — тело в ключе `text` | Navtelecom |
| `publish` | `{"topic": "base/relay/led1", "payload": "1"}` (+ `qos`) | MQTT |
| `coap_command` | `{"method": "get", "path": "/1", "data": ""}` | LwM2M |
| `text_command` | `{"command": "{\"device\":\"led\"}", "topic": "…", "payload": "1"}` — тело плюс топик/полезная нагрузка | WebSocket |

Формат команды (имя, тело, топик, байты) берётся **только** из документации устройства. Не переводи `text_command` в `publish` и обратно, не перекодируй байты «как удобнее».

### `config`

Только у протоколов с настройками устройства (в базовых моделях — LoRaWAN). Узел описывает настройку, а не телеметрию:

```json
{
  "id": "@lora.activation",
  "name": "Activation Method",
  "type": "config",
  "active": true,
  "source": "config",
  "dataType": "string",
  "ctrl": "Select",
  "defaultValue": "otaa",
  "opts": {"options": [{"label": "OTAA", "value": "otaa"}]},
  "children": [],
  "_inactive": false
}
```

`_dataPath` (`["lora", "activation"]`) — служебное поле экспорта, `make_import_file.py` его удаляет. Не добавляй `config` в модель протокола, у которого таких настроек нет.

## 6. Что нельзя переносить из базовых моделей

Базовые модели — каталоги платформы на сотни параметров для всех устройств протокола. Из них берётся только структура.

- **Не копируй весь каталог параметров.** 500 аргументов Galileosky или 313 Navtelecom относятся к любым устройствам протокола; в модели конкретного устройства оставляй только параметры, которые оно реально присылает по документации.
- **Не копируй `reference` чужого протокола.** Значения вида `tag_5C`, `in_out_81`, `custom106`, `option.SRV_SEND` осмысленны только в своём протоколе; `reference` берётся из документации устройства.
- **Не копируй платформенные названия и описания.** В каталогах `description: null`, английские `name` (`Turn-on LED`, `Position (JSON)`), названия подсистем `Params`, `Server information`. В новой модели `name`/`description` — по-русски, с назначением и единицей.
- **Не переноси служебные поля:** `_parentId`, `_localId`, `_isRoot`, `_levels`, `_dataPath`, `_at`, `selected`, `checked`, `removed`, `disabled`, `expanded`, `external`, а также `owner`, `group`, `time`, `_id` и оболочку `version`/`origin`/`user`/`group` (их добавляет скрипт сборки).
- **Не копируй платформенные `icon` (SVG), `auth`, `x509`, `parserParams`** в модель, где они не нужны: это настройки протокола, а не устройства; `auth` не содержит паролей и не должен их содержать.
- **Не копируй `name` корня из каталога**: у `Autofon8` там лишний пробел (`"Autofon8 "`), у остальных — английское имя протокола.
- **Не выдумывай `order`, `prefix`, `idPattern`, `defaultGateCommandTimeout`.** Бери из таблицы; для протокола вне таблицы — из подтверждённого экспорта.

## 7. Минимальный каркас для нового протокола

Пример для MQTT: два параметра и одна команда. Обрати внимание на `props` из таблицы, блок внешних модулей и подсистему команд.

```json
{
  "name": "Датчик температуры и влажности",
  "description": "Показания температуры и влажности, публикуемые по MQTT",
  "base": "mqtt",
  "mixins": [],
  "props": {
    "bots": true,
    "hardwareEvents": false,
    "helper": "",
    "prefix": "",
    "order": 1,
    "typeInput": {"hidden": false},
    "statusInput": {"hidden": false},
    "descriptionInput": {"hidden": false},
    "protocol": "mqtt",
    "idPattern": "mqtt-$tagname-$nanoid"
  },
  "data": {
    "id": "root",
    "name": "Датчик температуры и влажности",
    "type": "subsystem",
    "active": true,
    "children": [
      {
        "id": "external-software-modules",
        "name": "Внешние программные модули",
        "active": true,
        "copy": true,
        "type": "subsystem",
        "children": [],
        "_inactive": false
      },
      {
        "id": "params",
        "name": "Параметры",
        "type": "subsystem",
        "active": true,
        "children": [
          {
            "id": "temperature",
            "name": "Температура",
            "type": "argument",
            "active": true,
            "source": "state",
            "dataType": "number",
            "reference": "sensors/temperature",
            "unit": "temperature-celsius",
            "factor": 1,
            "linear": true,
            "description": "Температура воздуха, °C",
            "children": [],
            "_inactive": false
          }
        ],
        "_inactive": false
      },
      {
        "id": "commands",
        "name": "Команды управления",
        "type": "subsystem",
        "active": true,
        "children": [
          {
            "id": "interval_60",
            "name": "Интервал 60 секунд",
            "type": "action",
            "active": true,
            "service": "ric-gate",
            "command": "publish",
            "params": {"topic": "device/cmd", "payload": "{\"interval\": 60}"},
            "description": "Задать интервал публикации 60 секунд",
            "children": [],
            "_inactive": false
          }
        ],
        "_inactive": false
      }
    ],
    "_inactive": false
  }
}
```

Для протоколов с `defaultNode` (`mqtt`, `http-ric`, `lora`, `nidd`, `smpp`) добавь этот ключ в `props` из таблицы. Для `lora`/`nidd` — `disableOnline: true`; для `websocket` — `auth`, `idInput`, `namePattern`.

## 8. Порядок сборки и выдачи файла

1. Определи протокол и `base` по разделу 2, зафиксируй источник (документация устройства/платформы).
2. Возьми `props`-каркас протокола из раздела 1 и значения из раздела 3.
3. Собери дерево: корень → `external-software-modules` → подсистемы (`Параметры`, `Команды управления`, при необходимости `Конфигурация`).
4. Добавь `argument` только для параметров из документации: `reference` — точный ключ, `id` — `snake_case` по смыслу, `unit` — из списка, `factor`/`linear` — только при подтверждённом масштабе.
5. Добавь `action` в подсистему команд в форме, которую требует протокол (раздел 5).
6. Прогони проверку: `python3 scripts/validate.py model.json --store models --mode new`. Ошибки исправляй в модели, а не в валидаторе.
7. Собери файл: `python3 scripts/make_import_file.py model.json --store models`. Скрипт уберёт служебные поля, добавит `_id` и оболочку, сохранит `<дата>_Модель_<имя>.json` в `rightech-output/`.
8. Отдай файл и инструкцию: «Модели → плюс → Создать → Загрузить готовую модель → файл → Создать».

Если протокол вне таблицы, а экспорта нет — остановись и запроси подтверждение. Готовая модель без подтверждённого `base` бесполезна: платформа не привяжет её к устройствам.

## 9. Чек-лист перед выдачей

- [ ] `base` и `props.protocol` — пара из таблицы, а не «похожий» протокол.
- [ ] `name` и `description` непустые, по-русски.
- [ ] Первый ребёнок корня — `external-software-modules` с `copy: true` и пустым `children`.
- [ ] У каждого `argument` есть `dataType` из подтверждённого набора, `reference` из документации, `unit` из списка (или отсутствует у `boolean`).
- [ ] У каждого `action` — форма `params`, соответствующая протоколу.
- [ ] Нет служебных полей экспорта и чужих идентификаторов.
- [ ] `validate.py --mode new` — без ошибок; предупреждения объяснены пользователю.
- [ ] Имя файла и путь совпадают с шаблоном, инструкция по импорту приложена.
