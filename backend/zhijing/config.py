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
