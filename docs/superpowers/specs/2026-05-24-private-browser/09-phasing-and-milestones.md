# 09 — Phasing and Milestones

## Принципы фазирования

- **Каждый milestone = работающий продукт** (не "почти готово, но не запускается")
- **Каждый milestone имеет acceptance criteria** — что должно работать чтобы признать M пройденным
- **На каждом M — review checkpoint**: код, тесты, документация, ручная проверка
- **Реалистичные сроки**: соло + AI, fulltime ≈ X недель; part-time ≈ 2X недель

## M0 — Setup & exploration (1 неделя)

### Задачи
- Fork [polyackiy/camoufox-profile-manager](https://github.com/polyackiy/camoufox-profile-manager) → `private-browser` repo
- Поставить dev env: Python 3.11, Node 20, Camoufox prebuilt
- Запустить upstream as-is — убедиться что профили создаются и Camoufox запускается
- Изучить Camoufox JSON config через ручные эксперименты
- Прочитать issues и PRs в upstream чтобы понять активность
- Создать `dev-machine-setup.md` для воспроизводимой среды
- Настроить git workflow + CI skeleton (GitHub Actions)

### Acceptance
- Из `git clone` до запуска приложения локально — ≤ 15 минут
- Создан 1 профиль через UI, запущен Camoufox, открыта browserleaks.com
- В CI зелёные lints + минимальный unit test

## M1 — Foundation: rebrand + новая архитектура (3 недели)

### Задачи
- Rebrand: имя пакета, README, иконки, цвета, branding
- Заменить SQLite на SQLCipher с master password unlock flow
- Argon2id KDF + verifier
- Master password setup wizard
- Структура папок под наш scope (отделить future modules)
- Базовый структурированный логинг (structlog)
- Audit log таблица
- API token auth (random per-startup)
- Alembic миграции с нашей initial migration

### Acceptance
- При запуске — login screen, нельзя продолжить без правильного пароля
- БД на диске — реально зашифрована (проверяем strings/hex viewer)
- 5+ unit tests на security primitives зелёные
- Старые upstream-фичи продолжают работать (CRUD профилей)

### Review checkpoint
- Code review: security модуль особенно внимательно (KDF, ключи, шифрование)
- Threat model assessment: что атакующий может сделать с украденным app.db без пароля? Должен быть unable to read.

## M2 — FingerprintGenerator + новый профильный API (3 недели)

### Задачи
- Модуль `fingerprint_generator.py`:
  - Datasets: OS distributions, screen resolutions per OS, WebGL renderers per OS, fonts lists per OS
  - Generator: produces consistent CamoufoxConfig
  - Validator: проверяет существующий config на consistency
- Расширенная схема `profile` table (все поля из [05](./05-profile-model.md))
- API endpoints:
  - `POST /api/profiles` — с auto-generation
  - `PATCH /api/profiles/{id}/fingerprint` — частичное обновление с пересчётом
  - `POST /api/profiles/{id}/regenerate` — full re-generation
  - `POST /api/fingerprint/validate` — standalone валидация
- Прокидывание fingerprint config в Camoufox через `launch_options`

### Acceptance
- Создаю 10 профилей через `/api/profiles` без параметров → каждый имеет уникальный, консистентный config
- Запуск этих 10 профилей → CreepJS показывает 10 уникальных hash
- Pixelscan consistency check ✅ для каждого
- Unit tests: 20+ на FingerprintGenerator (правила консистентности)

### Review checkpoint
- Manual run: 10 профилей × 5 эталонных сайтов = 50 ручных проверок (либо автоматизировать в этом M)
- Code review FingerprintGenerator — самая критичная логика

## M3 — Proxy management + WebRTC (2 недели)

### Задачи
- ProxyPool сервис:
  - CRUD прокси
  - Validation формата (HTTP/SOCKS5)
  - Health check через HTTP запрос на ipinfo.io → возвращает IP/geo
  - Background scheduler — auto-check каждые N минут
  - Batch import из текста/CSV
- Связь profile ↔ proxy (FK)
- При запуске профиля — pre-flight check прокси
- Geo-based fingerprint adjustment: при назначении прокси с другой geo — предложение re-generate timezone/locale
- WebRTC mode: автоматически "proxy" если proxy назначен
- WebRTC leak test integrated (после запуска показываем "ваш IP в WebRTC: X")

### Acceptance
- 5 разных прокси → 5 разных видимых IP (на ipinfo.io check)
- Запуск профиля с прокси → utls.peet.ws показывает IP прокси
- WebRTC leak test https://browserleaks.com/webrtc → ZERO утечки реального IP
- Тест: запустил профиль без прокси с настройкой WebRTC=proxy → не должен запускаться или показать warning

### Review checkpoint
- Smoke test: один и тот же профиль через 3 разных прокси (US/DE/JP) — все должны работать без ре-генерации остального fingerprint, только timezone/locale meняется

## M4 — UI replacement (Layout C) (4 недели)

### Задачи
- Полная переделка frontend под [06-ui-design.md](./06-ui-design.md):
  - Next.js 14 App Router setup
  - Tailwind + shadcn/ui
  - Dark theme основная
  - Sidebar component (с виртуализацией для 1000+ профилей)
  - Profile detail panel
  - Profile editor (Sheet with tabs)
  - Proxy pool table (TanStack Table)
  - Settings screen
  - First-run wizard
  - i18n (ru + en) через next-intl
  - Command palette (Ctrl+K) — fuzzy search
  - Hotkeys system
  - Toast notifications (sonner)
  - WebSocket auto-reconnect
- pywebview shell:
  - Launches FastAPI backend как subprocess
  - Open native window pointing to localhost
  - System tray icon
  - Single-instance lock (нельзя запустить два экземпляра)
  - Auto-shutdown backend on window close

### Acceptance
- Все экраны соответствуют макетам в [06](./06-ui-design.md)
- Frontend e2e тесты Playwright проходят
- При 1000 профилей в БД UI остаётся responsive (< 100ms list render)
- Все hotkeys работают
- Lang switch ru↔en на лету

### Review checkpoint
- UX review: пользователь не из dev команды проходит first-run wizard → создаёт профиль → запускает. Не более 5 минут.
- Accessibility audit (axe-core scan)

## M5 — Export/Import + extensions + polish (3 недели)

### Задачи
- `.pbprof` формат — encrypt/decrypt/sign/verify
- Export UI (с password prompt, опц. browser data, опц. extensions)
- Import UI (drag-drop, file association)
- Регистрация `.pbprof` ассоциации при NSIS install
- Firefox extensions management:
  - Список установленных в профиле (через чтение `extensions.json` из profile dir)
  - Add через `.xpi` upload или ссылка на AMO
  - Remove
- Profile cloning (быстрый дубль с новым UUID, опц. без cookies)
- Bulk actions: select multiple → bulk delete / bulk export / bulk launch
- Recovery code generation
- Activity / Logs viewer
- Polish: empty states, loading states, error boundaries, tooltips

### Acceptance
- Round-trip: export → удалить профиль → import → профиль работает с теми же cookies
- Расширение `.pbprof` ассоциировано в Windows: двойной клик → открывается наше приложение
- Установка uBlock Origin в один профиль → отсутствует в другом
- 10 профилей выбрано → bulk launch → 10 окон Camoufox запущено

### Review checkpoint
- Security review export/import — проверка integrity, signature verification, error handling

## M6 — Distribution + first release (2 недели)

### Задачи
- PyInstaller config для standalone .exe
- NSIS installer script:
  - Прогресс установки
  - Создание Start Menu и Desktop shortcuts
  - Регистрация `.pbprof` association
  - Uninstall с опц. сохранения данных
- Portable ZIP build (без installer)
- Camoufox auto-download на first run (progress UI)
- Auto-update checker (notification only в v1)
- Документация:
  - README.md (полный)
  - User guide (markdown + рендеринг в Settings → Help)
  - Troubleshooting guide
  - Contributing guide
- Release: v0.1.0 на GitHub Releases с SHA-256 хешами
- Опубликовать README на сайте проекта (GitHub Pages — простой Jekyll)

### Acceptance
- На чистой Windows 10/11 VM installer работает без admin
- Portable ZIP запускается на USB-флешке без установки
- Self-test passes на чистой машине
- GitHub Release с подписанным (на этом этапе sha256 hash) бинарником

### Review checkpoint
- Final security review: распакованный .exe — что внутри? Не утекают ли test fixtures, ключи, секреты?
- Final scope review: всё что обещали в [01](./01-overview-and-goals.md) goals — реально работает?

## После v1 — sustainable maintenance

### Регулярные задачи (forever)
- **Каждые 4 недели**: pull новых релизов Camoufox, тест совместимости, bump pinned version, regression тесты, release v0.x.y
- **Каждые 4 недели**: проверка upstream camoufox-profile-manager — cherry-pick полезного
- **Каждый раз когда CreepJS обновляется**: regression тест что наши fingerprint всё ещё уникальны и passes lies-detection

### v1.1+ (опц., в зависимости от feedback)
- macOS / Linux port
- ML-based behavior emulation (мышь, клавиатура, тайминги)
- Encrypted profile suspend (zip-with-key для архивных профилей)
- Self-hosted sync (Docker + sqlite-replication)
- Профили "warming" (предзагрузка естественной activity)
- Improved cookies import из Chrome/Firefox/Edge

## Резюме сроков (соло + AI, fulltime)

| Milestone | Длительность | Cumulative |
|---|---|---|
| M0 | 1 нед | 1 нед |
| M1 | 3 нед | 4 нед |
| M2 | 3 нед | 7 нед |
| M3 | 2 нед | 9 нед |
| M4 | 4 нед | 13 нед |
| M5 | 3 нед | 16 нед |
| M6 | 2 нед | **18 нед ≈ 4.5 месяца** |

**Part-time (10-15 ч/нед)**: умножь на 2.5-3 → ~12 месяцев до v1.

**Это реалистично только если** Camoufox продолжает работать (а это под вопросом, см. [10](./10-risks-and-mitigations.md)). При major breakage сроки удлиняются.
