# Быстрый старт — LAB 04 (Idempotency Key)

## 0) Пререквизиты
Перед ЛР4 должны быть готовы:
- логика оплаты из ЛР2 (`pay_order_unsafe`, `pay_order_safe`);
- рабочая схема БД из предыдущих лабораторных.

## 1) Запуск проекта
```bash
cd lab_04
docker compose down -v
docker compose up -d --build
```

## 2) Миграции `001_init.sql` и `002_idempotency_keys.sql`

Они лежат в `backend/migrations/` и при первом `docker compose up` с **пустым** томом БД выполняются автоматически (`/docker-entrypoint-initdb.d`). Повторный запуск `psql -f …001…` / `…002…` вручную даст `already exists` — это ожидаемо. Нужна чистая БД: `docker compose down -v`, затем снова `up -d --build`.

## 3) Реализовать middleware
Файл:
- `backend/app/middleware/idempotency_middleware.py`

Проверьте, что middleware подключен в `backend/app/main.py`.

## 4) Подготовить заказ для ручной проверки (опционально)
```bash
docker compose exec -T db psql -U postgres -d marketplace -f /sql/01_prepare_demo_order.sql
```

## 5) Реализовать и запустить тесты
Файлы:
- `backend/app/tests/test_retry_without_idempotency.py`
- `backend/app/tests/test_retry_with_idempotency_key.py`
- `backend/app/tests/test_compare_idempotency_vs_for_update.py`

Запуск (одноразовый контейнер `backend` — не требует, чтобы сервис `backend` был в состоянии `running`):
```bash
docker compose run --rm backend pytest app/tests/test_retry_without_idempotency.py -v -s
docker compose run --rm backend pytest app/tests/test_retry_with_idempotency_key.py -v -s
docker compose run --rm backend pytest app/tests/test_compare_idempotency_vs_for_update.py -v -s
```
Если API уже поднят: `docker compose exec -T backend pytest …`

## 6) Заполнить отчёт
Заполните `REPORT.md` по результатам сценариев и сравнений.
