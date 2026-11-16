"""Streaming polish route used by the note editor."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..legacy.spring import PolishRequest
from ..services.polish import polish_events

router = APIRouter(prefix="/api/ai")


@router.post(
    "/polish-stream",
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
