# Velo.io — Playwright e2e / integration tests

Логические end-to-end и интеграционные тесты для **back-end (FastAPI)** и
**front-end (vanilla JS)** на [Playwright](https://playwright.dev).

## Структура

```
e2e/
  playwright.config.js   # конфиг: проекты api + ui
  global-setup.js        # сброс БД + первичная регистрация админа
  reset_db.py            # TRUNCATE всех таблиц (запускается из global-setup)
  helpers/
    api.js               # обёртка над request-фикстурой Playwright
    data.js              # координаты, GPX-фикстуры, утилиты уникальных email'ов
    ui.js                # проксирование API + предзаполнение сессии в UI
  api/*.spec.js          # интеграционные тесты REST API
  ui/*.spec.js           # браузерные e2e тесты страниц
```

## Как запустить

### 1. Поднять стек

```bash
docker-compose up --build
```

- **PostGIS** на `localhost:5432` (db `velo_io`)
- **backend** на `http://localhost:8000`
- **frontend (nginx)** на `http://localhost:3000`

> Порт `8000` должен быть свободен перед поднятием стека (на нём не должен
> висеть другой процесс).

### 2. Установить зависимости и браузер Playwright

```bash
npm install
npm run test:e2e:install   # == npx playwright install chromium
```

### 3. Запустить тесты

```bash
npm run test:e2e:api        # только интеграционные API-тесты
npm run test:e2e:ui         # только браузерные e2e-тесты
npm run test:e2e            # весь набор
```

Вручную:

```bash
npx playwright test --config e2e/playwright.config.js
```

### Отдельный тест

```bash
npx playwright test --config e2e/playwright.config.js --project=api territories
```

## Переменные окружения

| Переменная         | По умолчанию                      | Назначение                              |
|-------------------|------------------------------------|------------------------------------------|
| `API_BASE_URL`    | `http://localhost:8000`           | Базовый URL backend для API-тестов       |
| `UI_BASE_URL`     | `http://localhost:3000`           | Базовый URL frontend для UI-тестов       |
| `ADMIN_EMAIL`     | `admin@vel.io`                    | Email админа                            |
| `ADMIN_PASSWORD`  | `adminpass123`                    | Пароль админа (создаётся в global-setup) |
| `E2E_RESET_DB`    | `true`                            | Отключает сброс БД (`false`)            |

## Как это устроено

- **global-setup** перед набором сбрасывает БД (см. `reset_db.py`) и
  регистрирует аккаунт админа. Каждый тест создаёт свои уникальные email'ы,
  поэтому наборы изолированы даже на общей базе.
- **API-тесты** работают через request-контекст Playwright — это те же HTTP
  запросы, что и браузер, но без UI.
- **UI-тесты** открывают страницы на `:3000`. Фронтенд в этой конфигурации
  считает себя «продакшен-сборкой» (порт 3000) и ходит на
  `https://vel-io.onrender.com`. Хелпер `ui.js` перехватывает эти запросы и
  проксирует их на локальный backend — так тесты не зависят от сети и не
  трогают прод.

## Отчёты

- Терминал: list-репорт
- HTML-отчёт: `playwright-report/` (открыть `npx playwright show-report`)
- Screenshots / video / trace — только при падениях
  (`screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`).