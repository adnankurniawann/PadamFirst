from fastapi import FastAPI

from app.routes import cells, health, hotspots, priorities

app = FastAPI(title="PadamFirst API")
for module in (health, cells, priorities, hotspots):
    app.include_router(module.router, prefix="/api")
