from fastapi import FastAPI
from database import init_db
from auth import router as auth_router
from agents import router as agents_router
from webhook import router as webhook_router

app = FastAPI(title="Botko API")

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(webhook_router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"status": "ok", "message": "Botko API running"}

@app.get("/health")
def health():
    return {"status": "ok"}