COMPOSE = docker compose

.PHONY: up down restart logs sh sh-front migrate migration seed psql test reset prod prod-down

up:
	$(COMPOSE) up --build -d
	$(COMPOSE) logs -f

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

sh:
	$(COMPOSE) exec backend sh

sh-front:
	$(COMPOSE) exec frontend sh

migrate:
	$(COMPOSE) exec backend alembic upgrade head

# make migration m="add reports"
migration:
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

seed:
	$(COMPOSE) exec backend python -m app.seed

psql:
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-promo} -d $${POSTGRES_DB:-promo}

test:
	$(COMPOSE) exec backend pytest -v

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d
	$(COMPOSE) logs -f

prod:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml down
