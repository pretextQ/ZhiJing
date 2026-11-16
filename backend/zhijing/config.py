from pathlib import Path
from typing import Annotated

from pydantic import Field, FiniteFloat, HttpUrl, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZHIJING_AI_", env_file=".env", extra="ignore"
    )

    base_url: HttpUrl | None = None
    model: str = ""
    api_key: SecretStr = SecretStr("")
    max_tokens: PositiveInt = 8192
    temperature: FiniteFloat = 0.4
    round_timeout: Annotated[FiniteFloat, Field(gt=0)] = 270
    min_chunk_time: Annotated[FiniteFloat, Field(ge=0)] = 30


class StudySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZHIJING_STUDY_", env_file=".env", extra="ignore", env_ignore_empty=True
    )

    database: Path = Path(".data/study.sqlite3")
    obsidian_dir: Path | None = None
    theme_dir: Path | None = None
    theme_max_archive_mb: PositiveInt = 32
    theme_max_expanded_mb: PositiveInt = 64
    theme_max_entries: PositiveInt = 32
