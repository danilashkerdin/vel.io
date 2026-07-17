# Tasks / Notes

## Интеграция ачивок в роутеры — DONE (2026-07-17)

- `territory_router.py` — `check_achievements_on_capture` вызывается в `_save_and_return` после `process_capture_rewards`
- `payment_router.py` — `check_achievements_on_premium` вызывается в `activate_premium`
- `auth_router.py` — `check_achievements_on_referral` вызывается в `/register` при реферале
- Добавлен эндпоинт `GET /api/achievements` — возвращает список достижений пользователя

### Багфиксы по пути
- `database.py:95` — `_cleanup_expired()` лишний отступ (IndentationError)
- `database.py:131` — `session.commit()` без отступа внутри `_activate_demo_zone`
- `database.py:133` — `_notify_expiring_territories()` вне функции
- `database.py:194` — `_cleanup_expired` не импортировал `Territory`
- `telegram_router.py:161` — `if ref_user_id` лишний отступ
- `telegram_router.py:172` — `db.refresh(user)` лишний отступ
- `database.py` — `elif` блок содержал строки 86-93 с отступом (должны быть на уровне `init_db`)

### Тесты — 5 новых, 37/37 passed
- `test_first_capture_achievement` — захват → first_capture
- `test_territories_5_achievement` — 5 захватов → territories_5
- `test_premium_achievement` — премиум → premium
- `test_referral_achievement` — реферал → invite_friend
- `test_achievements_endpoint_returns_all_types` — базовый тест ручки

## Осталось сделать
1. ~~Ачивки на фронте — страница/модалка с иконками, прогресс~~ ✅
2. ~~Ачивка `first_share` — интеграция в share-функцию~~ ✅
3. ~~Ачивка `comeback` — второй захват~~ ✅
4. ~~Ачивка `area_X` — тест~~ ✅
5. Редеплой Render
6. Render MCP — когда перезапустишь opencode

## Текущая сессия — DONE (2026-07-17, часть 2)

### Ачивка first_share
- `POST /api/share` — новый эндпоинт, триггерит `check_achievements_on_share`
- Фронт: `shareTelegram()` и `shareCopyLink()` вызывают `fireShareAchievement()` (один раз, через `window._shareFired`)
- Тест: `test_share_achievement` ✅

### Ачивка comeback
- Упрощена: выдаётся на второй и последующие захваты (`t_count_before > 0`)
- Тест: `test_comeback_achievement` — первый захват без comeback, второй с comeback ✅

### Багфикс
- `_save_and_return` → `check_achievements_on_capture` вызывался ПОСЛЕ `db.commit()`, поэтому `t_count` уже включал текущую территорию. Исправил: `t_count_before = t_count_after - 1`

### Тесты — 8 ачивок, 40/40 passed
- Добавлены: `test_comeback_achievement`, `test_share_achievement`, `test_area_1_achievement`