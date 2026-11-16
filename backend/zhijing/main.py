"""FastAPI application factory for the Zhijing local study workbench."""

from asyncio import Lock
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import ai, study, themes
from .infra.db import Database
from .legacy import spring
from .services.study import StudyService
from .services.themes import ThemeService
from .settings import Settings, StudySettings

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None, study_settings: StudySettings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings if settings is not None else Settings()
        resolved_study = study_settings if study_settings is not None else StudySettings()
        database = Database(resolved_study.database)
        database.migrate()
        app.state.study_settings = resolved_study
        app.state.database = database
        app.state.study = StudyService(database, resolved_study.obsidian_dir)
        app.state.themes = ThemeService(resolved_study)
        app.state.polish_lock = Lock()
        async with httpx.AsyncClient() as client:
            app.state.model_client = client
            yield

    app = FastAPI(title="知径", lifespan=lifespan)
    spring.install(app)
    app.include_router(ai.router)
    app.include_router(study.router)
    app.include_router(themes.router)
    if (FRONTEND / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="study-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/courses", include_in_schema=False)
    def study_room():
        index = FRONTEND / "index.html"
        if not index.is_file():
            raise HTTPException(503, "请先运行 npm --prefix frontend run build")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
