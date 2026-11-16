"""Shared FastAPI dependencies for the local-only study API."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from ..services.study import StudyService
from ..services.themes import ThemeService

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def require_local(request: Request, response: Response) -> None:
    """Reject non-loopback hosts and cross-site origins, and disable caching."""
    if request.url.hostname not in LOCAL_HOSTS:
        raise HTTPException(403, "自习室 API 只能通过本机地址访问")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "请从知径页面操作")
    response.headers["Cache-Control"] = "no-store"


def study_service(request: Request, _local: Annotated[None, Depends(require_local)]) -> StudyService:
    return request.app.state.study


def theme_service(request: Request, _local: Annotated[None, Depends(require_local)]) -> ThemeService:
    return request.app.state.themes


Study = Annotated[StudyService, Depends(study_service)]
Theme = Annotated[ThemeService, Depends(theme_service)]
