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
1. Ачивки на фронте — страница/модалка с иконками, прогресс
2. Ачивка `first_share` — интеграция в share-функцию
3. Ачивка `comeback` — определение что пользователь раньше владел этой территорией
4. Ачивка `area_X` — в `check_achievements_on_capture` уже есть, но не проверена в тестах
5. Редеплой Render (очистка cache + deploy)