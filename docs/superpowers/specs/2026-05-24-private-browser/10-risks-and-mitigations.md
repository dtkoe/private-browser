# 10 — Risks and Mitigations

## Категории рисков

1. **Dependency risks** — внешние проекты на которые мы опираемся
2. **Technical risks** — архитектурные/реализационные
3. **Adversarial risks** — анти-детект gonna catch up
4. **Operational risks** — наш собственный темп, soло+AI
5. **Legal/regulatory risks**

---

## 1. Dependency risks

### R1.1 — Camoufox заглохнет
**Описание**: Maintainer daijro в больнице с марта 2025. Развитие замедлилось. Community fork (CloverLabsAI) поддерживает Firefox 142 но не гарантировано продолжит.

**Вероятность**: Средняя (30-50%)
**Влияние**: Критическое (мы без браузерного движка)

**Mitigation**:
- **Plan A**: Следим за обоими репо (`daijro/camoufox`, `CloverLabsAI/camoufox`). При признаках стагнации community fork — переход к ним.
- **Plan B**: Pinned Camoufox version в `camoufox.lock`. Если обе ветки заглохнут — мы остаёмся на последней работающей версии и фризим Firefox base. Это даёт ~6-12 месяцев работы пока новые детекторы не обойдут наш статичный fingerprint.
- **Plan C** (recovery): берём патчи Camoufox (они opensource) и аппликуем сами на свежий Firefox. Это сильно увеличивает scope (~6-12 месяцев работы плюс собственная Firefox build pipeline) — фактически start over в C++ режиме.
- **Plan D** (radical pivot): переход на Approach C (наш Rust+utls прокси) или Approach A (CDP wrapper) — потеря части возможностей.

**Trigger для активации**: если >60 дней нет commits в обоих репо ИЛИ Firefox 145 stable вышел а Camoufox всё на 142.

### R1.2 — Firefox upstream sloman ключевые API
**Описание**: Mozilla может удалить или изменить функции на которые опирается Camoufox (например, NSS internal API, font enumeration API).

**Вероятность**: Низкая-средняя
**Влияние**: Высокое (часть fingerprint векторов перестанут работать)

**Mitigation**:
- Pinned версия Firefox через Camoufox
- При обновлении Camoufox на новую Firefox base — обязательно regression тесты перед deploy
- ESR (Extended Support Release) Firefox в качестве более стабильной базы — но Camoufox не использует ESR. Может потребовать наш собственный форк Camoufox на ESR.

### R1.3 — camoufox-profile-manager (upstream) развивается несовместимо
**Описание**: polyackiy может сделать существенные архитектурные изменения которые осложнят merge.

**Вероятность**: Средняя
**Влияние**: Низкое-среднее (мы и так делаем большую часть работы)

**Mitigation**: см. [04-fork-strategy.md](./04-fork-strategy.md) — cherry-pick подход, мы независимы.

### R1.4 — Python зависимости (FastAPI, Playwright, pywebview) breaking changes
**Вероятность**: Низкая
**Влияние**: Среднее

**Mitigation**: pinning через `uv lock` или `pip-tools`. Major upgrades — отдельный M с регрессией.

---

## 2. Technical risks

### R2.1 — pywebview на Windows webview2 не поддерживает наш UI
**Описание**: Webview2 от MS на Windows 10/11 для рендеринга. Возможны баги с современным React/Next features.

**Вероятность**: Средняя (10-20%)
**Влияние**: Среднее (workaround есть)

**Mitigation**: Switch на Electron если pywebview не справится. Стоимость: +80MB к binary, +2 недели работы. Не fatal.

### R2.2 — SQLCipher performance под нагрузкой
**Описание**: Шифрование добавляет ~10-30% к запросам. С 10000+ профилей может стать заметно.

**Вероятность**: Низкая (для нашего scope)
**Влияние**: Низкое (UX оптимизация)

**Mitigation**:
- Индексы на горячих путях
- Виртуализация списка в UI
- Кэширование на frontend
- Опц.: shared cache mode SQLite
- Бенчмарк в M2

### R2.3 — Множественные Camoufox процессы переполняют RAM
**Описание**: Каждый Camoufox = ~200-300MB. 20 одновременных = 4-6 GB.

**Вероятность**: Высокая если пользователь злоупотребляет
**Влияние**: Среднее (предупреждаем пользователя)

**Mitigation**:
- В Settings: лимит на одновременные запуски (default 10)
- Мониторинг RAM в footer
- Warning toast при достижении 75% системной RAM

### R2.4 — Профили коррапт при некорректном завершении
**Описание**: Если приложение крашнется или Windows kill процесс — Firefox profile dir может быть в inconsistent state.

**Вероятность**: Средняя
**Влияние**: Низкое (Firefox умеет recover)

**Mitigation**:
- При запуске профиля — backup критичных файлов (cookies.sqlite) с rotation
- Detect inconsistent state и предложить recovery
- Auto-snapshot БД каждые N часов (см. [07](./07-security-model.md))

---

## 3. Adversarial risks (анти-детект arms race)

### R3.1 — Анти-бот сервисы детектят Camoufox
**Описание**: Cloudflare, DataDome, Akamai обновляются. То что обходилось вчера — могут поймать сегодня.

**Вероятность**: Постоянная (это arms race)
**Влияние**: Среднее (теряем эффективность но не fatal)

**Mitigation**:
- Следим за CreepJS обновлениями и issues Camoufox
- Регрессионный тест после каждого обновления anti-bot
- В UI: бейдж "tested against X" с датой
- Прозрачно сообщаем что обходим и что нет

### R3.2 — Firefox как UA становится подозрительным
**Описание**: Если процент Firefox-юзеров продолжит падать (~3%), сайты могут начать relax verification для Chrome но tighten для Firefox.

**Вероятность**: Низкая-средняя в долгосрочной перспективе
**Влияние**: Среднее (наш core архитектурный bet — Firefox)

**Mitigation**:
- Опц. UA spoof — представляться Chrome (но это создаёт inconsistency, сразу детектится)
- Долгосрочное: Chrome-base анти-детект — потребует полностью другого продукта

### R3.3 — Behavioral детекция (мышь, тайминги)
**Описание**: Tier-1 анти-бот может детектить ботов через behavioral анализ который мы не закрываем.

**Вероятность**: Высокая для специфичных сайтов
**Влияние**: Variable

**Mitigation**:
- Camoufox имеет базовое human-like mouse — используем
- В v2: ML-based behavior simulation
- Пока — документируем как known limitation

### R3.4 — Browser-specific детектируемые баги Camoufox
**Описание**: Camoufox может иметь свои "tells" — баги или артефакты которые палят что это не stock Firefox.

**Вероятность**: Средняя
**Влияние**: Среднее

**Mitigation**:
- Регулярные тесты против CreepJS "lies detector"
- Issues в Camoufox upstream если находим — репортим/фиксим
- Опц.: свои патчи поверх Camoufox если критично (но это форк-of-fork, сложно)

---

## 4. Operational risks

### R4.1 — Solo developer бутылочное горлышко
**Описание**: Один разработчик. Болезнь, выгорание, отвлечения — всё блокирует.

**Вероятность**: Высокая в долгосрочной перспективе
**Влияние**: Среднее

**Mitigation**:
- AI ассистент (я) — ускорение в 2-3 раза по части работы
- Acceptance criteria для каждого M — гарантия что промежуточные релизы рабочие даже если проект остановится
- Документация по архитектуре чтобы другие разработчики могли подхватить
- Open-source с самого начала — community может помочь

### R4.2 — Scope creep
**Описание**: По ходу хочется добавить новые фичи, отвлекает от core.

**Вероятность**: Высокая
**Влияние**: Высокое (срыв сроков)

**Mitigation**:
- Жёсткий non-goals список в [01](./01-overview-and-goals.md)
- Все идеи "хорошо бы добавить" → в `backlog.md`, не в текущий M
- Review checkpoint на каждом M — спрашиваем "это в scope текущего M?"

### R4.3 — Чрезмерный перфекционизм
**Описание**: Долгое полирование вместо отгрузки.

**Mitigation**: Acceptance criteria, не больше. Polish откладываем в M5.

---

## 5. Legal/regulatory risks

### R5.1 — Юзеры используют для нарушения ToS платформ
**Описание**: Кто-то делает мульти-аккаунтинг где это запрещено, попадается. Платформа делает претензии нам.

**Вероятность**: Низкая для open-source инструмента общего назначения
**Влияние**: Среднее (репутация)

**Mitigation**:
- В README, About, Terms четко: "инструмент для legitimate purposes — privacy, testing, automation. Соблюдай ToS платформ которые используешь."
- Не маркетим как "обходить Facebook" — маркетим как privacy + multi-account management
- Аналог: Tor — инструмент для anonymity, не отвечает за пользователей-плохишей

### R5.2 — Regulatory action в специфичных юрисдикциях
**Описание**: Некоторые страны могут ограничить anti-detection tools.

**Вероятность**: Низкая на ближайшую перспективу
**Влияние**: Низкое-среднее

**Mitigation**:
- Документация на английском
- GitHub Releases — нейтральная distribution platform
- Если требуется — geo-block specific regions

### R5.3 — Camoufox license drift
**Описание**: MPL 2.0 у Firefox, MPL у Camoufox. Если кто-то изменит license в наследниках — наши обязательства могут измениться.

**Mitigation**:
- Pinned версии — то что было MPL остаётся MPL
- Юридический ревью license compliance перед v1 release

---

## Сводная таблица

| ID | Риск | Веро­ятность | Влия­ние | Plan |
|---|---|---|---|---|
| R1.1 | Camoufox заглохнет | Mid | Crit | Pinned + plan B,C,D |
| R1.2 | Firefox API breaking | Low-Mid | High | Pin + regression |
| R1.3 | Upstream divergence | Mid | Low-Mid | Cherry-pick |
| R1.4 | Python deps break | Low | Mid | Pinning |
| R2.1 | pywebview не справится | Mid | Mid | Electron fallback |
| R2.2 | SQLCipher slow | Low | Low | Bench + optimize |
| R2.3 | RAM overuse | High | Mid | Limit + warn |
| R2.4 | Profile corruption | Mid | Low | Snapshots |
| R3.1 | Anti-bot adapts | Постоянный | Mid | Regression + transparency |
| R3.2 | FF UA suspicious | Low-Mid | Mid | Long-term watch |
| R3.3 | Behavioral detect | High | Var | Document + v2 ML |
| R3.4 | Camoufox tells | Mid | Mid | CreepJS testing |
| R4.1 | Solo bottleneck | High | Mid | AI + docs + OSS |
| R4.2 | Scope creep | High | High | Backlog discipline |
| R4.3 | Perfectionism | Mid | Mid | AC-driven |
| R5.1 | ToS abuse | Low | Mid | Marketing + terms |
| R5.2 | Regulatory | Low | Low-Mid | Watch |
| R5.3 | License drift | Low | Low-Mid | Pin + review |

## Главный честный вывод

**Самый большой риск — R1.1**: вся наша архитектура опирается на Camoufox, проект которого в неопределённом состоянии. Если он не восстановится в течение 6 месяцев и community fork не наберёт momentum, мы окажемся в положении "наш браузер работает но не обновляется", и в течение 12 месяцев анти-бот системы научатся его детектировать.

**Что нам это говорит для дизайна**:
- Build the abstraction layer (`CamoufoxAdapter`) так чтобы свап на другой движок был возможен
- Не давать обещаний про "годами работающий анти-детект"
- Положить в roadmap план перехода на свой Firefox-fork если нужно (после v1)
