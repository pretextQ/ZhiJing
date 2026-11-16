import hashlib
import io
import json
import os
import re
import secrets
import shutil
import threading
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import mkdtemp, mkstemp
from urllib.parse import quote

from fastapi import HTTPException

from ..domain.schemas import ThemeCard, ThemeLimits
from ..settings import StudySettings

PREFIX = "/api/study/themes"
THEME_ID = re.compile(r"[0-9a-f]{12}")
STAGING_PREFIX = ".staging-"
TEMP_PREFIX = ".theme-"
DIGEST_NAME = ".archive-sha256"
MANIFEST_NAME = "theme.json"
MAX_NAME_LENGTH = 60
MAX_FILENAME_LENGTH = 60
FALLBACK_FILENAME = "theme"
MIB = 1024 * 1024

IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
VIDEO_TYPES = {"webm": "video/webm", "mp4": "video/mp4"}
AUDIO_TYPES = {"mp3": "audio/mpeg", "ogg": "audio/ogg"}
UNSUPPORTED_IMAGE_SUFFIXES = {"gif", "bmp", "svg", "avif"}
UNSUPPORTED_VIDEO_SUFFIXES = {"mov", "avi", "mkv", "flv", "m4v", "wmv"}
UNSUPPORTED_AUDIO_SUFFIXES = {"wav", "flac", "m4a", "aac"}


@dataclass(frozen=True)
class ThemeManifest:
    name: str
    background: str
    cover: str | None = None
    background_video: str | None = None
    ambient: str | None = None


def mib_to_bytes(megabytes: int) -> int:
    return megabytes * MIB


def size_text(size: int) -> str:
    if size and size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)} MiB"
    if size and size % 1024 == 0:
        return f"{size // 1024} KiB"
    return f"{size} B"


def fail(message: str) -> None:
    raise HTTPException(422, message)


def safe_path(value: str) -> str:
    """Return a relative archive path, rejecting anything that could escape the theme directory."""
    if not isinstance(value, str) or not value or "\x00" in value:
        fail("主题包内的文件路径为空或含有非法字符")
    if "\\" in value:
        fail(f"主题包内的文件路径不安全：{value}")
    if any(ord(char) < 32 for char in value):
        fail(f"主题包内的文件路径不安全：{value}")
    if value.startswith("/") or re.match(r"[A-Za-z]:", value):
        fail(f"主题包内的文件路径不安全：{value}")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        fail(f"主题包内的文件路径不安全：{value}")
    return value


def suffix_of(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def media_type(name: str) -> str:
    suffix = suffix_of(name)
    return (
        IMAGE_TYPES.get(suffix)
        or VIDEO_TYPES.get(suffix)
        or AUDIO_TYPES.get(suffix)
        or "application/octet-stream"
    )


def is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def image_matches(suffix: str, data: bytes) -> bool:
    if suffix == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {"jpg", "jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if suffix == "webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def video_matches(suffix: str, data: bytes) -> bool:
    if suffix == "webm":
        return data.startswith(b"\x1aE\xdf\xa3")
    if suffix == "mp4":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return False


def audio_matches(suffix: str, data: bytes) -> bool:
    if suffix == "mp3":
        if data.startswith(b"ID3"):
            return True
        return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
    if suffix == "ogg":
        return data.startswith(b"OggS")
    return False


def check_media(name: str, data: bytes) -> None:
    suffix = suffix_of(name)
    if suffix in IMAGE_TYPES:
        if not image_matches(suffix, data):
            fail(f"图片文件内容与扩展名不匹配：{name}")
        return
    if suffix in VIDEO_TYPES:
        if not video_matches(suffix, data):
            fail(f"视频文件内容与扩展名不匹配：{name}")
        return
    if suffix in AUDIO_TYPES:
        if not audio_matches(suffix, data):
            fail(f"音频文件内容与扩展名不匹配：{name}")
        return
    if suffix in UNSUPPORTED_IMAGE_SUFFIXES:
        fail(f"不支持的图片格式：{name}")
    if suffix in UNSUPPORTED_VIDEO_SUFFIXES:
        fail(f"不支持的视频格式：{name}")
    if suffix in UNSUPPORTED_AUDIO_SUFFIXES:
        fail(f"不支持的音频格式：{name}")
    fail(f"不支持的素材格式：{name}")


def parse_manifest(raw: bytes) -> ThemeManifest:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("theme.json 必须使用 UTF-8 编码")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        fail("theme.json 不是有效的 JSON")
    if not isinstance(data, dict):
        fail("theme.json 必须是 JSON 对象")

    version = data.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        fail("主题包清单版本不受支持，只支持 schemaVersion 1")

    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME_LENGTH:
        fail(f"主题包名称需要 1 到 {MAX_NAME_LENGTH} 个字符")
    name = name.strip()

    background = data.get("background")
    if not isinstance(background, str) or not background.strip():
        fail("主题包缺少背景图 background")
    background = safe_path(background.strip())

    references: dict[str, str] = {}
    for field, target in (("cover", "cover"), ("ambient", "ambient"), ("backgroundVideo", "background_video")):
        value = data.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            fail(f"主题包清单里的 {field} 必须是文件路径")
        references[target] = safe_path(value.strip())

    return ThemeManifest(name=name, background=background, **references)


def read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    try:
        return archive.read(info)
    except RuntimeError as error:
        if "password" in str(error).lower() or "encrypted" in str(error).lower():
            fail("主题包不能包含加密文件")
        fail("主题包内容损坏，无法读取")
    except (zipfile.BadZipFile, NotImplementedError, ValueError, OSError):
        fail("主题包内容损坏，无法读取")


def inspect_archive(data: bytes, *, max_entries: int, max_expanded_bytes: int) -> tuple[ThemeManifest, dict[str, bytes]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError):
        fail("主题包不是有效的 ZIP 文件")
    with archive:
        infos = archive.infolist()
        if len(infos) > max_entries:
            fail(f"主题包不能超过 {max_entries} 个文件")
        files: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for info in infos:
            if info.flag_bits & 0x1:
                fail("主题包不能包含加密文件")
            if is_symlink(info):
                fail("主题包不能包含符号链接")
            directory = info.filename.endswith("/")
            name = info.filename[:-1] if directory else info.filename
            safe_path(name)
            if directory:
                continue
            if name in files:
                fail(f"主题包里有重名文件：{name}")
            total += info.file_size
            if total > max_expanded_bytes:
                fail(f"主题包解压后不能超过 {size_text(max_expanded_bytes)}")
            files[name] = info

        if MANIFEST_NAME not in files:
            fail("主题包根目录缺少 theme.json")
        manifest = parse_manifest(read_entry(archive, files[MANIFEST_NAME]))

        payloads: dict[str, bytes] = {}
        for reference in (
            manifest.background,
            manifest.cover,
            manifest.background_video,
            manifest.ambient,
        ):
            if reference is None or reference in payloads:
                continue
            if reference not in files:
                fail(f"清单引用的文件不在主题包内：{reference}")
            content = read_entry(archive, files[reference])
            check_media(reference, content)
            payloads[reference] = content
        return manifest, payloads


def asset_url(theme_id: str, name: str) -> str:
    return f"{PREFIX}/{theme_id}/assets/{quote(name, safe='/')}"


def build_card(theme_id: str, manifest: ThemeManifest) -> ThemeCard:
    background = asset_url(theme_id, manifest.background)
    return ThemeCard(
        id=theme_id,
        name=manifest.name,
        cover_url=asset_url(theme_id, manifest.cover) if manifest.cover else background,
        background_url=background,
        ambient_url=asset_url(theme_id, manifest.ambient) if manifest.ambient else None,
        background_video_url=(
            asset_url(theme_id, manifest.background_video) if manifest.background_video else None
        ),
    )


def normalized_name(value: object) -> str:
    """Validate a user supplied theme name, returning the trimmed value."""
    if not isinstance(value, str):
        fail(f"主题名称需要 1 到 {MAX_NAME_LENGTH} 个字符")
    name = value.strip()
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        fail(f"主题名称需要 1 到 {MAX_NAME_LENGTH} 个字符")
    return name


def manifest_json(manifest: ThemeManifest) -> str:
    saved = {
        "schemaVersion": 1,
        "name": manifest.name,
        "background": manifest.background,
    }
    if manifest.cover is not None:
        saved["cover"] = manifest.cover
    if manifest.background_video is not None:
        saved["backgroundVideo"] = manifest.background_video
    if manifest.ambient is not None:
        saved["ambient"] = manifest.ambient
    return json.dumps(saved, ensure_ascii=False, indent=2) + "\n"


def write_manifest(directory: Path, manifest: ThemeManifest) -> None:
    """Atomically replace theme.json inside an existing theme directory."""
    descriptor, temporary = mkstemp(dir=directory, prefix=TEMP_PREFIX, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(manifest_json(manifest))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, directory / MANIFEST_NAME)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def ascii_download_name(name: str) -> str:
    """Build an ASCII fallback used inside the quoted Content-Disposition filename."""
    cleaned = "".join(
        char
        for char in name
        if 32 <= ord(char) < 127 and char not in {'"', "\\", "/", ":", "*", "?", "<", ">", "|"}
    )
    cleaned = cleaned.strip(" .")[:MAX_FILENAME_LENGTH].strip(" .")
    return cleaned or FALLBACK_FILENAME


def content_disposition(name: str) -> str:
    fallback = ascii_download_name(name)
    encoded = quote(f"{name}.zip", safe="")
    return f'attachment; filename="{fallback}.zip"; filename*=UTF-8\'\'{encoded}'


class ThemeService:
    """Imported theme pack library stored under the configured theme root."""

    def __init__(self, settings: StudySettings):
        self.root = settings.theme_root
        self.max_archive_mb = settings.theme_max_archive_mb
        self.max_expanded_mb = settings.theme_max_expanded_mb
        self.max_entries = settings.theme_max_entries
        self.max_archive_bytes = mib_to_bytes(self.max_archive_mb)
        self.max_expanded_bytes = mib_to_bytes(self.max_expanded_mb)
        self.lock = threading.Lock()

    def limits(self) -> ThemeLimits:
        return ThemeLimits(
            max_archive_mb=self.max_archive_mb,
            max_expanded_mb=self.max_expanded_mb,
            max_entries=self.max_entries,
        )

    def theme_directory(self, theme_id: str, message: str = "找不到这个主题") -> Path:
        if not THEME_ID.fullmatch(theme_id):
            raise HTTPException(404, message)
        directory = self.root / theme_id
        if directory.is_symlink() or not directory.is_dir():
            raise HTTPException(404, message)
        return directory

    def cards(self) -> list[ThemeCard]:
        with self.lock:
            if not self.root.is_dir():
                return []
            cards = []
            for directory in sorted(self.root.iterdir(), key=lambda path: path.name):
                if not THEME_ID.fullmatch(directory.name) or directory.is_symlink() or not directory.is_dir():
                    continue
                manifest = self.stored_manifest(directory)
                if manifest is not None:
                    cards.append(build_card(directory.name, manifest))
            return cards

    def stored_manifest(self, directory: Path) -> ThemeManifest | None:
        try:
            return parse_manifest((directory / MANIFEST_NAME).read_bytes())
        except (OSError, HTTPException):
            return None

    def existing(self, digest: str) -> ThemeCard | None:
        for directory in sorted(self.root.iterdir(), key=lambda path: path.name):
            if not THEME_ID.fullmatch(directory.name) or directory.is_symlink() or not directory.is_dir():
                continue
            try:
                stored = (directory / DIGEST_NAME).read_text(encoding="ascii").strip()
            except (OSError, UnicodeError):
                continue
            if stored != digest:
                continue
            manifest = self.stored_manifest(directory)
            if manifest is not None:
                return build_card(directory.name, manifest)
        return None

    def import_archive(self, data: bytes) -> ThemeCard:
        if len(data) > self.max_archive_bytes:
            raise HTTPException(413, f"主题包不能超过 {size_text(self.max_archive_bytes)}")
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            duplicate = self.existing(digest)
            if duplicate is not None:
                return duplicate
            staging = Path(mkdtemp(dir=self.root, prefix=STAGING_PREFIX))
            published = False
            try:
                manifest, payloads = inspect_archive(
                    data, max_entries=self.max_entries, max_expanded_bytes=self.max_expanded_bytes
                )
                for name, content in payloads.items():
                    destination = staging / name
                    if not destination.resolve().is_relative_to(staging.resolve()):
                        fail(f"主题包内的文件路径不安全：{name}")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                write_manifest(staging, manifest)
                (staging / DIGEST_NAME).write_text(digest + "\n", encoding="ascii")
                theme_id = self.fresh_id()
                os.replace(staging, self.root / theme_id)
                published = True
                return build_card(theme_id, manifest)
            finally:
                if not published:
                    shutil.rmtree(staging, ignore_errors=True)

    def fresh_id(self) -> str:
        while True:
            theme_id = secrets.token_hex(6)
            if not (self.root / theme_id).exists():
                return theme_id

    def rename(self, theme_id: str, value: object) -> ThemeCard:
        name = normalized_name(value)
        with self.lock:
            directory = self.theme_directory(theme_id)
            manifest = self.stored_manifest(directory)
            if manifest is None:
                raise HTTPException(404, "找不到这个主题")
            updated = replace(manifest, name=name)
            try:
                write_manifest(directory, updated)
            except OSError as error:
                raise HTTPException(409, "无法重命名主题，请检查主题目录的权限") from error
            return build_card(theme_id, updated)

    def export(self, theme_id: str) -> tuple[str, bytes]:
        with self.lock:
            directory = self.theme_directory(theme_id)
            manifest = self.stored_manifest(directory)
            if manifest is None:
                raise HTTPException(404, "找不到这个主题")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST_NAME, manifest_json(manifest))
                seen = {MANIFEST_NAME}
                for reference in (
                    manifest.background,
                    manifest.cover,
                    manifest.background_video,
                    manifest.ambient,
                ):
                    if reference is None or reference in seen:
                        continue
                    seen.add(reference)
                    target = directory / reference
                    if target.is_symlink() or not target.is_file():
                        raise HTTPException(409, f"主题素材缺失，无法导出：{reference}")
                    try:
                        content = target.read_bytes()
                    except OSError as error:
                        raise HTTPException(409, f"无法读取主题素材：{reference}") from error
                    archive.writestr(reference, content)
            return manifest.name, buffer.getvalue()

    def delete(self, theme_id: str) -> None:
        with self.lock:
            directory = self.theme_directory(theme_id)
            try:
                shutil.rmtree(directory)
            except OSError as error:
                raise HTTPException(409, "无法删除主题，请检查主题目录的权限") from error

    def asset(self, theme_id: str, asset_path: str) -> tuple[Path, str]:
        with self.lock:
            directory = self.theme_directory(theme_id, "找不到这个素材")
            manifest = self.stored_manifest(directory)
            if manifest is None:
                raise HTTPException(404, "找不到这个素材")
            allowed = {
                name: media_type(name)
                for name in (
                    manifest.background,
                    manifest.cover,
                    manifest.background_video,
                    manifest.ambient,
                )
                if name is not None
            }
            if asset_path not in allowed:
                raise HTTPException(404, "找不到这个素材")
            target = directory / asset_path
            if target.is_symlink() or not target.is_file():
                raise HTTPException(404, "找不到这个素材")
            return target, allowed[asset_path]
