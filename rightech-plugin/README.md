<p align="center">
  <img src="assets/rightech-logo.png" alt="Rightech IoT Services" width="200">
</p>

# Rightech IoT Core — плагин генерации JSON

Плагин помогает агенту собирать корректный JSON сущностей Rightech (**модели**, **сценарии**, **геозоны**, **обработчики**) по правилам, выведенным из рабочих экспортов, проверять его локально и отдавать **готовый файл для ручного импорта**.

Подключение к API и токен не нужны: ничего не отправляется в аккаунт.

Работает в **Claude Code** и **Codex** (общий набор навыков `skills/`), а также локально без маркетплейса.

## Установка

### Claude Desktop / Claude.ai

Скачайте [готовый `rightech-plugin-claude.zip`](https://github.com/cent466/Rightech-IOT-Core-plagin/raw/refs/heads/main/rightech-plugin-claude.zip). В Claude откройте **Персонализация → Плагины → Добавить → Загрузить плагин** и выберите архив. ZIP содержит папку плагина с `.claude-plugin/plugin.json`, образцы и скрипты, встроенные внутрь навыков для песочницы Claude. Для запуска скриптов включите **Code execution and file creation** в **Настройки → Возможности**. После установки включите навыки на странице **Персонализация → Навыки** и начните новый чат.

### Claude Code

```bash
claude plugin marketplace add ./
claude plugin install rightech@rightech-plugins
```

Проверка манифеста: `claude plugin validate ./rightech-plugin`.

Без маркетплейса, прямо из папки:

```bash
claude --plugin-dir ./rightech-plugin
```

### Codex

В Codex нет установки ZIP-файлом: плагин подключается через marketplace — из GitHub или из локального клона.

```bash
# из GitHub
codex plugin marketplace add cent466/Rightech-IOT-Core-plagin --ref main
codex plugin add rightech@rightech-plugins

# из локального клона
codex plugin marketplace add ./
codex plugin add rightech@rightech-plugins
```

Дальше `codex /plugins` открывает браузер плагинов с вкладкой **Rightech Plugins**; в приложении ChatGPT/Codex тот же маркетплейс открывается на вкладке **Plugins**. После установки начните новый чат.

Имена файлов образцов сокращены до ASCII, потому что длинные русские имена не проходят `git checkout` на Windows (лимит длины пути) и установка из GitHub теряла часть образцов. Содержимое образцов и `name` сущностей внутри файлов не менялись.

Плагины Codex поддерживаются в CLI и приложении; расширение IDE их не поддерживает.

### Локально без плагина

Скопируйте `skills/` в каталог навыков агента (`~/.claude/skills/` для Claude, `~/.agents/skills/` или `.agents/skills/` для Codex) и оставьте `references/` и `scripts/` рядом — навыки ссылаются на них через `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}`.

## Что получает пользователь

| Тип | Файл | Как попадает в Rightech |
|---|---|---|
| Модель | `<дата>_Модель_<имя>.json` | Создание модели → импорт из файла |
| Сценарий | `<дата>_Сценарий_<имя>.json` | Создание сценария → импорт из файла |
| Обработчик | `<имя>.json` + `<имя>.js`/`.ts` | Импорта нет: создать, вставить код, сохранить |
| Геозона | `<дата>_Геозона_<имя>.json` | Импорт не документирован: нарисовать по координатам |

Импорт моделей, сценариев и объектов документирован Rightech; обработчики импортируются только вставкой кода, для геозон импорт в документации не описан. Источники — `references/import-guide.md`.

## Что внутри

```
rightech-plugin/
├── .claude-plugin/plugin.json     манифест Claude
├── .codex-plugin/plugin.json      манифест Codex
├── skills/                        восемь навыков; необходимые скрипты/ресурсы упакованы внутрь навыков
│   ├── rightech-research/         поиск документации до запроса материалов
│   ├── rightech-samples/          изучение образцов и вывод правил
│   ├── rightech-questions/        обязательные уточняющие вопросы
│   ├── rightech-models/           модели
│   ├── rightech-geofences/        геозоны
│   ├── rightech-handlers/         обработчики (userCode)
│   ├── rightech-scenarios/        сценарии
│   └── rightech-output/           готовые файлы и инструкция по импорту
├── references/
│   ├── samples-index.md           инвентарь 25 образцов (включая эталон шаблона модели)
│   ├── rules.md                   правила по четырём типам + противоречия
│   ├── import-guide.md            что и как импортируется
│   ├── open-questions.md          что осталось выяснить
│   ├── device-notes.md            создаётся по результатам исследования устройства
│   └── samples/primer_*           копии рабочих экспортов
├── scripts/
│   ├── validate.py                офлайн-валидатор
│   ├── make_import_file.py        сборка файла импорта и файла кода
│   └── geojson_zone.py            проверка/выбор существующего Polygon GeoJSON
└── tests/                         41 тест без сети
```

## Быстрый старт

```bash
# 1. Проверить любой экспорт или подготовленный JSON
python3 rightech-plugin/scripts/validate.py path/to/entity.json

# 2. Собрать файл для импорта (появится в rightech-output/)
python3 rightech-plugin/scripts/make_import_file.py entity.json --store models

# 3. Проверить и подготовить однозначный Polygon из GeoJSON
python3 rightech-plugin/scripts/geojson_zone.py zone.json -o rightech-zone.json
# FeatureCollection с несколькими объектами: указать целевой id или имя
python3 rightech-plugin/scripts/geojson_zone.py export.json --feature "МКАД" -o zone.geojson
```

Для своего сервера: добавьте `--origin your.rightech.host`.

## Проверки

```bash
python3 rightech-plugin/scripts/validate.py rightech-plugin/references/samples   # 25 файлов, 0 ошибок
python3 -m unittest discover -s rightech-plugin/tests                            # 41 тест
```

## Ограничения

- Валидатор и правила проверены на всех 25 образцах; 41 тест проходит.
- Сборка файла повторяет оболочку экспорта и официальных примеров импорта, но **сам импорт на живом аккаунте не проверялся**. Не подтверждено, обязательны ли поля `user` и `group`.
- Не поддержаны: круглые геозоны, узел модели `event`, полный каталог действий сценариев — нужны эталоны (см. `references/open-questions.md`).
- Перед генерацией неизвестных технических деталей плагин обязан самостоятельно искать официальную документацию Rightech и производителя через навык `rightech-research`; если достоверных материалов не найдено — попросить конкретный недостающий документ или пример.
- Сценарий ссылается на модель по `_id`; идентификатор уже созданной модели должен прийти от пользователя.

## Безопасность

- Плагин не хранит и не запрашивает токены и пароли.
- В файлы не попадают служебные поля чужого аккаунта (`_id`, `owner`, `group`, `time`).
- Всё, что уходит в аккаунт, пользователь загружает сам через интерфейс платформы.
