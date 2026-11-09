from fastapi import FastAPI

from app.routes import health

app = FastAPI(title="PadamFirst API")
app.include_router(health.router, prefix="/api")
