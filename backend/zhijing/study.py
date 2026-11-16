import hashlib
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time_ns
from typing import Annotated
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from .config import StudySettings

router = APIRouter(prefix="/api/study", tags=["自习室"])
MAX_SECONDS = 359999
VIDEO_PATH = re.compile(r"/video/(BV[a-zA-Z0-9]{10}|av[0-9]{1,16})/?")
COURSE_PATH = re.compile(r"/(?:cheese|bangumi)/play/(?:ep|ss)[0-9]{1,16}/?")
SITE = "https://www.bilibili.com"
PLAYER = "https://player.bilibili.com/player.html"


def read_number(value: str, lower: int, upper: int) -> int:
    if re.fullmatch(r"[0-9]{1,6}", value) and lower <= int(value) <= upper:
        return int(value)
    raise HTTPException(422, "请检查链接里的分 P 或起播时间")


def read_source(url: str) -> tuple[str, int, int | None]:
    try:
        parsed = urlsplit(url.strip())
    except ValueError as error:
        raise HTTPException(422, "链接格式不正确") from error
    if parsed.scheme not in {"https", "http"}:
        raise HTTPException(422, "请粘贴完整的 B 站视频链接")
    shared_params: dict[str, list[str]] = {}
    if parsed.netloc.lower() == "b23.tv" and re.fullmatch(r"/[a-zA-Z0-9]{1,32}/?", parsed.path):
        shared_params = parse_qs(parsed.query)
        try:
            response = httpx.get(f"https://b23.tv{parsed.path}", follow_redirects=False, timeout=5)
            if response.is_redirect and "location" in response.headers:
                parsed = urlsplit(response.headers["location"])
            else:
                raise HTTPException(422, "短链接未返回视频地址，请使用展开后的链接")
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(422, "短链接解析失败，请使用展开后的链接") from error
    if parsed.scheme not in {"https", "http"} or parsed.netloc.lower() not in {
        "www.bilibili.com", "m.bilibili.com", "bilibili.com",
    }:
        raise HTTPException(422, "请使用 B 站视频、课程或 b23.tv 分享链接")
    query = parse_qs(parsed.query) | shared_params
    video = VIDEO_PATH.fullmatch(parsed.path)
    if video:
        part = read_number(query.get("p", ["1"])[0], 1, 999999)
        seconds = read_number(query["t"][0], 0, MAX_SECONDS) if "t" in query else None
        return f"video/{video[1]}", part, seconds
    if COURSE_PATH.fullmatch(parsed.path):
        return parsed.path.strip("/"), 1, None
    raise HTTPException(422, "找不到视频编号，请打开视频后复制地址")


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


def lesson_summary(row: sqlite3.Row) -> LessonSummary:
    source, part = row["source"], row["part"]
    video = VIDEO_PATH.fullmatch(f"/{source}")
    original = f"{SITE}/{source}/"
    embed = None
    if video:
        video_id = video[1]
        identifier = {"bvid": video_id} if video_id.startswith("BV") else {"aid": video_id[2:]}
        embed = f"{PLAYER}?{urlencode(dict(identifier, p=part, danmaku=0, autoplay=0))}"
        original += f"?p={part}"
    return LessonSummary(
        id=row["id"], title=row["title"], part=part, seconds=row["seconds"],
        original_url=original, embed_url=embed,
    )


def as_lesson(row: sqlite3.Row) -> Lesson:
    return Lesson(**lesson_summary(row).model_dump(), markdown=row["markdown"], revision=row["revision"])


def selected(conn: sqlite3.Connection, lesson_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "找不到这节课")
    return row


def check_revision(row: sqlite3.Row, revision: int) -> None:
    if row["revision"] != revision:
        raise HTTPException(409, "这篇笔记已在另一窗口更新")


class StudyStore:
    def __init__(self, settings: StudySettings):
        self.database = settings.database
        self.obsidian_dir = settings.obsidian_dir

    @contextmanager
    def connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.row_factory = sqlite3.Row
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    part INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    seconds INTEGER NOT NULL DEFAULT 0,
                    opened_at INTEGER NOT NULL,
                    markdown TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 0,
                    export_path TEXT,
                    export_digest TEXT,
                    UNIQUE (source, part)
                )
            """)
            yield conn

    def room(self) -> Room:
        with self.connect() as conn:
            conn.execute("BEGIN")
            rows = conn.execute("""
                SELECT id, source, part, title, seconds FROM lessons ORDER BY opened_at DESC, id DESC
            """).fetchall()
            active = selected(conn, rows[0]["id"]) if rows else None
            return Room(
                lessons=[lesson_summary(row) for row in rows],
                active=as_lesson(active) if active is not None else None,
                obsidian_enabled=self.obsidian_dir is not None,
            )

    def open_link(self, payload: OpenLink) -> Lesson:
        source, part, seconds = read_source(payload.url)
        title = source.rsplit("/", 1)[-1]
        with self.connect() as conn:
            row = conn.execute("""
                INSERT INTO lessons (source, part, title, seconds, opened_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (source, part) DO UPDATE SET
                    opened_at = excluded.opened_at, seconds = coalesce(?, lessons.seconds)
                RETURNING *
            """, (source, part, title, seconds or 0, time_ns(), seconds)).fetchone()
            return as_lesson(row)

    def reopen(self, lesson_id: int) -> Lesson:
        with self.connect() as conn:
            row = conn.execute(
                "UPDATE lessons SET opened_at = ? WHERE id = ? RETURNING *", (time_ns(), lesson_id)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "找不到这节课")
            return as_lesson(row)

    def update(self, lesson_id: int, payload: LessonUpdate) -> LessonSummary:
        with self.connect() as conn:
            conn.execute("""
                UPDATE lessons SET title = coalesce(?, title), seconds = coalesce(?, seconds)
                WHERE id = ?
            """, (payload.title, payload.seconds, lesson_id))
            return lesson_summary(selected(conn, lesson_id))

    def lesson(self, lesson_id: int) -> Lesson:
        with self.connect() as conn:
            return as_lesson(selected(conn, lesson_id))

    def save_note(self, lesson_id: int, payload: NoteUpdate) -> Revision:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = selected(conn, lesson_id)
            if row["markdown"] == payload.markdown:
                return Revision(revision=row["revision"])
            check_revision(row, payload.revision)
            revision = row["revision"] + 1
            conn.execute(
                "UPDATE lessons SET markdown = ?, revision = ? WHERE id = ?",
                (payload.markdown, revision, lesson_id),
            )
            return Revision(revision=revision)

    def export(self, lesson_id: int, payload: Revision) -> str:
        if self.obsidian_dir is None:
            raise HTTPException(409, "请先在 .env 配置 Obsidian 目标目录")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = selected(conn, lesson_id)
            check_revision(row, payload.revision)
            lesson = lesson_summary(row)
            filename = f"B站-{row['source'].replace('/', '-')}-P{lesson.part}.md"
            data = f"# {lesson.title}\n\n[在 B 站打开]({lesson.original_url})\n\n{row['markdown']}\n".encode()
            digest = hashlib.sha256(data).hexdigest()
            try:
                directory = self.obsidian_dir.resolve(strict=True)
                target = directory / filename
                if target.is_symlink():
                    raise HTTPException(409, "目标文件是符号链接，请下载 Markdown")
                if target.exists():
                    current = hashlib.sha256(target.read_bytes()).hexdigest()
                    known = (row["export_path"], row["export_digest"])
                    if current != digest and known != (str(target), current):
                        raise HTTPException(409, "Obsidian 里已有不同内容，请先下载 Markdown 合并")
                    if current != digest:
                        write_markdown(target, data)
                else:
                    write_markdown(target, data)
            except OSError as error:
                raise HTTPException(409, "无法写入 Obsidian 目录，请检查路径和权限") from error
            conn.execute(
                "UPDATE lessons SET export_path = ?, export_digest = ? WHERE id = ?",
                (str(target), digest, lesson_id),
            )
            return filename


def write_markdown(target: Path, data: bytes) -> None:
    with NamedTemporaryFile(dir=target.parent, prefix=".zhijing-", delete=False) as draft:
        path = Path(draft.name)
        try:
            draft.write(data)
            draft.close()
            os.replace(path, target)
        finally:
            draft.close()
            path.unlink(missing_ok=True)


def store_for(request: Request, response: Response) -> StudyStore:
    if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(403, "自习室 API 只能通过本机地址访问")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "请从知径页面操作")
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.study


Store = Annotated[StudyStore, Depends(store_for)]


@router.get("")
def room(store: Store) -> Room:
    return store.room()


@router.post("/lessons")
def open_link(payload: OpenLink, store: Store) -> Lesson:
    return store.open_link(payload)


@router.post("/lessons/{lesson_id}/open")
def reopen(lesson_id: int, store: Store) -> Lesson:
    return store.reopen(lesson_id)


@router.patch("/lessons/{lesson_id}")
def update(lesson_id: int, payload: LessonUpdate, store: Store) -> LessonSummary:
    return store.update(lesson_id, payload)


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: int, store: Store) -> Lesson:
    return store.lesson(lesson_id)


@router.put("/lessons/{lesson_id}/note")
def save_note(lesson_id: int, payload: NoteUpdate, store: Store) -> Revision:
    return store.save_note(lesson_id, payload)


@router.post("/lessons/{lesson_id}/export")
def export(lesson_id: int, payload: Revision, store: Store) -> dict[str, str]:
    return {"filename": store.export(lesson_id, payload)}
