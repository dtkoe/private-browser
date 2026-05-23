# 03 — Fingerprint Vectors

## Подход

Используем Camoufox который патчит fingerprint на C++ уровне (внутри Firefox исходников). Передаём конфиг через JSON. Наша работа = **генерировать консистентные JSON-конфиги** (UA matches platform matches Client Hints matches fonts matches timezone matches WebGL renderer для выбранной OS).

Раздел документирует:
1. Векторы которые Camoufox **покрывает из коробки**
2. Что мы **должны корректно конфигурировать**
3. Векторы которые Camoufox **НЕ покрывает** — пока принимаем как риски (см. [10](./10-risks-and-mitigations.md))

## Векторы покрываемые Camoufox

Источник: README Camoufox, GitHub issues, тесты против CreepJS/BrowserLeaks.

| # | Вектор | Уровень патча | Наш конфиг-ключ | Что должны передать |
|---|---|---|---|---|
| 1 | **navigator.userAgent** | Firefox C++ binding | `navigator.userAgent` | Согласовано с OS+browserVersion |
| 2 | **navigator.platform** | C++ | `navigator.platform` | "Win32"/"MacIntel"/"Linux x86_64" |
| 3 | **navigator.oscpu** | C++ | `navigator.oscpu` | Согласовано с OS |
| 4 | **navigator.appVersion** | C++ | `navigator.appVersion` | Производное от UA |
| 5 | **navigator.languages** | C++ | `navigator.language(s)` | Match геолокации прокси |
| 6 | **navigator.hardwareConcurrency** | C++ | `navigator.hardwareConcurrency` | 2/4/8/16 (по статистике OS) |
| 7 | **navigator.deviceMemory** | C++ | `navigator.deviceMemory` | 2/4/8 (round numbers) |
| 8 | **navigator.maxTouchPoints** | C++ | `navigator.maxTouchPoints` | 0 для desktop, 5/10 для мобильных |
| 9 | **navigator.plugins / mimeTypes** | C++ | автоматически | Пусто как в современных Firefox |
| 10 | **screen.width/height/availWidth/availHeight** | C++ | `screen.width`, `screen.height` | Из набора реальных разрешений |
| 11 | **screen.colorDepth / pixelDepth** | C++ | `screen.colorDepth` | 24 |
| 12 | **window.devicePixelRatio** | C++ | `window.devicePixelRatio` | 1.0 / 1.25 / 1.5 / 2.0 |
| 13 | **window.outerWidth/outerHeight** | C++ | `window.outer*` | viewport+chrome |
| 14 | **Canvas 2D fingerprint** | C++ noise | автоматически | Per-profile seed |
| 15 | **WebGL renderer string** | C++ | `webGl.renderer`, `webGl.vendor` | Realistic pair (Intel/NVIDIA/AMD) |
| 16 | **WebGL parameters (MAX_TEXTURE_SIZE и др.)** | C++ | `webGl.parameters` | Из преса для renderer |
| 17 | **WebGL supported extensions** | C++ | автоматически | По renderer |
| 18 | **WebGL shader precision** | C++ | автоматически | По renderer |
| 19 | **AudioContext fingerprint** | C++ noise | автоматически | Per-profile seed |
| 20 | **Fonts (CSS / @font-face enumeration)** | C++ whitelist + metric noise | `fonts` array | Список из ~150 шрифтов под OS |
| 21 | **Font metric noise** | C++ (Camoufox shifts letter spacing 0-0.1px) | автоматически | — |
| 22 | **WebRTC IP leak (host/srflx candidates)** | C++ (только relay если proxy) | `webrtc:mode` | "proxy" если задан proxy |
| 23 | **WebRTC local IPv4/IPv6 leak** | C++ | `webrtc:localipv4`, `webrtc:localipv6` | Спуфнутые значения |
| 24 | **WebRTC SDP logs** | C++ (fixed leaks v146) | автоматически | — |
| 25 | **TLS fingerprint (через NSS)** | C++ (Firefox использует NSS, патчится cipher order) | автоматически | Camoufox держит правдоподобный JA3 |
| 26 | **HTTP/2 fingerprint (Akamai h2 hash)** | C++ (settings order) | автоматически | — |
| 27 | **Accept-Language header** | C++ | согласован с `navigator.languages` | — |
| 28 | **User-Agent header (HTTP)** | C++ | согласован с `navigator.userAgent` | — |
| 29 | **Sec-CH-UA Client Hints** | C++ | согласовано | — (Firefox их не шлёт, но Camoufox может) |
| 30 | **Timezone (Intl.DateTimeFormat)** | C++ + ICU | `timezone` | "America/New_York" по proxy geo |
| 31 | **Date.getTimezoneOffset** | C++ | автоматически из timezone | — |
| 32 | **Geolocation API** | C++ (lat/lng spoof) | `geolocation:latitude/longitude` | По proxy geo |
| 33 | **Battery API** | C++ stub | автоматически | Фикс. значения |
| 34 | **Sensors (gyro/accel/light)** | C++ disable | автоматически | Disabled для desktop |
| 35 | **Pointer/Touch event capability** | C++ | автоматически по OS | — |
| 36 | **MediaDevices.enumerateDevices count** | C++ | `mediaDevices.micros/webcams/speakers` | Realistic counts |
| 37 | **MediaDevices ID** | C++ | автоматически | Per-profile stable |
| 38 | **Speech synthesis voices** | C++ | автоматически по OS+lang | — |
| 39 | **Speech playback rate noise** | C++ | автоматически | Per-profile |
| 40 | **matchMedia hover/pointer/color-gamut** | C++ | автоматически | По OS |
| 41 | **Permission API consistency** | C++ | автоматически | — |
| 42 | **CDP detection markers (window.cdc_*, navigator.webdriver)** | НЕТ — Firefox не имеет CDP, используется Marionette | — | Не наша проблема |
| 43 | **matchMedia HiDPI mismatch (fixed v146)** | C++ | автоматически | — |

## Что мы должны генерировать (FingerprintGenerator)

Модуль `backend/services/fingerprint_generator.py` создаёт **консистентный** конфиг для нового профиля:

### Алгоритм

```python
def generate_fingerprint(
    target_os: Literal["windows", "macos", "linux"] | None = None,
    target_geo: GeoLocation | None = None,
    target_browser_version: str | None = None,
) -> CamoufoxConfig:
    # 1. Выбор OS — по статистическому распределению или из proxy geo
    os = target_os or weighted_random({"windows": 0.70, "macos": 0.18, "linux": 0.04, "other": 0.08})
    
    # 2. Выбор Firefox version — самый свежий stable который поддерживает Camoufox
    ff_version = target_browser_version or get_pinned_ff_version()
    
    # 3. UA-строка — собирается из OS + version по шаблонам Mozilla
    ua = build_user_agent(os, ff_version)
    
    # 4. Screen — реалистичный из топ-10 разрешений для OS (Win11: 1920x1080, 2560x1440 и т.д.)
    screen = pick_screen_for_os(os)
    
    # 5. Hardware — coherent
    hw_concurrency = weighted_random({4: 0.30, 8: 0.45, 16: 0.25})
    device_memory = pick_compatible_memory(hw_concurrency)  # 4→8GB, 8→16GB, 16→32GB
    
    # 6. WebGL — realistic renderer/vendor pair для OS
    webgl = pick_webgl_for_os(os)
    # Windows → "Intel(R) Iris(R) Xe Graphics" / "ANGLE (Intel ...)"
    # macOS → "Apple M1 Pro" / "Apple"
    # Linux → "Mesa Intel(R) UHD Graphics"
    
    # 7. Fonts — стандартный набор для OS
    fonts = load_font_list(os)  # ~140-160 шрифтов
    
    # 8. Timezone + locale — по proxy geo
    if target_geo:
        timezone = geo_to_timezone(target_geo)
        locale = geo_to_locale(target_geo)
        languages = geo_to_languages(target_geo)
    else:
        # Fallback на нейтральные значения
        timezone, locale, languages = "UTC", "en-US", ["en-US", "en"]
    
    # 9. Per-profile seeds — для воспроизводимого noise
    seeds = {
        "canvas": random_uint64(),
        "audio": random_uint64(),
        "webgl_noise": random_uint64(),
    }
    
    # 10. Сборка в Camoufox JSON format
    return CamoufoxConfig(...)
```

### Согласованность — что должно matcher

| A → B | Правило |
|---|---|
| OS → UA | `Mozilla/5.0 (Windows NT 10.0; Win64; x64)` для Win и т.д. |
| OS → platform | "Win32" / "MacIntel" / "Linux x86_64" |
| OS → fonts | Загружаем `fonts/{os}.txt` |
| OS → WebGL renderer | Только реальные комбинации |
| Proxy IP → timezone | Из IP geo lookup через MaxMind GeoLite2 |
| Proxy IP → locale | Из geo |
| Proxy IP → languages | Из geo |
| Hardware concurrency → device memory | Реалистичная пара |
| Screen resolution → devicePixelRatio | Только реалистичные комбинации |

## Что НЕ покрываем (риски)

| Вектор | Почему не покрываем | Mitigation |
|---|---|---|
| **GPU fingerprint через WebGL timing-атаки** | Требует low-level патчей в ANGLE/Skia, Camoufox этого не делает | Принимаем риск. Большинство анти-бот не использует |
| **TCP/IP stack fingerprint (p0f, Nmap-style)** | Зависит от OS на которой запущен браузер. Прокси может помочь если правильный стек | Рекомендуем пользователю VPN или residential proxy с реалистичным стеком |
| **Mouse/keyboard паттерны behavioral** | Camoufox имеет базовое human-like movement, но не полноценный ML | Документируем, v2+ может расширить |
| **Audio output timing** | Tier 3+ детекторы могут анализировать | Risk accepted |
| **Microsoft Edge как UA target** | Camoufox — Firefox, не может прикинуться Edge/Chrome нативно | Architectural choice |
| **Battery API дискретные паттерны** | Camoufox даёт фикс. значения, не имитирует разрядку | Не критично |

## Как тестируем

См. [08-testing-strategy.md](./08-testing-strategy.md). TL;DR:
- Acceptance tests против 5 эталонных fingerprint-тестов:
  - https://abrahamjuliot.github.io/creepjs/
  - https://browserleaks.com/
  - https://pixelscan.net/
  - https://bot.sannysoft.com/
  - https://tls.peet.ws/api/all
- Уникальность: 10 профилей → 10 различных hash во всех векторах
- Consistency: каждый профиль проходит "pixelscan consistency check"
