# Velo.io — территориальная игра для велосипедистов 🚴

Территориальная игра для велосипедистов. Пользователи загружают **GPX-треки**
своих поездок, сервис автоматически находит **замкнутые петли** маршрута,
преобразует их в **полигоны территорий** и закрепляет владение за пользователем.
Пересекающиеся территории вычитаются — в собственность уходит только незанятая
площадь.

Дополнительно сервис поддерживает **спонсорские территории** (рекламные зоны
компаний) и **измеримую модель дохода**: тот, кто захватывает территорию,
пересекающуюся со спонсорской зоной, получает **10%** месячного бюджета зоны.

---

## Возможности

- **GPX → территории**: загрузка трека, детекция замкнутых циклов (spatial grid),
  упрощение геометрии, вычисление площади, сохранение полигона в PostGIS.
- **Умный расчёт владения**: перекрывающиеся территории вычитаются, выдаётся
  только незанятая площадь; захват чужих территорий перехватывает владение.
- **Лента лидеров** по общей площади, достижения, реферальная система.
- **Спонсорские территории**: администратор создаёт рекламные зоны на карте с
  месячным бюджетом, пользователь захвативший пересечение получает отчисления.
- **Premium**: оплата через **Telegram Stars**, VIP-емейлы без оплаты, лимит
  бесплатных захватов (по умолчанию 1 в неделю).
- **Рекламные аккаунты**: профиль рекламодателя, пополнение баланса зон,
  дашборд показов/кликов.
- **Уведомления** (включая Telegram-бота), **OG-превью** для шаринга территорий.
- **Мобильные приложения** на базе Capacitor (Android + iOS) с фоновой записью
  GPS-трека (foreground service).

---

## Монетизация

- **Спонсорские территории**: рекламодатель платит месячный бюджет
  (~5000₽), платформа получает **90%**, захвативший зону пользователь — **10%**.
- При повторном захвате территории доход переходит новому владельцу.
- **Premium** (оплата Telegram Stars): снимает лимит на частоту захватов.
- **Реферальная система**: приглашай друзей -> получай бонусы.

### Платежи

- **Telegram Stars** — Premium и пополнение рекламных зон (приоритетный способ).
- Telegram-бот выставляет инвойсы и обрабатывает вебхуки об оплате.

---

## Технологический стек

| Слой      | Технологии                                                                   |
|-----------|------------------------------------------------------------------------------|
| Backend   | Python 3.12, FastAPI, SQLAlchemy 2, slowapi (rate limiting), httpx           |
| База      | PostgreSQL + **PostGIS** 15, GeoAlchemy2, Alembic                            |
| Геометрия | Shapely, PyProj (слияние полигонов, пересчёт проекций)                       |
| Frontend  | Vanilla JS (ES modules), Leaflet.js, CSS (без сборки)                        |
| Парсинг   | lxml (GPX), собственная пайплайн-логика       |
| Мобилка   | Capacitor 8 (Android + iOS), Geolocation, Filesystem, Share                  |
| Тесты     | pytest (backend), Playwright (API + UI e2e)                                  |
| Инфра     | Docker Compose (PostGIS + backend + nginx), Alembic-миграции                 |

---

## Архитектура

```
backend/
  main.py              — FastAPI app, CORS, rate limiter, keep-alive, логирование
  config.py            — pydantic-settings (DATABASE_URL, SECRET_KEY, CORS, Telegram…)
  database.py          — SQLAlchemy engine, Base, get_db, init_db
  models.py            — User, Territory (PostGIS), Notification, SponsoredTerritory,
                         AdvertiserProfile/Payment, UserBalance, Transaction, GpxHash,
                         UserAchievement
  auth.py              — PBKDF2-хэширование паролей, JWT, get_current_user
  pipeline.py          — GPX → замкнутые петли → полигон → площадь
  gpx_parser.py        — парсинг GPX с упрощением и фильтром GPS-выбросов
  loop_detector.py      — детекция замкнутых циклов (spatial grid, дедупликация)
  merger.py           — объединение полигонов через Shapely
  limiter.py           — настройка slowapi (глобальный тумблер RATELIMIT_ENABLED)
  routers/             — auth, territory, notification, payment, admin, advertiser,
                       telegram (бот + рефералы), og (превью)
  services/           — territory_service, sponsored_service, notification_service
  alembic/            — миграции БД
  tests/               — pytest-юнит + интеграционные тесты
frontend/
  index.html / auth.html / public.html / admin.html
  js/                  — ES modules (app, auth, map, upload, editor, share,
                           territories, admin, config…)
  css/                 — стили
  nginx.conf           — reverse proxy + security headers
e2e/
  playwright.config.js — проекты api + ui
  helpers/, api/, ui/ — хелперы и спецификации Playwright
android/ ios/          — Capacitor-обёртки мобильных приложений
```

---

## Модели данных (ключевые)

- **User** — email, username, hashed_password, `is_premium`, `captures_count`,
  `is_advertiser`, `ton_wallet`, `referred_by`, `referral_bonuses`,
  `telegram_chat_id`.
- **Territory** — Polygon (PostGIS, srid 4326), `area`, `closures_count`,
  `parts_count`, владелец, `color`, `image_url`, `link_url`.
- **SponsoredTerritory** — рекламная зона: Polygon, `monthly_budget_*`,
  `is_active`, текущий владелец, показы/клики.
- **AdvertiserProfile / AdvertiserPayment** — рекламный аккаунт и оплаты (Stars).
- **UserBalance** — накопленный баланс `balance_rub`, `total_earned_rub`.
- **Transaction** — начисления и выплаты (типы `earned` / `payout`).
- **UserAchievement** — достижения по типу (первые захваты, площади, рефералы…).
- **GpxHash** — хэш загруженных треков (дедупликация повтора одних и тех же).
- **Notification** — уведомления пользователя.

---

## API (основные endpoints)

### Auth
- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/telegram`,
  `GET /api/auth/me`, `PUT /api/auth/profile`

### Территории
- `POST /api/upload-gpx` — загрузить GPX, прогнать пайплайн, сохранить территорию
- `POST /api/capture-ride`, `POST /api/plan-route` — онлайн-запись трека
- `GET /api/territories?north=&south=&east=&west=&limit=&offset=` — bbox-запрос
- `GET /api/territories/public/{id}`, `GET /api/my-territories`,
  `PATCH /api/territories/{id}`, `DELETE /api/territories/{id}`
- `GET /api/leaderboard` — рейтинг по общей площади
- `GET /api/sponsored-territories`, `POST /api/share`, `GET /api/initial-view`
- `GET /api/achievements`, `GET /api/achievements/all`, `GET /api/activity`

### Уведомления
- `GET /api/notifications`, `POST /api/notifications/read-all`

### Платежи / баланс
- `POST /api/payment/create-star-invoice` — инвойс Telegram Stars
- `POST /api/payment/request-payout`, `GET /api/payment/status`
- `GET /api/balance`, `GET /api/transactions`, `GET /api/my-sponsored`

### Админка
- `GET /api/admin/dashboard`, `GET /api/admin/tiers`
- CRUD `/api/admin/sponsored-territories`
- `GET/PATCH /api/admin/users`, `POST /api/admin/users/{id}/balance`
- `GET /api/admin/payouts/pending|history`, `POST /api/admin/payouts/process/{id}`

### Рекламодатели
- `GET /api/advertiser/tiers|profile|dashboard|payments`
- `PUT /api/advertiser/profile`
- `GET /api/my-advertiser-zones`, `PATCH /api/my-advertiser-zones/{id}`

### Telegram / рефералы
- `POST /api/telegram/webhook`, `GET/POST /api/telegram/set-webhook`
- `GET /api/referral/link`, `GET /api/referral/bonuses`

### OG-превью
- `GET /api/og/it/{territory_id}`, `GET /api/og/territory/{id}.png`

### Прочее
- `GET /api/health` — health-check с проверкой БД

---

## Быстрый старт

### Вариант 1 — Docker (рекомендуется)

```bash
# 1) Настроить .env из шаблона
cp backend/.env.example backend/.env
#  -> указать DATABASE_URL, SECRET_KEY, при необходимости Telegram-токен

# 2) Поднять стек (PostGIS + backend + frontend)
docker-compose up --build
```

- PostGIS → `localhost:5432` (db `velo_io`)
- backend → `http://localhost:8000`
- frontend → `http://localhost:3000`

> Порт `8000` должен быть свободен перед поднятием стека.

### Вариант 2 — Локальная разработка

```bash
# База
docker-compose up -d db

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # настроить
uvicorn main:app --reload

# Frontend (в другом терминале)
cd frontend
python3 -m http.server 3000
```

### Миграции

```bash
docker-compose exec backend alembic upgrade head
# или локально:
cd backend && alembic upgrade head
# Создать новую миграцию:
alembic revision --autogenerate -m "description"
```

---

## Тестирование

### Backend (pytest)

```bash
cd backend

# Юнит-тесты (БД не нужна)
pytest tests/test_auth.py tests/test_gpx_parser.py tests/test_loop_detector.py \
       tests/test_merger.py tests/test_pipeline.py -v

# E2E-тесты (нужен PostGIS на localhost:5432)
pytest tests/test_e2e.py -v

# Все тесты
pytest tests/ -v
```

### E2E / интеграционные (Playwright)

```bash
# Установить зависимости и браузер
npm install
npm run test:e2e:install        # == npx playwright install chromium

# Запустить
npm run test:e2e:api            # только REST API-тесты
npm run test:e2e:ui             # только браузерные e2e
npm run test:e2e                # весь набор
# вручную:
npx playwright test --config e2e/playwright.config.js
```

Переменные окружения e2e: `API_BASE_URL`, `UI_BASE_URL`, `ADMIN_EMAIL`,
`ADMIN_PASSWORD`, `E2E_RESET_DB` (подробности в `e2e/README.md`).

> Примечание: `global-setup` перед запуском сбрасывает БД (см. `e2e/reset_db.py`)
> и регистрирует аккаунт админа. Каждый тест использует уникальные email'ы —
> наборы изолированы друг от друга.

---

## Переменные окружения

Основные (полный список — в `backend/.env.example` и `backend/config.py`):

| Переменная                 | По умолчанию                                   | Назначение                                        |
|----------------------------|------------------------------------------------|---------------------------------------------------|
| `DATABASE_URL`             | `postgresql://postgres:postgres@localhost:5432/velo_io` | DSN подсистемы PostgreSQL + PostGIS      |
| `SECRET_KEY`               | `velo-io-default`                               | JWT-секрет (заменить в проде!)                     |
| `CORS_ORIGINS`             | JSON-список                                     | Разрешённые Origin                                 |
| `ADMIN_EMAIL`              | `admin@vel.io`                                  | Админ (доступ в `/admin.html`)                     |
| `VIP_EMAILS`                | `[]`                                            | Белый список email'ов для premium без оплаты        |
| `FREE_CAPTURES_LIMIT`      | `1`                                             | Лимит бесплатных захватов (за период)                 |
| `FREE_PREMIUM_SLOTS`      | `100`                                           | Сколько первых юзеров получает premium бесплатно        |
| `RATELIMIT_ENABLED`        | `true`                                          | Тумблер slowapi-лимитов (отключать для e2e)       |
| `TELEGRAM_BOT_TOKEN`      | —                                               | Токен Telegram-бота (уведомления + рефералы)           |
| `TELEGRAM_BOT_USERNAME`    | `velio_bot`                                     | Username бота                                     |
| `PREMIUM_PRICE_STARS`      | `200`                                           | Стоимость Premium в Telegram Stars                   |
| `PREMIUM_PRICE_TON`        | `10`                                            | Стоимость Premium в TON (альтернатива)              |
| `SPONSORED_TIERS_JSON`      | JSON-список тарифов зон                          | Тарифы рекламных территорий                         |
| `FRONTEND_URL` / `APP_URL`  | локальные URL                                   | CORS + keep-alive пинг                              |

---

## Развёртывание (продакшен)

- **Docker**: миграции выполняются автоматически через `start.sh`
  (`alembic upgrade head` перед стартом приложения).
- **Render / VPS (без Docker)**: команда запуска
  `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000`.
- **Ручной прогон миграций**:
  `docker-compose exec backend alembic upgrade head`.
- **Полный сброс БД (теряет данные)**:
  `docker-compose down -v && docker-compose up --build`.
- Никогда не удаляйте старые файлы миграций — Alembic отслеживает применённые.

> ⚠️ **Безопасность**: файлы подписи Android (`.jks`, `.keystore`, `.pem`,
> `pepk_out.zip`, `rustore-upload-key.zip`) и `.ipa` **не должны попасть в git** —
> они исключены через `.gitignore`. Не загружайте их в репозиторий.

---

## Структура мобильных приложений

Каталоги `android/` и `ios/` — это Capacitor-обёртки вокруг фронтенда:

- Геопозиция, фоновый сбор GPS-трека (foreground service на Android).
- Шаринг территорий (Capacitor Share), работа с файлами (GPX-экспорт).
- Сборка и публикация в RuStore / App Store — из соответствующих каталогов с
  помощью Capacitor CLI (`npx cap sync`, `npx cap open android`, и т.д.).

---

## Условности проекта

- Русский язык для user-facing сообщений и значений по умолчанию.
- JWT-авторизация через заголовок `Authorization: Bearer <token>`.
- Все пространственные операции — через PostGIS (`ST_Intersects`,
  `ST_Difference`, `ST_Union`, `ST_DWithin`).
- Datetime — timezone-aware UTC.
- Цвета — только `#RRGGBB` (валидируются).
- Пароли: минимум 6 символов.
- Revenue share пользователю: **10%** (настраивается в `sponsored_service.py`).

---

## Лицензия

ISC. См. `LICENSE` (если присутствует).