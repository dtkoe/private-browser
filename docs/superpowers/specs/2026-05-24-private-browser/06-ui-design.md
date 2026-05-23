# 06 — UI Design

## Принципы

- **Тёмная тема по умолчанию** (light тоже доступен)
- **Плотный профессиональный layout** — это инструмент, не игрушка
- **Layout C** — sidebar (список профилей) + main panel (детали)
- **Русский основной, английский опц.** через i18n
- **Keyboard-friendly**: hotkeys для CRUD/launch
- **Responsive до min 1280×720**, оптимизировано для 1920×1080

## Главный экран — overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [LOGO] Private Browser           [🔍 Поиск...]    [🌐] [⚙] [👤] [─ □ ✕]  │
├──────────────┬──────────────────────────────────────────────────────────────┤
│              │                                                              │
│ [+ Новый]    │   [Имя профиля]                          [▶ Запустить]    │
│              │   Avatar + Status: ● Ready              [✏ Edit] [⋯ More]  │
│ [🔽 Все]     │                                                              │
│ Account_01●  │   ┌──────────────────────────────────────────────────────┐   │
│ Account_02●  │   │ FINGERPRINT                                          │   │
│ Account_03●  │   │ OS: Windows 11   Browser: Firefox 142                │   │
│ Account_04   │   │ Screen: 1920×1080   Device: 8C/8GB                   │   │
│ Account_05   │   │ Timezone: America/New_York   Lang: en-US             │   │
│ Account_06   │   │ WebGL: Intel Iris Xe   Fonts: 142                    │   │
│ Account_07   │   │ Canvas seed: 0x4a3f...   TLS JA3: live...            │   │
│ Account_08   │   │ [Подробнее в редакторе...]                           │   │
│              │   └──────────────────────────────────────────────────────┘   │
│ ─────────    │                                                              │
│ ТЕГИ         │   ┌──────────────────────────────────────────────────────┐   │
│ #facebook(5) │   │ ПРОКСИ                              [Изменить]      │   │
│ #amazon(3)   │   │ ✓ RES proxy.example.com:8000  US-NY                  │   │
│ #personal(2) │   │ IP: 192.0.2.4   Latency: 87ms   Last check: 2 min   │   │
│              │   └──────────────────────────────────────────────────────┘   │
│              │                                                              │
│              │   ┌──────────────────────────────────────────────────────┐   │
│              │   │ ПОСЛЕДНИЕ СЕССИИ                                     │   │
│              │   │ 2026-05-24 13:42  ·  38 мин  ·  192.0.2.4            │   │
│              │   │ 2026-05-23 09:15  ·  12 мин  ·  192.0.2.4            │   │
│              │   │ 2026-05-22 18:30  ·  2 ч 14 мин  ·  192.0.2.4        │   │
│              │   │ [Показать все...]                                    │   │
│              │   └──────────────────────────────────────────────────────┘   │
│              │                                                              │
│              │   ┌──────────────────────────────────────────────────────┐   │
│              │   │ ЗАМЕТКИ                                              │   │
│              │   │ FB Ads аккаунт для клиента X. Бизнес-страница...    │   │
│              │   └──────────────────────────────────────────────────────┘   │
│              │                                                              │
├──────────────┴──────────────────────────────────────────────────────────────┤
│ Запущено: 0/8   ·   База: ●●● зашифрована   ·   Camoufox 142.0.1   ·   v0.1│
└─────────────────────────────────────────────────────────────────────────────┘
```

## Экраны

### 1. Главный (Overview)
- Sidebar: список профилей с фильтром по статусу/тегам, поиск, кнопка "+ Новый"
- Main: детальный вид выбранного профиля (как выше)
- Footer: bar статуса (running count, DB encryption state, Camoufox version, app version)

### 2. Редактор профиля (Profile Editor)
- Модальное окно или отдельный route
- Вкладки:
  - **Identity**: имя, аватар-color, теги, заметки
  - **Fingerprint** (advanced): все поля JSON, с авто-валидацией консистентности, кнопка "Regenerate"
  - **Proxy**: select из ProxyPool или новый, тест связи кнопкой
  - **Browser data**: показывает размер cookies/cache, кнопка "Clear browser data"
  - **Extensions**: список установленных Firefox addons, добавить/удалить

### 3. Proxy Pool
- Таблица всех прокси: тип, host:port, статус, последняя проверка, country, latency
- Bulk actions: Test all, Delete unused
- Кнопка "Add proxy" — single или paste batch (формат `type://user:pass@host:port` по строке)
- Импорт из CSV

### 4. Settings
- Theme (dark/light/auto)
- Language (ru/en)
- Camoufox version (с кнопкой "Check for update")
- API port (default 8769)
- VPN preset (если пользователь использует VPN на хосте — отображать предупреждение)
- Master password change
- Backup БД (manual snapshot)
- Logs viewer link

### 5. Activity / Logs
- Лог запусков профилей
- Аудит действий (create/delete/export)
- Фильтр по дате/профилю/типу

### 6. First-run wizard
- Welcome
- Установка master password (обязательно)
- Download Camoufox (progress bar, ~150MB)
- Опц. import profiles из существующих анти-детект инструментов (заглушка для v1)

## Компоненты (shadcn/ui based)

| Компонент | Использование |
|---|---|
| `Sidebar` + `SidebarItem` | Левая панель профилей |
| `Card` | Группы информации в main panel |
| `Dialog` | Модалки (export password, confirm delete) |
| `Sheet` | Профильный редактор (выезжает справа) |
| `Tabs` | В редакторе профиля |
| `Table` (TanStack) | Proxy pool, sessions list |
| `DropdownMenu` | "⋯" контекстные действия |
| `Toast` (sonner) | Уведомления (профиль запущен, прокси упал) |
| `Tooltip` | На иконках статуса |
| `Badge` | Теги, статусы |
| `Form` (react-hook-form) | Все формы с zod валидацией |
| `Command` (cmd-k палитра) | Быстрый поиск/запуск из shortcut |

## Цветовая схема (dark theme)

```css
--bg-primary:    #0f1115   /* основной фон */
--bg-secondary:  #1a1d24   /* sidebar, cards */
--bg-tertiary:   #252932   /* hover, selected */
--border:        #2d3340
--text-primary:  #e5e7eb
--text-secondary:#9ca3af
--text-muted:    #6b7280

--accent:        #4a7cff   /* primary action — синий */
--accent-hover:  #6090ff

--status-ready:  #6fc788   /* зелёный */
--status-running:#ffa45c   /* оранжевый */
--status-error:  #ff7c7c   /* красный */
--status-suspended: #9ca3af /* серый */
```

## Hotkeys

| Сочетание | Действие |
|---|---|
| `Ctrl+K` | Command palette (быстрый поиск/запуск) |
| `Ctrl+N` | Новый профиль |
| `Ctrl+E` | Edit текущего профиля |
| `Ctrl+R` | Запустить выбранный |
| `Ctrl+Shift+R` | Остановить выбранный |
| `Del` | Удалить (с подтверждением) |
| `Ctrl+/` | Toggle sidebar |
| `Ctrl+,` | Settings |
| `↑↓` в sidebar | Навигация по профилям |
| `Enter` в sidebar | Запустить выбранный |

## i18n

Папка `frontend/i18n/`:
- `ru.json` — основной
- `en.json` — английский

Используем `next-intl` или `react-i18next`. Все строки в коде через `t("key")`.

## Состояние UI vs backend

| Состояние | Где живёт |
|---|---|
| Список профилей | Backend (БД) + кэш TanStack Query на фронте |
| Текущий выбранный профиль | Zustand store на фронте |
| Открытые модалки | Zustand store |
| Тема, язык | localStorage (синк с БД через app_settings) |
| Запущенные процессы | Backend (LaunchManager registry) + WS подписка на фронте |
| Realtime updates (статусы) | WebSocket `/ws` подписка |

## Доступность (a11y)

- Все интерактивные элементы доступны с клавиатуры
- `aria-label` на иконочных кнопках
- Контраст AA минимум (WCAG)
- `prefers-reduced-motion` уважаем (Tailwind default)
