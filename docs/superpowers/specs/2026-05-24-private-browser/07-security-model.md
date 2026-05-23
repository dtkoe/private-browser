# 07 — Security Model

## Threat model recap

См. [01-overview-and-goals.md](./01-overview-and-goals.md). Кратко:
- Защищаем cookies/credentials профилей **at rest** (если ноутбук украден)
- Защищаем `.pbprof` файлы **in transit** (если файл утёк)
- НЕ защищаем от malware на той же машине под тем же пользователем
- НЕ защищаем от runtime-инспекции если приложение запущено

## At-rest шифрование

### Главная БД (`app.db`)

- **Технология**: SQLCipher 4 (AES-256-CBC + HMAC-SHA512)
- **Ключ**: derived из master password пользователя через **Argon2id**
- **Argon2id параметры** (рекомендация OWASP 2024):
  - `memory_kb`: 65536 (64 MiB)
  - `iterations`: 3
  - `parallelism`: 4
  - `output_length`: 32 байта (256 бит)
- **Соль**: 16 случайных байт, хранится в открытом виде в `app_settings.kdf_salt` (соль не секрет)
- **Verifier**: `Argon2id(password, salt) → key`, затем `HKDF(key, "pbprof-verifier") → verifier_bytes`. Сохраняется в `app_settings.kdf_verifier`. При unlock — проверяем что верификатор совпадает (не дешифруем всё впустую)

### Firefox profile dirs (`profiles/<uuid>/`)

- **Cookies, localStorage и т.д.** хранятся внутри Firefox-профиля. Firefox шифрует их через OS-уровневые механизмы:
  - Windows: DPAPI (через CryptProtectData) — привязан к Windows user account
- **Проблема**: если другой Windows user получит файлы — он не сможет их прочитать. Но если этот же user будет скомпрометирован — может.
- **Дополнительная мера**: при `Suspend` профиля можно zip-encrypt папку SQLCipher-derived key, разворачивать только при запуске. **Опция в v2**, не v1.

### Логи (`logs/`)

- В plaintext (для отладки)
- Не содержат секретов (пароли, прокси credentials маскируются)
- При masking:
  - URL → схема + host, query/path замаскированы
  - Proxy URL → `socks5://***:***@host:port`
  - User passwords никогда не логируются

### Backups (`backups/`)

- Auto-snapshot main БД каждые N часов (настройка)
- Снапшот — копия зашифрованной БД, доп. шифрования не требуется
- Rotation: храним последние 14 дней

## Master password — пользовательский flow

### Создание (first run)
- Required, минимум 12 символов
- Проверка на:
  - длину
  - наличие как минимум 2 типов символов (буквы + цифры или спецсимволы)
- Подсказка по созданию (но НЕ сохраняем подсказку как plaintext рядом)
- "Recovery code" — генерируем 24-слово (BIP39 mnemonic), показываем один раз, требуем подтвердить что записал. Используется как backup для derive того же key. Хранится только в голове пользователя.

### Unlock (каждый запуск)
- Окно ввода пароля
- Argon2id → key
- Проверяем verifier
- При success — открываем БД, разрешаем работу
- Brute-force protection: после 5 неуспешных попыток — задержка 30 сек, после 10 — 5 минут, после 20 — час

### Смена пароля
- Settings → "Change master password"
- Запрашиваем текущий, новый
- Re-encrypt БД через `PRAGMA rekey` (SQLCipher поддерживает)
- Re-encrypt все `.pbprof` файлы? Нет — пользователь сам решает (export заново при необходимости)

### Forgot password
- Recovery code → unlock + рекомендация поменять пароль
- Если recovery тоже потерян → **данные потеряны**. Это by design — мы не имеем backdoor.

## In-transit security (`.pbprof`)

- Каждый файл зашифрован своим паролем (НЕ master password по умолчанию — пользователь вводит при экспорте)
- Опц. "Use master password" чекбокс для удобства (но всё равно prompt подтверждение)
- AES-256-GCM с per-export уникальным nonce
- HMAC-SHA256 для integrity
- Argon2id KDF параметры записаны в manifest (для воспроизводимости при импорте на другой машине)

## Network security

### Локальный API (FastAPI)
- Bind только на `127.0.0.1` (никогда не 0.0.0.0)
- Порт 8769 (default, настраиваем)
- **Авторизация**: token-based. Token генерируется при старте backend, передаётся в frontend через query param при загрузке HTML. Frontend хранит в memory (НЕ localStorage)
- Token не персистентный, регенерируется при каждом старте app
- Это защищает от другого приложения на той же машине которое попытается дёрнуть наш API

### WebSocket
- Тот же token (auth handshake)
- Только push-events от backend к frontend (не принимает команды)

### Outbound network
- **Никакой телеметрии**. Никаких analytics. Pinpoint: запросы только когда:
  1. Camoufox auto-update check (на GitHub API, опц., пользователь может выключить)
  2. Proxy health check (от backend через сам прокси на ipinfo.io или похожий)
  3. Сам Camoufox процесс — через свой proxy, не через backend
- DNS leaks: Camoufox использует DNS через прокси (если SOCKS5) или системный (если HTTP proxy)

## Code-signing & distribution

- **MVP (v1)**: unsigned binary. Windows Defender SmartScreen покажет warning, пользователь обходит через "More info → Run anyway"
- **Цель (v2)**: EV Code-signing cert ($300-500/год от DigiCert/Sectigo) → нет warnings
- **Reproducible builds**: PyInstaller spec + NSIS script в репозитории, hash артефактов публикуем
- **Release distribution**: GitHub Releases с SHA-256 хешами в release notes
- **Auto-update**: опц., через signed update manifest from GitHub Releases. Verify сигнатуру manifest, then download + verify hash. **В v1: только notification "новая версия доступна", manual download/install**

## Sandbox / process isolation

### Camoufox процессы
- Firefox/Camoufox имеет встроенный multi-process sandboxing (e10s, fission)
- Каждый профиль = отдельный root процесс camoufox.exe → его child processes
- Между разными root процессами полная изоляция

### Backend process
- Один процесс, без elevation
- Доступ к файлам только в `%APPDATA%\private-browser\`
- Не нуждается в admin rights ни на инсталляции ни на runtime
- Camoufox запускается тоже без elevation

### Известные ограничения
- Если malware работает под тем же user account — может читать наш APPDATA, наш RAM, наши процессы. Это **общее ограничение** desktop приложений, не специфичное для нас.
- Mitigation: рекомендация пользователю — Windows Defender, не запускать админом, не открывать подозрительные .pbprof файлы от незнакомцев.

## Privacy promises

Запишем в README и Settings → About:

1. **Никакой телеметрии**. Никаких запросов на наш сервер (у нас его нет).
2. **Никаких аккаунтов**. Не нужно регистрироваться нигде чтобы пользоваться.
3. **Никакого облака**. Все данные локально.
4. **Open-source**. Каждая строка кода ревьюваема.
5. **Reproducible builds**. Артефакты можно собрать самому из репозитория.
6. **No backdoor**. Если забыл пароль и recovery code — данные потеряны.

## Аудит (audit_log таблица)

Записываем:
- Создание/изменение/удаление профилей и прокси
- Запуски и завершения сессий
- Экспорты и импорты
- Изменения настроек безопасности (master password change)
- Неудачные попытки unlock

Не записываем:
- Содержимое запросов из браузера
- Контент cookies
- Что пользователь смотрел в браузере

## Compliance / legal

- Лицензия: MIT
- Использование Camoufox: MPL 2.0 (совместимо, можем дистрибутировать вместе)
- Использование SQLCipher Community Edition: BSD license (free for open-source)
- ВАЖНО: в README указываем что наш инструмент для **законного использования** — privacy, multi-account testing, web automation. Не отвечаем за использование пользователем в нарушение ToS платформ.
