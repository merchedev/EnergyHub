from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import APP_NAME, APP_VERSION, DEMO_MODE, DEV_MODE, LOG_LEVEL, STATIC_DIR
from .database import SessionLocal, init_db
from .models import Contract
from .routers.api import router
from .services import demo

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("energyhub")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if DEMO_MODE:
        with SessionLocal() as db:
            contract = db.scalars(select(Contract).limit(1)).first()
            if contract is None:
                logger.info("Cargando datos de demostración de EnergyHub")
                demo.seed_demo(db)
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Control y estimación del consumo eléctrico del hogar para Home Assistant.",
    lifespan=lifespan,
)

if DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(router)

if STATIC_DIR and Path(STATIC_DIR).is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/")
    def root() -> dict:
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "message": "EnergyHub API. En desarrollo, abre el frontend de Vite en el puerto 5173.",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8099, reload=True)
