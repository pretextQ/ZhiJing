"""Spring Boot compatible request and error protocol for the polish stream.

The original LearnHub backend was a Spring Boot service. The note editor still speaks
that protocol on POST /api/ai/polish-stream, so the request model, the
{code, msg, data} error envelope and the Jackson-style validation messages live here
until the frontend no longer depends on them. Do not add new behaviour to this module.
"""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ..services.markdown import JAVA_TRIM


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


async def validation_handler(request: Request, error: RequestValidationError) -> Response:
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


def install(app: FastAPI) -> None:
    """Install the legacy validation handler on the application."""
    app.add_exception_handler(RequestValidationError, validation_handler)
