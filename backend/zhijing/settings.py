"""Application settings loaded from environment variables and the optional .env file."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, FiniteFloat, HttpUrl, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Model provider settings (ZHIJING_AI_*)."""

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
    """Local study data settings (ZHIJING_STUDY_*)."""

    model_config = SettingsConfigDict(
        env_prefix="ZHIJING_STUDY_", env_file=".env", extra="ignore", env_ignore_empty=True
    )

    database: Path = Path(".data/study.sqlite3")
    data_dir: Path | None = None
    obsidian_dir: Path | None = None
    theme_dir: Path | None = None
    theme_max_archive_mb: PositiveInt = 32
    theme_max_expanded_mb: PositiveInt = 64
    theme_max_entries: PositiveInt = 32

    @property
    def data_root(self) -> Path:
        """Directory holding the database and application data files."""
        return self.data_dir if self.data_dir is not None else self.database.parent

    @property
    def theme_root(self) -> Path:
        """Directory holding imported theme packs."""
        return self.theme_dir if self.theme_dir is not None else self.data_root / "themes"

    @property
    def backup_root(self) -> Path:
        """Directory where backup archives are written by default."""
        return self.data_root / "backups"
