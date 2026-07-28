# PromoHunter

Краудсорсинговый сервис отслеживания промоакций сетей общепита: пользователи
отмечают, какие акционные товары (коллаборации, наборы, брендированный мерч)
реально есть в конкретном ресторане прямо сейчас.

Сценарий: найти акцию → узнать, есть ли товар в точке рядом → отметить, что
видел сам.

## Быстрый старт

Нужен только Docker (с Compose v2). Ни Python, ни Node, ни Postgres на хосте
не требуются.

```bash
git clone <repo> && cd PromoHunter
cp .env.example .env
make up          # или: docker compose up --build
```

После старта доступны:

| Адрес | Что это |
|---|---|
| http://localhost:5173 | Фронтенд (dev-режим с HMR) |
| http://localhost:8000/docs | Swagger бэкенда |
| localhost:5432 | PostgreSQL (можно подключиться DBeaver'ом, креды из `.env`) |

Миграции применяются автоматически при старте бэкенда. При первом запуске
(пустая база и `SEED_ON_START=true`) база сидируется тестовыми данными.

**Учётка админа из сидов:** `admin@local` / `admin123`.
Тестовые пользователи: `maria@example.com`, `ivan@example.com`,
`olga@example.com`, `dmitry@example.com` — пароль у всех `user123`.

Регистрация открытая. На пустой базе без сидов **первый зарегистрированный
пользователь автоматически получает роль `admin`** — удобно для локального
старта.

## Make-таргеты

```
make up            # поднять всё (build + up + логи)
make down          # остановить
make restart
make logs          # docker compose logs -f
make sh            # шелл в backend
make sh-front      # шелл во frontend
make migrate       # alembic upgrade head
make migration m="add reports"   # автогенерация ревизии
make seed          # прогнать сиды (идемпотентно)
make psql          # psql внутри контейнера db
make test          # pytest внутри backend
make reset         # down -v + up, полный сброс базы
make prod          # прод-сборка (см. ниже)
```

## Переменные окружения (`.env`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `promo` | Креды PostgreSQL |
| `DATABASE_URL` | `postgresql+psycopg://promo:promo@db:5432/promo` | URL БД для бэкенда (host — сервис `db`) |
| `JWT_SECRET` | dev-значение | Секрет подписи JWT, в проде поменять |
| `JWT_EXPIRE_MINUTES` | `10080` | Время жизни токена (7 дней) |
| `STATUS_WINDOW_HOURS` | `24` | Окно агрегации отчётов для статусов |
| `REPORT_COOLDOWN_MINUTES` | `30` | Кулдаун между отчётами одного пользователя по одной паре (точка, акция) |
| `SEED_ON_START` | `true` | Сидировать базу при старте, если таблица users пуста |
| `UID` / `GID` | `1000` | id пользователя хоста — чтобы файлы из контейнеров в bind-mount не были под root (`id -u` / `id -g`) |
| `VITE_API_PROXY_TARGET` | `http://backend:8000` | Куда vite проксирует `/api` в dev |

## Как это устроено

- **Акция принадлежит бренду (сети), а не точке.** Создали акцию для
  «Вкусно и точка» — она автоматически видна во всех ресторанах этой сети
  (связь `restaurant.brand_id == promotion.brand_id`, без копий записей).
- **Отчёты привязаны к конкретной точке.** Статус товара в точке считается
  по отчётам за последние `STATUS_WINDOW_HOURS`; от каждого пользователя
  учитывается только его последний отчёт: `yes > no` → «есть», `no > yes` →
  «кончилось», поровну → «спорно», нет данных → «нет данных»
  (`backend/app/services/status.py`).
- Пользовательские заявки на акции модерирует админ: в админке они
  сгруппированы по брендам, одобрение = создание нормальной акции на основе
  предзаполненной формы.

Стек: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16;
React 18 + TypeScript + Vite + Leaflet (OSM). Правила разработки — в
[CLAUDE.md](CLAUDE.md).

## Прод-режим

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# или: make prod
```

Отличия от dev: backend без `--reload` с несколькими воркерами и без
bind-mount'ов (код копируется в образ), фронт собирается в статику и отдаётся
nginx на порту 80 (он же проксирует `/api`), `SEED_ON_START=false`.

## Частые проблемы

- **Файлы из контейнера принадлежат root на хосте** — пропишите свои
  `UID`/`GID` в `.env` (`id -u`, `id -g`) и пересоберите: `make up`.
- **Backend падает на старте с ошибкой подключения к БД** — дождитесь
  healthcheck базы; entrypoint сам ждёт до минуты. Если база «застряла» после
  жёсткой остановки — `make reset` (сотрёт данные).
- **HMR не подхватывает правки** — в `vite.config.ts` уже включён
  `usePolling`; если правили конфиг, перезапустите контейнер:
  `docker compose restart frontend`.
- **Порт занят (5432/8000/5173)** — остановите локальные сервисы на этих
  портах или поменяйте проброс в `docker-compose.yml`.
- **Поменяли `requirements.txt` / `package.json`, а внутри контейнера ничего
  не изменилось** — зависимости ставятся при сборке образа: `make up`
  (пересоберёт) или `docker compose build backend|frontend`.
- **429 «Вы уже отмечали эту акцию здесь»** — это кулдаун
  (`REPORT_COOLDOWN_MINUTES`), защита от спама, а не ошибка.
