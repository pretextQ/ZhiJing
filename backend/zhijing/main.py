from asyncio import Lock
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError

from .config import Settings, StudySettings
from .markdown import JAVA_TRIM
from .polish import polish_events
from .study import StudyStore, router as study_router

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class PolishRequest(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")

    text: str | None = None
    mode: str | None = "polish"

    @field_validator("text", "mode", mode="before")
    @classmethod
    def coerce_boolean(cls, value):
        # Jackson accepts scalar JSON values for Java String fields.
        return str(value).lower() if isinstance(value, bool) else value

    @model_validator(mode="after")
    def validate_text(self):
        if self.text is None or not self.text.strip(JAVA_TRIM):
            raise PydanticCustomError("blank_text", "内容不能为空")
        return self


def error_result(code: int, message: str, status: int = 200) -> JSONResponse:
    return JSONResponse({"code": code, "msg": message, "data": None}, status_code=status)


def create_app(settings: Settings | None = None, study_settings: StudySettings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings if settings is not None else Settings()
        app.state.study = StudyStore(study_settings if study_settings is not None else StudySettings())
        app.state.polish_lock = Lock()
        async with httpx.AsyncClient() as client:
            app.state.model_client = client
            yield

    app = FastAPI(title="知径", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        if request.url.path != "/api/ai/polish-stream":
            return await request_validation_exception_handler(request, error)
        problem = error.errors()[0]
        kind = problem["type"]
        if kind == "blank_text":
            return error_result(400, problem["msg"])
        if kind == "missing" or (kind == "model_attributes_type" and problem.get("input") is None):
            message = (
                "Required request body is missing: public "
                "org.springframework.web.servlet.mvc.method.annotation.SseEmitter "
                "org.dyh.learnhub.controller.AiController.polishStream(org.dyh.learnhub.dto.AiPolishRequest)"
            )
        elif kind == "json_invalid":
            message = "JSON parse error: " + problem.get("ctx", {}).get("error", "Invalid JSON")
        else:
            value = problem.get("input")
            target = "org.dyh.learnhub.dto.AiPolishRequest" if len(problem["loc"]) == 1 else "java.lang.String"
            if isinstance(value, (dict, list)):
                token, shape = ("START_OBJECT", "Object") if isinstance(value, dict) else ("START_ARRAY", "Array")
                message = f"JSON parse error: Cannot deserialize value of type `{target}` from {shape} value (token `JsonToken.{token}`)"
            else:
                message = f"JSON parse error: Expected a JSON object for `{target}`"
        return error_result(500, f"服务器内部错误: {message}", 500)

    @app.post(
        "/api/ai/polish-stream",
        responses={200: {"content": {"text/event-stream": {}, "application/json": {}}}},
    )
    async def polish_stream(payload: PolishRequest, request: Request):
        async def events():
            async with request.app.state.polish_lock:
                async for event in polish_events(
                    request.app.state.model_client, request.app.state.settings, payload.text, payload.mode
                ):
                    yield event

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(study_router)
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
