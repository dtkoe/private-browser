# 02 — Architecture

## Высокоуровневая схема

```
┌───────────────────────────────────────────────────────────────────┐
│ Pywebview / Electron shell (Windows app frame, system tray)       │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ Next.js 14 SPA (React 18 + TypeScript + Tailwind)             │ │
│ │ Layout C: sidebar (profile list) + details panel              │ │
│ │ — Profile editor — Proxy pool — Settings — Logs — Activity    │ │
│ └─────────────────────────┬─────────────────────────────────────┘ │
└───────────────────────────┼───────────────────────────────────────┘
                            │ REST + WebSocket (localhost:8769)
┌───────────────────────────▼───────────────────────────────────────┐
│ FastAPI backend (Python 3.11+, uvicorn, async)                    │
│ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐  │
│ │ ProfileService  │ │ ProxyService    │ │ FingerprintGenerator │  │
│ │ CRUD, status    │ │ pool, healthchk │ │ consistent configs   │  │
│ └─────────────────┘ └─────────────────┘ └──────────────────────┘  │
│ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐  │
│ │ LaunchManager   │ │ CamoufoxRunner  │ │ ImportExportService  │  │
│ │ pids, lifecycle │ │ subprocess+conf │ │ .pbprof zip+crypto   │  │
│ └─────────────────┘ └─────────────────┘ └──────────────────────┘  │
└───────────────────────────┬───────────────────────────────────────┘
                            │ subprocess.Popen + JSON config
┌───────────────────────────▼───────────────────────────────────────┐
│ Camoufox processes (1+ instances)                                 │
│ Каждый: свой profile dir, свой fingerprint JSON, свой proxy       │
│ Управление: Marionette protocol (для healthcheck) или JSON+stdin  │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ Storage (всё локально под %APPDATA%\private-browser\)             │
│ — app.db (SQLCipher, encrypted) — профили, прокси, сессии         │
│ — profiles/<uuid>/ — Firefox profile dirs (cookies, localStorage) │
│ — camoufox/ — скачанный Camoufox bundle                           │
│ — logs/ — локальные логи                                          │
│ — backups/ — auto-snapshot БД                                     │
└───────────────────────────────────────────────────────────────────┘
```

## Технологический стек (финальный)

### Backend
- **Язык**: Python 3.11+ (Camoufox SDK — Python)
- **Web framework**: FastAPI (async, OpenAPI auto-gen)
- **ASGI server**: uvicorn
- **БД**: SQLite через `sqlalchemy[asyncio]` + `pysqlcipher3` для шифрования
- **Миграции**: Alembic
- **Camoufox SDK**: `camoufox[geoip]` (official Python package)
- **Browser automation**: Playwright (через Camoufox; используется только для health checks и опц. автоматизации)
- **Cryptography**: `cryptography` lib для KDF и .pbprof, SQLCipher для БД
- **Async tasks**: встроенный asyncio + `apscheduler` для периодик
- **Logging**: structlog с JSON-форматом

### Frontend
- **Framework**: Next.js 14 (App Router, static export для встраивания в shell)
- **UI**: React 18 + TypeScript 5
- **Styling**: Tailwind CSS 3
- **Component lib**: shadcn/ui (Radix UI primitives)
- **State**: Zustand (профильный store) + TanStack Query (server state)
- **Forms**: react-hook-form + zod
- **Tables**: TanStack Table
- **Charts**: recharts (для будущей analytics)
- **Icons**: lucide-react

### Shell (десктопная обёртка)
- **Опция А (рекомендуется)**: [pywebview](https://pywebview.flowrl.com/) — Python обёртка вокруг native webview. Лёгкая (~10MB), та же экосистема что и backend.
- **Опция B (fallback)**: Electron, если pywebview Windows webview2 не справится с UI. Тяжелее (~100MB) но проверено.
- **Решение в M4**: начнём с pywebview, переключимся если упрёмся в Windows-специфичные проблемы

### Browser engine
- **Camoufox** prebuilt binary, скачивается launcher'ом из GitHub Releases (https://github.com/daijro/camoufox/releases или CloverLabsAI fork)
- Версия pinned в `camoufox.lock` файле
- Размер: ~150MB на Windows
- Лежит в `%APPDATA%\private-browser\camoufox\`

### Packaging
- **Python distribution**: PyInstaller для backend (single .exe ~80MB)
- **Frontend bundle**: Next.js static export, упакован в backend exe через PyInstaller add-data
- **Installer**: NSIS — Windows-native, поддержка x64, создаёт shortcuts, ассоциация `.pbprof`
- **Portable**: ZIP с теми же файлами что в installer, run-from-folder

## Поток данных — основные сценарии

### Сценарий: "создание профиля"

```
User → UI [клик "+ Новый"] → POST /api/profiles
  → FingerprintGenerator генерит consistent config
    - выбирает OS (по распределению — Win 70%, Mac 20%, Linux 10%)
    - выбирает Firefox-версию, screen, UA, languages, fonts, timezone
    - всё согласовано: timezone matches geo, fonts match OS, UA matches platform
  → ProfileService сохраняет в SQLCipher БД (status=new)
  → создаётся пустой profile dir под profiles/<uuid>/
  → возвращает {id, name, fingerprint_summary}
UI обновляет sidebar list
```

### Сценарий: "запуск профиля"

```
User → UI [клик ▶ Запустить] → POST /api/profiles/{id}/launch
  → LaunchManager.launch(profile_id):
    - читает профиль из БД
    - читает proxy_config (если есть) — проверяет alive
    - формирует Camoufox JSON config: fingerprint + proxy
    - subprocess.Popen(camoufox.exe, env=..., stdin=config)
    - регистрирует PID, маркирует profile.status = running
    - WebSocket push в UI: profile_status_changed
  → Camoufox процесс открывается с патчами применёнными к fingerprint
  → При закрытии окна процесс умирает → LaunchManager детектит
    → status = ready, записывает session row (duration, exit_ip)
    → WS push
```

### Сценарий: "экспорт профиля"

```
User → UI [клик ⋯ → Export] → POST /api/profiles/{id}/export
  → ImportExportService:
    - запрашивает пароль у user через UI prompt
    - читает fingerprint + proxy + (опц.) cookies snapshot
    - сериализует в JSON
    - encrypt(JSON, password) через AES-256-GCM с Argon2id KDF
    - zip с metadata.json + encrypted_payload.bin
  → отдаёт файл .pbprof через download link
```

## Изоляция профилей

Каждый профиль = **полностью отдельный Firefox-профиль**:

| Что изолировано | Как |
|---|---|
| Cookies, localStorage, IndexedDB | Отдельный profile dir |
| Cache, history, downloads | Отдельный profile dir |
| Extensions | Отдельный profile dir (можно ставить разный набор) |
| TLS session resumption cache | Отдельный profile dir (Firefox sessionstore) |
| WebRTC media perms | Отдельный profile dir |
| Fingerprint config | Передаётся при запуске через Camoufox JSON config |
| Proxy | Передаётся при запуске через Camoufox JSON config |
| Network | Каждый процесс — свой proxy подключение |

**Однопроцессность ≠ изоляция**: даже если два профиля запущены одновременно, это два разных процесса `camoufox.exe` с разными `--profile` и разными конфигами. Они не разделяют ничего кроме самого бинарника.

## Что НЕ делаем (явно)

- **Не патчим Camoufox** в v1. Используем как есть. Если будут проблемы — в v2 рассмотрим форк.
- **Не делаем CDP-инъекции поверх**. Camoufox уже на C++ уровне, JS-инъекции добавят детектируемые следы.
- **Не делаем встроенный proxy-провайдер**. Юзер приносит свои прокси.
- **Не делаем "human emulation"** в v1. У Camoufox есть базовое поведение мыши, этого достаточно для v1.
- **Не делаем браузер сами** в v1 — обёртка вокруг Camoufox.

## Распределение работы (компоненты)

| Компонент | Откуда берём | Что меняем |
|---|---|---|
| Camoufox engine | Prebuilt от upstream | Ничего, используем как есть |
| Профильный backend skeleton | Fork camoufox-profile-manager | Расширяем сильно |
| Frontend skeleton | Fork camoufox-profile-manager | Сильно переделываем под Layout C |
| Fingerprint generation logic | Дописываем свою (используя BrowserForge из Camoufox) | — |
| Desktop shell | pywebview (новое для проекта) | — |
| Installer | NSIS scripts (новое) | — |
| Encryption layer | sqlcipher + cryptography (новое) | — |
| Proxy pool management | Расширяем существующее | — |
| .pbprof format | Полностью новый | — |
