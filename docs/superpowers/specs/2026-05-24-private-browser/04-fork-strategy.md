# 04 — Fork Strategy

## Что форкаем

[polyackiy/camoufox-profile-manager](https://github.com/polyackiy/camoufox-profile-manager) — open-source профильный менеджер для Camoufox.

- Лицензия: MIT (совместимо)
- Стек: Python/FastAPI бэк + Next.js фронт
- Состояние: ранняя стадия (11 commits, "in active development, not production-ready")
- Звёзд: 26
- Архитектура: уже соответствует тому что нам нужно

## Что в апстриме хорошо (берём как есть)

- Базовая структура папок (`backend/`, `frontend/`, `core/`, `database/`, `docs/`)
- Базовая SQLite модель профилей (расширим)
- FastAPI скелет
- Next.js скелет

## Что нужно расширить (наш scope)

| # | Область | Объём работы | Файлы |
|---|---|---|---|
| 1 | **SQLCipher** вместо plain SQLite | Малый | `database/`, `core/config.py` |
| 2 | **Layout C UI** (sidebar + details) полностью | Большой | `frontend/src/` весь |
| 3 | **FingerprintGenerator** (consistent configs) | Большой | новый `backend/services/fingerprint_generator.py` |
| 4 | **ProxyPool** с проверкой живости и geo-detection | Средний | расширение |
| 5 | **LaunchManager** с lifecycle + WebSocket updates | Средний | расширение |
| 6 | **`.pbprof` export/import format** | Средний | новый `backend/services/pbprof.py` |
| 7 | **pywebview shell** (desktop wrapper) | Малый | новый `shell/main.py` |
| 8 | **PyInstaller build** | Средний | новый `build/` |
| 9 | **NSIS installer** | Малый | новый `installer/` |
| 10 | **Camoufox auto-download** (первый запуск) | Малый | новый `backend/services/camoufox_downloader.py` |
| 11 | **i18n (ru + en)** | Малый | `frontend/i18n/` |
| 12 | **Logging + audit trail** | Малый | расширение |
| 13 | **Master password + KDF** | Средний | `backend/core/security.py` (новый) |

## Как форкаем — процесс

### Шаг 1. Подготовка
```bash
# на машине разработки
gh repo fork polyackiy/camoufox-profile-manager --clone --remote
cd camoufox-profile-manager
git remote rename origin upstream
gh repo create private-browser --source=. --remote=origin --public
git push -u origin main
```

### Шаг 2. Rebrand
- Меняем имя пакета в `pyproject.toml` / `package.json` → `private-browser`
- Меняем README.md полностью (свой проект)
- Сохраняем атрибуцию: `BASED_ON.md` указывает что это форк, благодарность авторам
- LICENSE остаётся MIT с двойным копирайтом

### Шаг 3. Сохраняем связь с upstream
```bash
git remote add upstream https://github.com/polyackiy/camoufox-profile-manager.git
git fetch upstream
```

Регулярно (раз в 2-4 недели):
```bash
git fetch upstream
git log --oneline HEAD..upstream/main  # смотрим что нового
git cherry-pick <конкретные commits>  # выборочный merge полезного
```

Не делаем blind `git merge upstream/main` потому что наш фронт разойдётся с их сильно. Cherry-pick — основной режим.

### Шаг 4. Branch model
- `main` — production-ready (после релизов)
- `develop` — основная dev-ветка
- `feat/*` — фичи
- `fix/*` — баги
- `release/v*` — стабилизация перед релизом

### Шаг 5. Архитектура совместимости с upstream
Чтобы максимизировать пользу от upstream-обновлений:

- **Бэкенд**: придерживаемся той же структуры папок что в upstream (`backend/api/`, `backend/core/`, etc.). Наши новые модули вписываем в существующие папки, не создаём параллельные.
- **БД миграции**: используем Alembic с новой initial migration (наша) — НЕ пытаемся merge их migration history
- **Фронтенд**: переписываем сильно, но если они добавляют новые API endpoints — мы добавляем UI к ним
- **Camoufox SDK calls**: оборачиваем в свой adapter (`backend/services/camoufox_adapter.py`) чтобы upstream-изменения в их вызовах не ломали наш код

## Риски форка

### Риск 1: upstream заглохнет
**Mitigation**: мы и так делаем большую часть работы сами. Если polyackiy остановит проект — мы продолжаем, теряя только потенциальные будущие улучшения.

### Риск 2: upstream сделает breaking changes
**Mitigation**: cherry-pick подход вместо merge. Мы контролируем что берём.

### Риск 3: лицензионные вопросы
**Mitigation**: MIT — самая liberal лицензия. Атрибуция в BASED_ON.md и LICENSE.

### Риск 4: identity confusion (нас путают с upstream)
**Mitigation**: своё имя, свой бренд, чёткое позиционирование в README.

## Альтернатива если фрик не пойдёт

Если за M1 окажется что upstream slishком сырой/идёт в разные стороны:
- **Plan B**: оставляем себе только архитектурные идеи (стек), пишем backend и frontend с нуля. Camoufox SDK всё равно используем напрямую — это main dependency, не upstream.
- Время потерь: ~1-2 недели (не критично).
