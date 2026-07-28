# PromoHunter — правила разработки

Краудсорсинговый сервис отслеживания промоакций сетей общепита.
MVP: найти акцию → узнать, есть ли товар в конкретной точке → отметить, что видел сам.

## Ключевая доменная идея

Акция (`Promotion`) принадлежит **бренду** (`Brand`), а не отдельному ресторану.
Связь «акция видна в точке» вычисляется на лету через
`restaurant.brand_id == promotion.brand_id` — никаких копий записей.
Отчёты о наличии (`Report`) привязаны к конкретной точке (`Restaurant`).

## Правила разработки

- **Локальное окружение не создаётся.** Никаких `python -m venv`, `pip install`
  на хосте, `npm install` на хосте. Всё живёт в контейнерах.
- Любая команда Python, pytest, alembic, npm выполняется через
  `docker compose exec <service> ...` или через соответствующий таргет `make`.
- Новая зависимость добавляется в `requirements.txt` / `package.json` и
  подхватывается пересборкой образа (`make up`), а не установкой в живой
  контейнер.
- Для параллельной работы над несколькими ветками использовать `git worktree`,
  не `git stash`.
- Правки — точечные и по месту. Не переписывать рабочие файлы целиком ради
  «причёсывания».

## Команды

Все рутинные операции — через `make` (см. Makefile): `make up`, `make down`,
`make logs`, `make migrate`, `make migration m="..."`, `make seed`, `make test`,
`make psql`, `make reset`.

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic,
  PostgreSQL 16, JWT (`python-jose`), `passlib[bcrypt]`.
- Frontend: React 18 + TypeScript + Vite, React Router, Leaflet
  (изолирован в `src/components/MapView.tsx`), обычный CSS с токенами в
  `src/styles/tokens.css`. Без UI-китов и HTTP-библиотек.
- Все запросы фронта идут на относительный `/api/...` — проксирует Vite (dev)
  и nginx (prod). Никаких хардкодов `localhost:8000` во фронте.

## Чего в MVP нет (не добавлять)

Гильдии, очки, рейтинги, репутация, коллекции, достижения, пуши, фото,
сканирование чеков, проверка геолокации при отчёте, комментарии, чаты,
WebSocket, real-time.
