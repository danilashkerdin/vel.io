# Tasks / Notes

## Актуальная сессия: Capacitor + Native App (2026-07-18)

### ✅ Сделано за эту сессию
- **Установлен Node.js** (v26.5.0) через Homebrew
- **Capacitor инициализирован** — `@capacitor/core`, `@capacitor/cli`, `@capacitor/android`
- **Плагины установлены**: `@capacitor/geolocation`, `@capacitor/filesystem`, `@capacitor/share`
- **Android платформа добавлена** — `npx cap add android`
- **capacitor.config.json** — appId `io.velo.app`, appName `Velo.io`, webDir `frontend`
- **config.js** — определяет Capacitor runtime (`window.Capacitor`), ставит продакшн URL
- **recorder.js** — нативная геолокация через `window.Capacitor.Plugins.Geolocation` с fallback на браузер. Работает и в браузере, и в нативном приложении
- **app.js** — Service Worker отключается в Capacitor-режиме
- **AndroidManifest.xml** — все разрешения: `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`, `VIBRATE`
- **APK debug собран** — `android/app/build/outputs/apk/debug/app-debug.apk` (BUILD SUCCESSFUL)

---

### 📱 Android — что доделать вручную

#### 1. Иконка приложения (Android)
**Файл:** `frontend/icons/icon-512.svg`
```
open -a "Android Studio" android/
```
В Android Studio: правый клик на `app/res` → New → Image Asset
- Foreground Layer: выбери `frontend/icons/icon-512.svg`
- Background Color: `#0a0a1a` (тёмный фон)
- Res: `ic_launcher` и `ic_launcher_round`
После генерации → `npx cap sync android && cd android && ./gradlew assembleDebug`

#### 2. Release APK (подпись keystore)
```bash
# Сгенерировать keystore (один раз)
cd android
keytool -genkey -v -keystore velio-release-key.jks \
  -alias velio -keyalg RSA -keysize 2048 -validity 10000

# Собрать подписанный APK
cd android
./gradlew assembleRelease

# APK будет в: android/app/build/outputs/apk/release/app-release.apk
```

#### 3. Публикация в RuStore
- Зарегистрироваться в консоли RuStore (rustore.ru)
- Создать карточку приложения
- Загрузить `app-release.apk`
- Заполнить описание, скриншоты, категорию (Карты и навигация / Спорт)
- Отправить на модерацию

---

### 📱 iOS — что нужно сделать (новое)

#### 1. Добавить iOS платформу
```bash
npm install @capacitor/ios --save
npx cap add ios
```

#### 2. Настроить Info.plist (разрешения)
Добавить в `ios/App/App/Info.plist`:
- `NSLocationWhenInUseUsageDescription` — "Velo.io использует геолокацию для записи маршрутов"
- `NSLocationAlwaysAndWhenInUseUsageDescription` — "Velo.io использует фоновую геолокацию для записи заездов"
- `NSLocationAlwaysUsageDescription` — то же самое

#### 3. Сборка iOS (нужен Apple Developer)
```bash
npx cap sync ios
npx cap open ios
```
В Xcode:
- Подписать приложение (нужен Apple Developer аккаунт, $99/год)
- Выбрать симулятор или реальное устройство
- Product → Archive → Distribute App

#### 4. Альтернатива (без $99)
- **AltStore** — sideload через AltServer
- **SideStore** — fork AltStore, работает без переподписи каждые 7 дней (с VPN)
- **Xcode + личный Apple ID** — до 3 приложений, 7 дней до переподписи

---

## ✅ Ранее завершённое (прошлые сессии)

### Render — деплой
- Коммиты запушены, Clear build cache & deploy выполнено (44edc32 — последний)
- Живой URL: https://vel-io.onrender.com

### Меню — реорганизовано
- 4 секции: Основное / Активность / Мой профиль / Рекламодателю
- `app.js` — привязка кнопок, `advertiser.js` — обработчики

### Planner / Плацан
- Только построение маршрута (без захвата)
- Валидация: min 3 точки
- OSRM профиль: `foot`

### Recorder / Фоновая запись
- `visibilitychange` — пауза/возобновление
- `keepalive: true` в fetch
- `lastKnownPosition` при возобновлении

### Ачивки
- model + service + интеграция в роутеры (territory, payment, auth)
- Фронт: модалка с иконками и прогресс-барами
- 40/40 e2e тестов

### Push-уведомления (Firebase FCM)
- `notifications.js` — регистрация FCM, сохранение токена
- Звуковые оповещения
- ⚠️ **Не работает** — webhook/key issue

### Уведомления о захвате
- Предыдущему владельцу при захвате территории
- Рекламодателю при захвате спонсорской зоны
- Эндпоинты: GET /api/notifications, POST /api/notifications/{id}/read

### Багфиксы
- `database.py` — IndentationError в `_cleanup_expired`, `_activate_demo_zone`, `_notify_expiring_territories`
- `telegram_router.py` — отступы в `if ref_user_id`, `db.refresh(user)`
- `territory_router.py` — missing logger import (500 error)
- Planner: `Polygon` → GeoJSON сериализация

---

## 📋 ДОДЕЛАТЬ В ЭТОЙ СЕССИИ
- [x] Баннер установки нативного приложения (для Telegram WebApp и браузера)
  - Для браузера: кнопка "Установить" → share/ссылка
  - Для TWA: кнопка → RuStore / App Store (заглушка, ссылки обновить после публикации)
  - После закрытия — больше не показывать (localStorage)

## 📋 БАГИ (нужно починить)
1. **Firebase Cloud Messaging** — push не приходят. Нужно проверить webhook URL, service worker ключ, FCM проект
2. **Telegram Bot / Login** — не работает через ngrok? Нужно разобраться с вебхуками бота
3. **Planner** — ошибка при нажатии кнопки построения маршрута (нужен текст ошибки из консоли)

## 📋 UI/UX
4. **Иконки спонсорских точек** — придумать дизайн вместо текущих

## 📋 Фичи (на будущее)
5. Страница "Мои территории" — история изменений
6. Strava API — импорт активностей
7. Публичные страницы с OG-картинками
8. Статистика в реальном времени (онлайн, захваты/час)
9. Экспорт CSV для админа
10. Тёмная тема (ручной тумблер)

---

## Договорённости
1. **RuStore** — основной магазин для Android (App Store нет, нет аккаунта)
2. **Capacitor** — обёртка над HTML/JS, никаких фреймворков (не Flutter!)
3. **Firebase** — push-уведомления, бесплатный tier
4. **Render** — деплой вручную через Dashboard (Clear build cache & deploy)
5. **Тесты** — `pytest`, e2e требует PostGIS на localhost:5432
6. **Язык** — русский, даты UTC
7. **iOS** — через Capacitor, но нужен Apple Developer ($99/год) или AltStore/SideStore