"""Pydantic models describing the public API request and response shapes."""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

MAX_SECONDS = 359999


class OpenLink(BaseModel):
    url: Annotated[str, Field(min_length=1, max_length=2048)]


class LessonUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    seconds: Annotated[int, Field(ge=0, le=MAX_SECONDS, strict=True)] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is not None:
            value = " ".join(value.split())
            if not value:
                raise ValueError("请输入课程名称")
        return value


class Revision(BaseModel):
    revision: Annotated[int, Field(ge=0, strict=True)]


class NoteUpdate(Revision):
    markdown: Annotated[str, Field(max_length=200_000)]


class LessonSummary(BaseModel):
    id: int
    title: str
    part: int
    seconds: int
    original_url: str
    embed_url: str | None


class Lesson(LessonSummary):
    markdown: str
    revision: int


class Room(BaseModel):
    lessons: list[LessonSummary]
    active: Lesson | None
    obsidian_enabled: bool


class ThemeCard(BaseModel):
    id: str
    name: str
    cover_url: str
    background_url: str
    ambient_url: str | None
    background_video_url: str | None


class ThemeLimits(BaseModel):
    max_archive_mb: int
    max_expanded_mb: int
    max_entries: int
