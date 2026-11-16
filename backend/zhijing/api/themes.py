"""Theme pack routes: request parsing plus thin calls into ThemeService."""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from ..domain.schemas import ThemeCard, ThemeLimits
from ..services.themes import PREFIX, content_disposition, size_text
from .deps import Theme

router = APIRouter(prefix=PREFIX, tags=["自习室"])


async def read_upload(request: Request, service: Theme) -> bytes:
    limit = service.max_archive_bytes
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, f"主题包不能超过 {size_text(limit)}")
    if not body:
        raise HTTPException(422, "主题包不能为空")
    return bytes(body)


@router.get("")
def list_themes(service: Theme) -> list[ThemeCard]:
    return service.cards()


@router.get("/limits")
def theme_limits(service: Theme) -> ThemeLimits:
    return service.limits()


@router.post("")
async def import_theme(request: Request, service: Theme) -> ThemeCard:
    return service.import_archive(await read_upload(request, service))


@router.patch("/{theme_id}")
def rename_theme(theme_id: str, payload: dict, service: Theme) -> ThemeCard:
    return service.rename(theme_id, payload.get("name"))


@router.get("/{theme_id}/export")
def export_theme(theme_id: str, service: Theme) -> Response:
    name, archive = service.export(theme_id)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": content_disposition(name),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{theme_id}", status_code=204)
def delete_theme(theme_id: str, service: Theme) -> None:
    service.delete(theme_id)


@router.get("/{theme_id}/assets/{asset_path:path}")
def theme_asset(theme_id: str, asset_path: str, service: Theme) -> FileResponse:
    target, kind = service.asset(theme_id, asset_path)
    return FileResponse(
        target,
        media_type=kind,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )
