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

### 📱 iOS — сборка IPA + распространение

#### Сборка IPA (терминал)
```bash
# 1. Синхронизировать веб-ассеты
npx cap sync ios

# 2. Архив
cd ios
xcodebuild -project App/App.xcodeproj -scheme App -archivePath /tmp/velio.xcarchive archive -allowProvisioningUpdates

# 3. Экспорт IPA
xcodebuild -exportArchive -archivePath /tmp/velio.xcarchive -exportPath /tmp/velio-ipa -exportOptionsPlist /dev/stdin -allowProvisioningUpdates << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>debugging</string>
    <key>signingStyle</key>
    <key>signingStyle</key>
    <string>automatic</string>
</dict>
</plist>
EOF

# 4. Копировать в проект
cp /tmp/velio-ipa/App.ipa ios/Velo.ipa
```

#### Установка на iPhone
- **Finder:** подключи iPhone → перетащи `Velo.ipa` в "Приложения"
- **AltStore:** открой IPA на телефоне → Open in AltStore

#### Распространение другим людям
- Выложить `Velo.ipa` на Google Drive / GitHub Releases / Яндекс.Диск
- Люди устанавливают через AltStore (нужен AltStore на телефоне)

#### ⚠️ Важно (free developer)
- **IPA живёт 7 дней**, потом перестаёт открываться
- Нужно пересобирать и переустанавливать каждые 7 дней
- Через App Store ($99/год) этого ограничения нет
- **Без $99/год опубликовать в App Store нельзя**

#### Публикация в AltStore Source (для всех)
1. Создать XML-файл (AltStore Source)
2. Выложить IPA + XML на GitHub Pages или сервер
3. Люди добавляют Source в AltStore → приложение обновляется автоматом
4. Подробнее: https://altstore.io/source-format

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

---

## 🚀 Нативные возможности (план доработок)

### Приоритет 1 (сделать в ближайшее время)

#### 1. Фоновая запись через Foreground Service
- Показывать persistent-нотификацию "Velo.io записывает маршрут" во время записи
- Не выгружается из памяти при свёртывании (в отличие от current visibilitychange)
- **Плагин:** `@capacitor/geolocation` уже есть, нужен foreground service в нативном коде
- **iOS:** Background Modes в Info.plist (уже добавлено LocationAlways)
- **Android:** Foreground Service + нотификация

#### 2. Скорость / Темп / Расстояние в реальном времени
- `@capacitor/motion` — акселерометр
- Показывать текущую скорость, среднюю скорость, пройденное расстояние на экране записи
- Авто-пауза при остановке (по датчику движения)

#### 3. Haptic feedback
- `navigator.vibrate()` уже есть в браузере
- iOS: `@capacitor/haptics` для Taptic Engine (более приятная вибрация)
- Когда: старт записи, захват территории, стоп записи

### Приоритет 2 (после публикации)

#### 4. Deep Links / App Links
- `https://velio.app/territory/XXX` → открывается в приложении
- На Android: Android App Links (Asset Links JSON)
- На iOS: Universal Links (apple-app-site-association)

#### 5. Health / Google Fit интеграция
- Импорт велотренировок из Apple Health / Google Fit как GPX для захвата
- Экспорт захваченных территорий в Health как тренировки
- **Плагин:** отсутствует в Capacitor community, писать свой плагин

#### 6. Camera для фото территорий
- `@capacitor/camera` — прикреплять фото к территории при захвате (для рекламодателей — фото витрины)
- Для верификации не используем (трек валидируется структурой)

### Приоритет 3 (потом / необязательно)

#### 7. Offline-кеш карты
- Скачать тайлы `https://tile.openstreetmap.org/...` при подключении
- Писать трек офлайн → отправить при появлении сети
- **Плагин:** `@capacitor/filesystem` уже есть, нужен менеджер загрузок

#### 8. QR-код для шаринга территории
- Сгенерировать QR ссылку на территорию → другой сканирует и открывает

#### 9. Биометрия (Touch ID / Face ID)
- `@capacitor/biometrics` — дополнительная аутентификация для вывода средств (необязательно)

---

## 🔑 Keystore (Android подпись)

- **Файл:** `android/app/velio-release-key.jks`
- **Пароль store:** `velio123`
- **Пароль key:** `velio123`
- **Alias:** `velio`
- **Срок:** 10000 дней (~27 лет)
- **Никому не передавать!** Без него не выпустить обновление в RuStore

### Подпись для RuStore (PEPK)
```bash
# Скачать pepk.jar (один раз)
curl -sL "https://www.gstatic.com/play-apps-publisher-rapid/signing-tool/prod/pepk.jar" -o /tmp/pepk.jar

# Создать ZIP для RuStore
java -jar /tmp/pepk.jar \
  --keystore=android/app/velio-release-key.jks \
  --alias=velio \
  --output=android/app/pepk_out.zip \
  --encryptionkey=0000a602c72b07188122bf52043d9277ddf109716ca55dd0a10393b559e996c349bff51f20ffa9f04e2c02aa7078defaedf36efb85f1226ed0c333202347503ae1b96556 \
  --include-cert \
  --keystore-pass=velio123 \
  --key-pass=velio123
```

### Сборка release APK
```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export JAVA_HOME="/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home"
cd android && ./gradlew assembleRelease
# APK: android/app/build/outputs/apk/release/app-release.apk
```

## 🆘 КРИТИЧНО: Render — через неделю кончается бесплатный тариф

**Дедлайн:** ~25 июля 2026 (через неделю от 18.07)

**Варианты:**
1. **Оплатить Render** — перейти на платный тариф (от $7/мес за сервис, два сервиса = ~$14/мес)
2. **Переехать на другой хостинг** — VPS за $3-5/мес (например, timeweb.ru или reg.ru vps)
3. **Бесплатные альтернативы:**
   - **Fly.io** — есть free tier, но просыпается как Render
   - **Railway.app** — $5 кредита бесплатно
   - **Oracle Cloud** — вечно бесплатный VPS (ARM, 4 ядра, 24GB RAM) — лучший вариант, но сложная регистрация
   - **Свой сервер** — если есть старый ноут/малинка

**Что переезжает:**
- PostgreSQL (можно оставить на Render за $7/мес, или перенести)
- FastAPI бэкенд
- Frontend (nginx или статика)

---

## 🛠 Процесс публикации новой версии в магазины

### Сейчас
Веб: коммит → Render подхватил мгновенно  
Нативные: нужно вручную собрать APK/IPA, подписать, загрузить в RuStore/App Store, ждать модерацию

### Процесс на каждый релиз
1. Коммит + пуш + деплой на Render (как обычно)
2. `npx cap sync android && cd android && ./gradlew assembleRelease`
3. Загрузить `app-release.apk` в RuStore (консоль → новая версия)
4. iOS: `npx cap sync ios` → Xcode → Product → Archive → App Store Connect
5. Ждать модерацию (обычно час-день, бывает до 3 дней)

### Автоматизация (на будущее)
- GitHub Actions: на пуш тега `v*` собирать APK и публиковать через RuStore API
- Fastlane: подпись + загрузка в App Store одной командой

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