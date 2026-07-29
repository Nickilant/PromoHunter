import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select, func

from app.config import settings
from app.database import SessionLocal
from app.routers import (
    admin,
    auth,
    public,
    rating,
    reports,
    restaurant_suggestions,
    subscriptions,
    suggestions,
)

logger = logging.getLogger("promohunter.trust")

# Ключ advisory-lock: при нескольких воркерах пересчёт выполняет только один
_TRUST_LOCK_KEY = 0x50524F4D  # "PROM"


def _trust_loop() -> None:
    from app.services.trust import run_trust_pass

    while True:
        time.sleep(settings.trust_job_interval_seconds)
        db = SessionLocal()
        try:
            locked = db.execute(
                select(func.pg_try_advisory_lock(_TRUST_LOCK_KEY))
            ).scalar()
            if locked:
                try:
                    stats = run_trust_pass(db)
                    if stats["matured"] or stats["drifted"]:
                        logger.info("trust pass: %s", stats)
                finally:
                    db.execute(select(func.pg_advisory_unlock(_TRUST_LOCK_KEY)))
                    db.commit()
        except Exception:
            logger.exception("trust pass failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.trust_job_interval_seconds > 0:
        threading.Thread(target=_trust_loop, daemon=True, name="trust-job").start()
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

app.include_router(auth.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(suggestions.router, prefix="/api")
app.include_router(restaurant_suggestions.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(rating.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
