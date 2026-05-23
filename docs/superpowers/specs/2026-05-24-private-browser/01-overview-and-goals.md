# 01 — Overview and Goals

## Что строим

Десктопное Windows-приложение, которое позволяет пользователю создавать и одновременно запускать **множество изолированных браузерных профилей**, каждый из которых для внешних сервисов выглядит как уникальное устройство и пользователь. Сервисы не могут связать профили между собой через fingerprint.

Архитектурно: GUI-обёртка (Next.js+React) поверх backend (FastAPI) который оркестрирует процессы **Camoufox** — Firefox-fork с нативным fingerprint spoofing на уровне C++.

## Цели (v1)

1. **Профили**: создавать, редактировать, клонировать, удалять, экспортировать/импортировать
2. **Fingerprint per profile**: все векторы которые покрывает Camoufox (см. [03](./03-fingerprint-vectors.md))
3. **Proxy per profile**: HTTP, HTTPS, SOCKS5 с auth; проверка живости; geo-detection
4. **Multi-launch**: одновременно открыто N профилей в отдельных окнах Camoufox
5. **Storage isolation**: каждый профиль = отдельный Firefox profile dir, cookies/localStorage/IndexedDB не пересекаются
6. **Extensions**: пользователь может ставить Firefox addons (с Mozilla AMO) в каждый профиль независимо. **Важно**: поскольку база Firefox-fork, Chrome Web Store расширения **не поддерживаются напрямую**. Большинство популярных (uBlock Origin, Bitwarden, Dark Reader, NoScript, KeePassXC и т.д.) есть в обоих сторах. Chrome-only расширения (некоторые Google-tools, специфичные dev-tools) работать не будут — это сознательный trade-off архитектуры Firefox-base
7. **UI**: Layout C (sidebar + details), русский + английский, тёмная тема
8. **Безопасность**: БД зашифрована (SQLCipher), нет телеметрии, нет облака
9. **Distribution**: Windows installer (NSIS) и portable ZIP. Single-click setup, Camoufox скачивается при первом запуске

## Non-goals (v1)

1. ❌ macOS / Linux версии (только Windows; портирование позже)
2. ❌ Облачная синхронизация профилей (только локальный export/import .pbprof)
3. ❌ Билд Camoufox из исходников пользователем (используем prebuilt от daijro/CloverLabsAI)
4. ❌ Встроенный VPN / прокси-провайдер (пользователь приносит свои)
5. ❌ Командная работа / шаринг профилей между пользователями
6. ❌ Биллинг / лицензирование / закрытый исходник
7. ❌ Мобильная версия
8. ❌ Свои патчи Chromium (если Camoufox чего-то не покрывает — лучше форк Camoufox)
9. ❌ ML-driven behavior simulation (мышь, тайминги) — Camoufox имеет базовое, расширять в v2+
10. ❌ Захардкоженные платные интеграции (резидентные прокси через нас)

## Threat model

**Кого мы защищаем**: индивидуального пользователя и его аккаунты от сервисов которые применяют fingerprint-based linking — рекламные сети, маркетплейсы, соц-сети, сервисы автоматической верификации аккаунтов.

**От кого защищаем**:

| Уровень | Примеры | Покрываем? |
|---|---|---|
| L1 — Базовые трекеры (Google Analytics, FB Pixel) | Cookie + UA tracking | ✅ Полностью |
| L2 — Fingerprinting libs (FingerprintJS, ThumbmarkJS) | Canvas+WebGL+Audio+Fonts hash | ✅ Camoufox покрывает |
| L3 — Anti-bot сервисы | Cloudflare Bot Mgmt, DataDome, PerimeterX, Akamai | ⚠️ Частично (TLS/HTTP покрываем, behavior — слабее) |
| L4 — Корпоративный fraud-detection | Stripe Radar, банковский анти-фрод | ⚠️ Зависит от глубины. Не гарантируем |
| L5 — Государственный уровень | Корреляция через ISP, time-based анализ | ❌ Не наша область — нужен Tor/mix-network |

**Кого мы НЕ защищаем**:
- Пользователя от malware если он сам скачал и запустил
- Пользователя от деанонимизации через свой контент (логин, email, паттерн поведения)
- От сетевого провайдера если не используется VPN/прокси
- От самого Camoufox/Firefox если в них найдут уязвимость (мы лишь обёртка)

## Success criteria

**Браузер считаем успешным если**:

1. Запускаем 10 профилей одновременно, каждый имеет уникальный hash на:
   - [CreepJS](https://abrahamjuliot.github.io/creepjs/) — каждый профиль уникальный fingerprint
   - [BrowserLeaks](https://browserleaks.com/) — все основные тесты показывают спуфнутые значения
   - [Pixelscan](https://pixelscan.net/) — consistency check проходит (UA matches platform matches Client Hints)
   - [bot.sannysoft.com](https://bot.sannysoft.com/) — все проверки зелёные
   - [tls.peet.ws/api/all](https://tls.peet.ws/api/all) — JA3 fingerprint уникальный, не похож на curl/headless
2. Профили в течение 7 дней использования не объединены сервисами в один аккаунт-профиль (manual test)
3. Cookies/sessions сохраняются между запусками профиля
4. Создание нового профиля занимает < 5 секунд
5. Запуск профиля занимает < 10 секунд
6. UI отзывчив при 100+ профилях в списке
7. Утечка реального IP в WebRTC = 0% (проверяется автоматически)
8. Бинарь приложения после установки занимает < 300MB (без Camoufox) / < 500MB (с Camoufox)
9. Установлен и запущен пользователь без технических знаний за < 5 минут (UX test)

## Принципы

1. **Privacy-first**: ни одной телеметрической точки, ни одного запроса наружу без явной команды пользователя
2. **Local-first**: всё локально, никаких облаков, никаких учёток у нас
3. **Open-source**: лицензия MIT (как camoufox-profile-manager). Полная воспроизводимая сборка
4. **No vendor lock-in**: пользователь может в любой момент экспортировать профили и уйти
5. **Honest about limits**: явно говорим что обходим и что НЕ обходим
6. **Sustainable maintenance**: архитектура должна выживать перерывы в апстриме Camoufox
