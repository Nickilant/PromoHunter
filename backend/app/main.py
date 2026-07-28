from fastapi import FastAPI

from app.routers import admin, auth, public, reports, suggestions

app = FastAPI(title="PromoHunter API", docs_url="/docs", openapi_url="/api/openapi.json")

app.include_router(auth.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(suggestions.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
