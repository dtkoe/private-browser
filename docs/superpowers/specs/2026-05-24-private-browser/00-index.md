# Private Browser — Design Spec

**Версия:** 0.1 (draft)
**Дата:** 2026-05-24
**Статус:** в ревью

## TL;DR

Анти-детект браузер для Windows на базе **Camoufox** (open-source Firefox-fork с нативным fingerprint-spoofing на уровне C++). Форкаем существующий проект [camoufox-profile-manager](https://github.com/polyackiy/camoufox-profile-manager) как стартовую точку (FastAPI бэкенд + Next.js фронтенд) и существенно расширяем под требования. Цель — open-source альтернатива Multilogin/AdsPower/GoLogin/Dolphin Anty.

## Ключевые архитектурные решения

| Решение | Выбор | Файл |
|---|---|---|
| Use case | Мульти-аккаунт анти-детект | [01](./01-overview-and-goals.md) |
| Браузерный движок | Camoufox (Firefox-fork) | [02](./02-architecture.md) |
| Стартовая база | Fork polyackiy/camoufox-profile-manager | [04](./04-fork-strategy.md) |
| Бэкенд | Python 3.11+ / FastAPI / SQLite (+SQLCipher) | [02](./02-architecture.md) |
| Фронтенд | Next.js 14 + React 18 + TypeScript | [02](./02-architecture.md) |
| UI паттерн | Layout C — sidebar + details panel | [06](./06-ui-design.md) |
| Профили — синхронизация | Локальные + `.pbprof` export/import | [05](./05-profile-model.md) |
| Расширения | Полная поддержка Firefox addons | [02](./02-architecture.md) |
| Сеть | Общий VPN + per-profile proxy (опционально) | [05](./05-profile-model.md) |
| Шифрование данных | SQLCipher (Argon2id KDF) | [07](./07-security-model.md) |
| Distribution | Windows NSIS installer + portable ZIP | [02](./02-architecture.md) |

## Структура документа

1. **[01 — Overview and Goals](./01-overview-and-goals.md)** — что строим, чего НЕ строим, threat model
2. **[02 — Architecture](./02-architecture.md)** — компоненты, поток данных, технологический стек
3. **[03 — Fingerprint Vectors](./03-fingerprint-vectors.md)** — что подделываем, где это делает Camoufox, что добавляем сами
4. **[04 — Fork Strategy](./04-fork-strategy.md)** — как форкаем, что меняем, как мерджим upstream
5. **[05 — Profile Model](./05-profile-model.md)** — схема БД, формат экспорта, lifecycle профиля
6. **[06 — UI Design](./06-ui-design.md)** — Layout C детально, экраны, флоу
7. **[07 — Security Model](./07-security-model.md)** — шифрование at-rest, KDF, sandbox, нет-телеметрии
8. **[08 — Testing Strategy](./08-testing-strategy.md)** — unit, integration, fingerprint detection acceptance tests
9. **[09 — Phasing and Milestones](./09-phasing-and-milestones.md)** — M1-M6 с deliverables
10. **[10 — Risks and Mitigations](./10-risks-and-mitigations.md)** — Camoufox-зависимость, Firefox-base, anti-detect arms race

## Глоссарий

- **Анти-детект** — техника создания множественных изолированных браузерных сессий, которые сторонние сервисы не могут связать между собой
- **Fingerprint** — совокупность параметров браузера/устройства, по которой сервис идентифицирует пользователя (Canvas hash, WebGL renderer, TLS JA3, шрифты и т.д.)
- **JA3/JA4** — хеш параметров TLS ClientHello, уникальный для каждого браузера/версии
- **CDP** — Chrome DevTools Protocol, протокол управления Chromium-браузерами
- **Marionette** — Firefox-аналог CDP, используется Playwright для управления Firefox
- **Camoufox** — Firefox-fork с патчами анти-детект на C++ уровне
- **Profile (наш контекст)** — изолированная идентичность: свой fingerprint, свой proxy, свой user-data-dir
- **`.pbprof`** — наш формат экспорта профиля (zip с зашифрованным JSON)
