# Лабораторная работа №4
## Идемпотентность платежных запросов в FastAPI

## Важное уточнение
ЛР4 является **продолжением ЛР3/ЛР2** и выполняется на том же проекте.

В `lab_04` уже лежит кодовая база из предыдущей лабораторной:
- `backend/`
- `frontend/`
- `Dockerfile.backend`
- `Dockerfile.frontend`
- `.github/`

Если у студента есть доработки в предыдущей лабе, их нужно перенести в `lab_04`.

## Цель работы
Смоделировать и исправить сценарий:
1. Клиент отправил запрос на оплату.
2. Сеть оборвалась до получения ответа.
3. Клиент повторил тот же запрос.
4. Без защиты возможна двойная оплата.

Реализовать:
- таблицу `idempotency_keys`;
- middleware идемпотентности в FastAPI;
- возврат кэшированного ответа при повторе с тем же ключом;
- сравнение с подходом из ЛР2 (`REPEATABLE READ + FOR UPDATE`).

## Что дано готовым
1. Код проекта из предыдущей лабораторной.
2. Endpoint для retry-сценария:
   - `POST /api/payments/retry-demo`  
   режимы:
   - `unsafe` (без FOR UPDATE),
   - `for_update` (решение из ЛР2).
3. SQL-утилиты для ручной проверки:
   - `sql/01_prepare_demo_order.sql`
   - `sql/02_check_order_paid_history.sql`
   - `sql/03_check_idempotency_keys.sql`
4. Шаблон отчёта `REPORT.md`.

## Что нужно реализовать (TODO)

### 1) Миграция таблицы идемпотентности
Файл: `backend/migrations/002_idempotency_keys.sql`

Нужно:
- создать таблицу `idempotency_keys`;
- хранить ключ, endpoint, hash запроса, статус обработки, кэш ответа;
- добавить уникальный constraint для защиты от дубликатов;
- добавить индексы для lookup и cleanup.

### 2) Middleware идемпотентности
Файл: `backend/app/middleware/idempotency_middleware.py`

Нужно:
- читать `Idempotency-Key` из заголовка;
- для повторного запроса с тем же ключом и тем же payload возвращать кэшированный ответ;
- не вызывать повторно бизнес-логику списания;
- при reuse ключа с другим payload возвращать `409 Conflict`.

### 3) Демонстрация сценария без защиты
Файл: `backend/app/tests/test_retry_without_idempotency.py`

Нужно показать, что в `unsafe` сценарии повтор запроса может привести к двойной оплате.

### 4) Демонстрация сценария с Idempotency-Key
Файл: `backend/app/tests/test_retry_with_idempotency_key.py`

Нужно показать:
- повтор с тем же ключом -> кэшированный ответ;
- нет повторного списания;
- запись в `idempotency_keys` содержит сохранённый ответ.

### 5) Сравнение с решением из ЛР2
Файл: `backend/app/tests/test_compare_idempotency_vs_for_update.py`

Нужно **объяснить и показать** различия (в тесте — вывод в консоль и проверки; в отчёте — раздел 7 в `REPORT.md`):

| Механизм | Что защищает | Типичный сценарий из лабораторных |
|----------|----------------|-----------------------------------|
| **`FOR UPDATE` + изоляция (ЛР2)** | Две **параллельные** транзакции не «перешагивают» друг друга при оплате **одной** строки заказа | В ЛР2: `pytest …/test_concurrent_payment_*.py` — два одновременных `pay_order_safe` → одна оплата в истории; два `pay_order_unsafe` → гонка, две записи `paid` |
| **`Idempotency-Key` + middleware (ЛР4)** | Два **последовательных** HTTP-запроса с одним намерением (retry после обрыва сети) не выполняют списание дважды | В ЛР4: два `POST /api/payments/retry-demo` с одним ключом и телом → второй ответ из кэша, одна запись `paid` даже при `mode=unsafe` |

**Важно:** это разные слои и разные угрозы. `FOR UPDATE` не заменяет ключ: при обрыве сети клиент может повторить запрос **с новым** ключом или без ключа — снова дойдёт до БД. Ключ не заменяет `FOR UPDATE`: два разных ключа могут параллельно дернуть оплату — без блокировки в БД снова возможна гонка на `unsafe`. В продакшене обычно используют **оба** подхода.

## Запуск
```bash
cd lab_04
docker compose down -v
docker compose up -d --build
```

Проверка (с хоста, контейнеры уже подняты):

```bash
curl -sS http://127.0.0.1:8082/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5174/
docker compose exec -T db pg_isready -U postgres
```

Если на хосте нет `pg_isready`, используйте только команду через `docker compose exec … db` (как выше).

**Порты (см. `docker-compose.yml`):** API на хосте — **8082**, фронт — **5174**, PostgreSQL проброшен на хост как **5435**→5432 (если порт занят другим compose — поменяйте левую часть mapping и порт в `DATABASE_URL` у сервиса `backend`). После изменения кода Python пересоберите образ: `docker compose build backend`.

## Рекомендуемый порядок выполнения

После `docker compose up -d --build` скрипты из `backend/migrations/` **уже выполняются при первом создании** тома БД (`postgres_data`). Повторно гонять `001_init.sql` / `002_idempotency_keys.sql` вручную **не нужно** — появятся сообщения `already exists` / `duplicate key`: это нормально, схема уже на месте.

Ручные шаги 1–2 ниже имеют смысл только если том БД создан без нужных скриптов init; иначе пропустите. Полное пересоздание тома — команды из раздела **«Запуск»** выше (`docker compose down -v` и `up -d --build`).

```bash
# 1) Применить базовую схему (если не применена через init)
docker compose exec -T db psql -U postgres -d marketplace -f /docker-entrypoint-initdb.d/001_init.sql

# 2) Реализовать и применить миграцию идемпотентности
docker compose exec -T db psql -U postgres -d marketplace -f /docker-entrypoint-initdb.d/002_idempotency_keys.sql

# 3) Подготовить demo-order (опционально)
docker compose exec -T db psql -U postgres -d marketplace -f /sql/01_prepare_demo_order.sql

```

Тесты LAB 04: сервис `backend` в `compose` может быть остановлен — `exec` в него тогда не сработает. Используйте **одноразовый контейнер** (поднимет зависимости, в т.ч. `db`, по `depends_on`):

```bash
cd lab_04
docker compose run --rm backend pytest app/tests/test_retry_without_idempotency.py -v -s
docker compose run --rm backend pytest app/tests/test_retry_with_idempotency_key.py -v -s
docker compose run --rm backend pytest app/tests/test_compare_idempotency_vs_for_update.py -v -s
```

Если `backend` уже запущен (`docker compose up`), можно по-прежнему:

```bash
docker compose exec -T backend pytest app/tests/test_retry_without_idempotency.py -v -s
docker compose exec -T backend pytest app/tests/test_retry_with_idempotency_key.py -v -s
docker compose exec -T backend pytest app/tests/test_compare_idempotency_vs_for_update.py -v -s
```


## Структура LAB 04
```
lab_04/
├── backend/
│   ├── app/
│   │   ├── middleware/
│   │   │   └── idempotency_middleware.py      # TODO
│   │   ├── api/
│   │   │   └── payment_routes.py              # retry endpoint уже добавлен
│   │   └── tests/
│   │       ├── test_retry_without_idempotency.py
│   │       ├── test_retry_with_idempotency_key.py
│   │       └── test_compare_idempotency_vs_for_update.py
│   └── migrations/
│       └── 002_idempotency_keys.sql           # TODO
├── sql/
│   ├── 01_prepare_demo_order.sql
│   ├── 02_check_order_paid_history.sql
│   └── 03_check_idempotency_keys.sql
├── REPORT.md
└── README.md
```

## Критерии оценки
- Корректность реализации `idempotency_keys` + middleware — 35%
- Демонстрация retry-сценария без защиты и с защитой — 25%
- Сравнение с подходом FOR UPDATE из ЛР2 — 20%
- Качество отчёта и обоснований — 20%
