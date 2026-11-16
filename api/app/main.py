import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import cells, health, hotspots, priorities

app = FastAPI(title="PadamFirst API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
)
for module in (health, cells, priorities, hotspots):
    app.include_router(module.router, prefix="/api")
