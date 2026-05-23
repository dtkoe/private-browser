# 05 — Profile Model

## Схема БД (SQLCipher)

```sql
-- Профиль = идентичность пользователя в сети
CREATE TABLE profile (
    id            TEXT PRIMARY KEY,          -- UUID v4
    name          TEXT NOT NULL,
    notes         TEXT,                       -- свободные заметки
    tags          TEXT NOT NULL DEFAULT '[]', -- JSON array строк
    color         TEXT,                       -- HEX для avatar
    created_at    INTEGER NOT NULL,           -- unix ms
    updated_at    INTEGER NOT NULL,
    last_opened_at INTEGER,
    open_count    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL,              -- new | ready | running | suspended | error
    
    -- fingerprint config (передаётся в Camoufox)
    fingerprint   BLOB NOT NULL,              -- JSON: см. ниже
    
    -- proxy
    proxy_id      TEXT,                       -- FK на proxy.id (nullable)
    
    -- storage
    user_data_dir TEXT NOT NULL,              -- абсолютный путь под APPDATA
    
    -- метаданные сессий
    total_sessions      INTEGER NOT NULL DEFAULT 0,
    total_duration_sec  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_profile_status ON profile(status);
CREATE INDEX idx_profile_last_opened ON profile(last_opened_at DESC);

-- Прокси (пул отдельный от профилей чтобы прокси можно было переиспользовать)
CREATE TABLE proxy (
    id              TEXT PRIMARY KEY,         -- UUID
    label           TEXT NOT NULL,            -- человекочитаемое имя
    type            TEXT NOT NULL,            -- http | https | socks5
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL,
    username        TEXT,
    password        TEXT,
    
    -- автодетект
    last_checked_at INTEGER,
    last_check_ok   INTEGER NOT NULL DEFAULT 0, -- 0/1 boolean
    last_ip         TEXT,                       -- IP который видит исход
    last_country    TEXT,                       -- ISO 3166-1 alpha-2
    last_city       TEXT,
    last_timezone   TEXT,
    last_latency_ms INTEGER,
    
    -- метаданные
    tags            TEXT NOT NULL DEFAULT '[]', -- JSON array
    notes           TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE INDEX idx_proxy_last_check ON proxy(last_checked_at DESC);

-- Сессии (запуски профилей)
CREATE TABLE session (
    id              TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    started_at      INTEGER NOT NULL,
    ended_at        INTEGER,
    duration_sec    INTEGER,
    pid             INTEGER,
    exit_code       INTEGER,
    proxy_id        TEXT REFERENCES proxy(id) ON DELETE SET NULL,
    exit_ip         TEXT,
    user_agent      TEXT,
    error           TEXT
);
CREATE INDEX idx_session_profile ON session(profile_id, started_at DESC);

-- Аудит для безопасности
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    actor       TEXT NOT NULL,         -- "user" | "system"
    action      TEXT NOT NULL,         -- e.g. "profile.create", "proxy.delete"
    target_type TEXT,                  -- "profile" | "proxy" | ...
    target_id   TEXT,
    details     TEXT                   -- JSON, опц.
);
CREATE INDEX idx_audit_ts ON audit_log(ts DESC);

-- Настройки приложения (single row)
CREATE TABLE app_settings (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    theme               TEXT NOT NULL DEFAULT 'dark',
    language            TEXT NOT NULL DEFAULT 'ru',
    camoufox_version    TEXT,                  -- pinned версия
    auto_update_check   INTEGER NOT NULL DEFAULT 1,
    api_port            INTEGER NOT NULL DEFAULT 8769,
    
    -- глобальные настройки прокси
    default_vpn_active  INTEGER NOT NULL DEFAULT 0,
    
    -- master key derivation params (для верификации пароля)
    kdf_salt            BLOB NOT NULL,
    kdf_verifier        BLOB NOT NULL          -- hash(key || "verifier")
);
```

## JSON-структура `fingerprint` (BLOB в БД)

Соответствует Camoufox config format. Версионирована для миграций.

```json
{
  "schema_version": 1,
  "generated_at": 1716508800000,
  "generator_version": "0.1.0",
  
  "os": {
    "type": "windows",
    "version": "11"
  },
  
  "browser": {
    "name": "firefox",
    "version": "142.0"
  },
  
  "navigator": {
    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
    "platform": "Win32",
    "oscpu": "Windows NT 10.0; Win64; x64",
    "language": "en-US",
    "languages": ["en-US", "en"],
    "hardwareConcurrency": 8,
    "deviceMemory": 8,
    "maxTouchPoints": 0
  },
  
  "screen": {
    "width": 1920,
    "height": 1080,
    "availWidth": 1920,
    "availHeight": 1040,
    "colorDepth": 24,
    "pixelDepth": 24
  },
  
  "window": {
    "innerWidth": 1280,
    "innerHeight": 720,
    "outerWidth": 1280,
    "outerHeight": 800,
    "devicePixelRatio": 1.0
  },
  
  "webGl": {
    "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "vendor": "Google Inc. (Intel)",
    "extensions": ["EXT_color_buffer_float", "EXT_texture_compression_rgtc", "..."],
    "parameters": {
      "MAX_TEXTURE_SIZE": 16384,
      "MAX_VERTEX_ATTRIBS": 16,
      "...": "..."
    }
  },
  
  "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "..."],
  
  "timezone": "America/New_York",
  "locale": "en-US",
  
  "geolocation": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "accuracy": 100
  },
  
  "webrtc": {
    "mode": "proxy",
    "publicIp": null,
    "localIpv4": "192.168.1.42",
    "localIpv6": null
  },
  
  "mediaDevices": {
    "micros": 1,
    "webcams": 1,
    "speakers": 2
  },
  
  "battery": {
    "charging": true,
    "level": 0.87
  },
  
  "seeds": {
    "canvas": "0x4a3f8e1b",
    "audio": "0x7c2d5f90",
    "webgl_noise": "0x1a8c3e72"
  }
}
```

## Lifecycle профиля

```
[создан]
   │ user clicks "+ Новый"
   ▼
[draft] — FingerprintGenerator создал config, БД сохранил, user_data_dir пустой
   │ user clicks "Запустить"
   ▼
[starting] — Camoufox процесс запускается
   │ процесс открылся
   ▼
[running] — Camoufox активен, profile.status = running, лежит в registry LaunchManager
   │ user закрыл окно ИЛИ user clicks "Остановить"
   ▼
[ready] — процесс умер, статистика сессии записана, готов к новому запуску
   │ опц. user clicks "Suspend"
   ▼
[suspended] — нельзя запустить пока не Reactivate (для архивных профилей)
```

**Ошибочные переходы**:
- Любое → [error] если launch failed (Camoufox не нашёлся, proxy dead, и т.д.)
- [running] → [ready] forced если процесс крашнулся (heartbeat не отвечает)

## `.pbprof` — формат экспорта

ZIP-архив с расширением `.pbprof`. Расширение ассоциировано с приложением в Windows registry (при установке).

### Структура

```
profile-Account_01.pbprof  (zip)
├── manifest.json          # metadata, незашифровано
├── payload.enc            # encrypted blob (AES-256-GCM)
└── signature.bin          # HMAC-SHA256(payload.enc, derived_key) — для integrity
```

### manifest.json (plaintext)

```json
{
  "format": "pbprof",
  "format_version": 1,
  "created_at": 1716508800000,
  "creator_version": "0.1.0",
  "profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "profile_name": "Account_01",
  "encryption": {
    "kdf": "argon2id",
    "kdf_salt": "base64==",
    "kdf_params": {
      "memory_kb": 65536,
      "iterations": 3,
      "parallelism": 4
    },
    "cipher": "aes-256-gcm",
    "nonce": "base64=="
  },
  "include_browser_data": true,
  "include_extensions": false,
  "size_bytes_encrypted": 12345678
}
```

### payload.enc (encrypted)

Содержит зашифрованный JSON:

```json
{
  "profile": { /* вся строка из profile таблицы */ },
  "proxy": { /* связанный proxy или null */ },
  "browser_data": {
    "cookies": "...",         /* зашифрованный SQLite cookies.sqlite Firefox */
    "localStorage": "...",
    "indexedDB_metadata": "...",
    "preferences": "..."
  },
  "extensions": [             /* опционально */
    {"id": "uBlock0@raymondhill.net", "name": "uBlock Origin", "version": "1.55.0", "data": "base64..."}
  ]
}
```

### Process: Export

1. User → UI [⋯ → Export]
2. Modal: пароль (с подтверждением), флаги (`include_browser_data`, `include_extensions`)
3. Backend:
   - Argon2id(password, salt) → derived_key
   - Сериализуем profile + proxy + (опц.) cookies.sqlite + ext data → JSON
   - AES-256-GCM(JSON, derived_key, nonce) → encrypted
   - HMAC-SHA256(encrypted, derived_key) → signature
   - Собираем zip → отдаём как download

### Process: Import

1. User → UI [Import] / drag-drop файла / ассоциация ОС
2. Modal: пароль
3. Backend:
   - Читает manifest
   - Argon2id(password, kdf_salt из manifest, params из manifest) → derived_key
   - Проверяет signature.bin
   - Расшифровывает payload
   - Создаёт новый профиль с new UUID (избегаем коллизий)
   - Копирует cookies.sqlite в новый user_data_dir
   - (Опц.) ставит extensions

### Security threat для `.pbprof`

- Если файл утёк без пароля — атакующему нужно перебирать Argon2id (memory_kb=64MB, iter=3) → дорого
- Файл подписан HMAC → tampering детектится
- Расширение ассоциировано с приложением → при двойном клике пользователь видит наше UI, не случайное открытие

## Файловая система — расположение

```
%APPDATA%\private-browser\
├── app.db                         # SQLCipher encrypted
├── app.db-shm
├── app.db-wal
├── camoufox\
│   ├── camoufox.exe
│   └── ... (Firefox files)
├── profiles\
│   ├── 550e8400-e29b-.../        # Firefox profile dir #1
│   │   ├── prefs.js
│   │   ├── cookies.sqlite
│   │   ├── places.sqlite
│   │   └── ...
│   └── 660f9511-...               # profile dir #2
├── logs\
│   ├── app.log
│   ├── launch.log
│   └── audit.log
├── backups\                       # auto-rotated SQLCipher backups
│   ├── app-2026-05-24.db
│   └── app-2026-05-23.db
└── temp\                          # для .pbprof export/import staging
```
