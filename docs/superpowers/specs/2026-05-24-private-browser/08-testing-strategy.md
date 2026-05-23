# 08 — Testing Strategy

## Уровни тестирования

### 1. Unit tests
- **Backend**: pytest + pytest-asyncio
- **Frontend**: Vitest + React Testing Library
- **Покрытие цель**: 70%+ для core (services, models), 50%+ для UI

### 2. Integration tests
- **Backend**: pytest с реальной in-memory SQLCipher + mocked Camoufox subprocess
- **API**: pytest с FastAPI TestClient

### 3. End-to-end tests
- **UI**: Playwright на нашем pywebview-приложении (frontend через HTTP к локальному backend)
- **Browser launch**: реальный запуск Camoufox с заглушенным fingerprint, проверка процесса

### 4. Fingerprint acceptance tests
Самый важный уровень — проверяем что fingerprint **реально работает**.

## Fingerprint Acceptance Tests

### Подход
Автоматизированный набор который:
1. Запускает N профилей с known fingerprint configs
2. Через Playwright (Marionette protocol) открывает эталонные сайты
3. Парсит результаты со страниц
4. Сравнивает с ожидаемыми значениями
5. Проверяет уникальность между профилями

### Эталонные сайты

| Сайт | Что проверяем | Pass criteria |
|---|---|---|
| **https://abrahamjuliot.github.io/creepjs/** | Главный fingerprint hash, его компоненты (Canvas/WebGL/Audio/etc) | 10 профилей → 10 уникальных hash. Каждый компонент в "lies" должен быть 0 |
| **https://browserleaks.com/** | Каждый отдельный тест (Canvas, WebGL, Fonts, WebRTC, Geolocation, etc) | Spoofed значения совпадают с config профиля |
| **https://pixelscan.net/** | Consistency check (UA matches Platform matches Client Hints matches Fonts) | "Your fingerprint is consistent" зелёная галочка |
| **https://bot.sannysoft.com/** | Headless/automation детекция | Все строки зелёные ("passed") |
| **https://tls.peet.ws/api/all** | TLS JA3, JA4, HTTP/2 fingerprint | JA3 совпадает с известными Firefox JA3, не похож на curl/headless |
| **https://amiunique.org/** | Общая уникальность | "Yes, you are unique" — но каждый профиль unique по-разному |
| **https://fingerprintjs.com/demo/** | Visitor ID stability | 10 профилей → 10 разных visitor ID. Тот же профиль на повторном запуске → тот же ID |

### Структура теста (pseudo-code)

```python
# tests/fingerprint/test_acceptance.py

@pytest.fixture
def ten_profiles(app):
    """Создаёт 10 профилей с разными случайными configs"""
    profiles = []
    for i in range(10):
        cfg = generate_fingerprint(target_os=random.choice(["windows", "macos", "linux"]))
        p = app.profile_service.create(name=f"test_{i}", fingerprint=cfg)
        profiles.append(p)
    yield profiles
    for p in profiles:
        app.profile_service.delete(p.id)

@pytest.mark.acceptance
@pytest.mark.parametrize("test_site,parser", [
    ("https://abrahamjuliot.github.io/creepjs/", parse_creepjs),
    ("https://browserleaks.com/canvas", parse_browserleaks_canvas),
    ("https://browserleaks.com/webgl", parse_browserleaks_webgl),
    # ...
])
async def test_fingerprint_uniqueness(ten_profiles, test_site, parser):
    results = []
    for profile in ten_profiles:
        async with launch_camoufox(profile) as browser:
            page = await browser.new_page()
            await page.goto(test_site, wait_until="networkidle")
            fp = await parser(page)
            results.append(fp)
    
    # все 10 уникальны
    assert len(set(r.hash for r in results)) == 10
    
    # каждый соответствует своему config
    for profile, result in zip(ten_profiles, results):
        assert result.matches_config(profile.fingerprint)
```

### Запуск
- **Локально**: `pytest tests/fingerprint/ -m acceptance` (медленно, ~10-20 минут)
- **CI**: запускается перед каждым release, не на каждый commit
- **Ручной regression**: после изменений в FingerprintGenerator или upgrade Camoufox

## Smoke tests при старте приложения

При первом запуске приложения предлагаем (опц.) запустить self-test:
- Создаётся test profile
- Запускается Camoufox в headless
- Открывается `chrome://version` (или Firefox-эквивалент `about:support`)
- Проверяется что UA/timezone/lang соответствуют конфигу
- Удаляется test profile

Это catches проблемы с установкой/permissions сразу.

## Regression test suite — backend

```
tests/
├── unit/
│   ├── test_fingerprint_generator.py    # consistency правила
│   ├── test_profile_service.py
│   ├── test_proxy_service.py
│   ├── test_security_kdf.py
│   ├── test_pbprof_format.py            # encrypt → decrypt round-trip
│   └── ...
├── integration/
│   ├── test_api_profiles.py             # HTTP CRUD
│   ├── test_api_launch.py               # с mocked subprocess
│   ├── test_db_migrations.py
│   └── test_sqlcipher_unlock.py
└── fingerprint/                          # acceptance
    ├── conftest.py
    ├── test_uniqueness.py
    ├── test_consistency.py
    └── test_known_detection_sites.py
```

## Regression test suite — frontend

```
frontend/src/
├── components/
│   └── __tests__/
│       ├── ProfileCard.test.tsx
│       ├── FingerprintEditor.test.tsx
│       └── ProxyPool.test.tsx
└── e2e/                                  # Playwright
    ├── flows/
    │   ├── create-profile.spec.ts
    │   ├── launch-profile.spec.ts
    │   ├── export-import.spec.ts
    │   └── change-password.spec.ts
    └── fixtures/
```

## Manual testing checklist

Перед каждым release вручную проверяем:

- [ ] Свежая установка на чистой Windows VM → first-run wizard работает
- [ ] Создание/запуск/удаление профиля
- [ ] Запуск 5 профилей одновременно
- [ ] Перезапуск приложения → unlock паролем работает
- [ ] Recovery code → unlock работает
- [ ] Export `.pbprof` → import на другой машине → профиль работает
- [ ] Change master password → re-unlock работает
- [ ] Wrong password → задержки/lockout как ожидается
- [ ] Установка Firefox extension в один профиль не появляется в другом
- [ ] Cookies сессии сохраняются между запусками одного профиля
- [ ] Cookies не пересекаются между профилями
- [ ] Прокси падает → профиль показывает error состояние
- [ ] Запуск без интернета → нормальное сообщение
- [ ] Удаление приложения → данные пользователя сохраняются (uninstall NSIS option)

## Performance tests

- Запуск 20 профилей одновременно → измеряем RAM/CPU/time
- 1000 профилей в БД → UI list rendering должен быть < 100ms (виртуализация списка)
- Поиск по 1000 профилям → < 50ms
- Старт приложения → < 2 сек до главного экрана (без учёта unlock)
- API latency 95p: < 50ms для всех CRUD endpoints

## Security tests

- Brute-force на master password → проверяем что задержки работают
- Tampered `.pbprof` → проверяем что signature mismatch ловится
- `.pbprof` с неверным паролем → корректное сообщение, нет panics
- SQL injection в API → pydantic validation отбивает
- XSS в полях профиля (name, notes) → React по умолчанию escape, проверяем
- API auth token reuse → token из старой сессии не работает после restart
