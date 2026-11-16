"""Course workspace routes: thin wrappers over StudyService."""

from fastapi import APIRouter

from ..domain.schemas import Lesson, LessonSummary, LessonUpdate, NoteUpdate, OpenLink, Revision, Room
from .deps import Study

router = APIRouter(prefix="/api/study", tags=["自习室"])


@router.get("")
def room(service: Study) -> Room:
    return service.room()


@router.post("/lessons")
def open_link(payload: OpenLink, service: Study) -> Lesson:
    return service.open_link(payload)


@router.post("/lessons/{lesson_id}/open")
def reopen(lesson_id: int, service: Study) -> Lesson:
    return service.reopen(lesson_id)


@router.patch("/lessons/{lesson_id}")
def update(lesson_id: int, payload: LessonUpdate, service: Study) -> LessonSummary:
    return service.update(lesson_id, payload)


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: int, service: Study) -> Lesson:
    return service.lesson(lesson_id)


@router.put("/lessons/{lesson_id}/note")
def save_note(lesson_id: int, payload: NoteUpdate, service: Study) -> Revision:
    return service.save_note(lesson_id, payload)


@router.post("/lessons/{lesson_id}/export")
def export(lesson_id: int, payload: Revision, service: Study) -> dict[str, str]:
    return {"filename": service.export(lesson_id, payload)}
