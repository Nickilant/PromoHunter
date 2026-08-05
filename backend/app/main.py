import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func

from app.config import settings
from app.database import SessionLocal
from app.routers import (
    admin,
    auth,
    game,
    issues,
    osm_imports,
    promo_codes,
    public,
    rating,
    reports,
    restaurant_suggestions,
    subscriptions,
    suggestions,
)

logger = logging.getLogger("promohunter.trust")

# Ключи advisory-lock: при нескольких воркерах пересчёт выполняет только один
_TRUST_LOCK_KEY = 0x50524F4D  # "PROM"
_GAME_LOCK_KEY = 0x50524F47  # "PROG"


def _locked_pass(lock_key: int, run, name: str) -> None:
    """Выполнить проход под advisory-lock: без дублей между воркерами."""
    db = SessionLocal()
    try:
        locked = db.execute(select(func.pg_try_advisory_lock(lock_key))).scalar()
        if locked:
            try:
                stats = run(db)
                if any(stats.values()):
                    logger.info("%s: %s", name, stats)
            finally:
                db.execute(select(func.pg_advisory_unlock(lock_key)))
                db.commit()
    except Exception:
        logger.exception("%s failed", name)
    finally:
        db.close()


def _trust_loop() -> None:
    from app.services.trust import run_trust_pass

    while True:
        time.sleep(settings.trust_job_interval_seconds)
        _locked_pass(_TRUST_LOCK_KEY, run_trust_pass, "trust pass")


def _game_loop() -> None:
    """Шкалы захвата, сезонный зачёт и предупреждения об атаке."""
    from app.services.game import run_game_pass
    from app.services.notify import sweep_attack_notifications

    def run(db):
        stats = run_game_pass(db)
        stats["notified"] = sweep_attack_notifications(db)
        return stats

    while True:
        time.sleep(settings.game_job_interval_seconds)
        _locked_pass(_GAME_LOCK_KEY, run, "game pass")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.trust_job_interval_seconds > 0:
        threading.Thread(target=_trust_loop, daemon=True, name="trust-job").start()
    if settings.game_enabled and settings.game_job_interval_seconds > 0:
        threading.Thread(target=_game_loop, daemon=True, name="game-job").start()
    # Бот: подтверждение номера через отправку контакта
    from app.services.telegram_bot import start_polling_thread

    start_polling_thread()
    yield


app = FastAPI(
    title="PromoHunter API",
    docs_url="/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

uploads_dir = Path(settings.upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.include_router(auth.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(suggestions.router, prefix="/api")
app.include_router(restaurant_suggestions.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(rating.router, prefix="/api")
app.include_router(promo_codes.router, prefix="/api")
app.include_router(game.router, prefix="/api")
app.include_router(issues.router, prefix="/api")
app.include_router(osm_imports.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
