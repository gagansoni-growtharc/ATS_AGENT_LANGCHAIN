from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
from functools import lru_cache

class Settings(BaseSettings):
    # Required fields
    MONGO_URI: str = Field(
        default="mongodb://localhost:27017/",
        description="MongoDB connection URI"
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key"
    )
    OUTPUT_DIR: Path = Field(
        default=Path("filtered_resumes"),
        description="Directory for filtered resumes"
    )   
    LOG_DB_NAME: str = Field(
        default="ats_agent",
        description="MongoDB database name for logs"
    )
    LOG_COLLECTION: str = Field(
        default="ats_logs",
        description="MongoDB collection name for logs"
    )
    CLEANUP_INTERVAL_HOURS: int = Field(
        default = 24,
        description="Default files life cycle"
    )


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    @field_validator("OUTPUT_DIR", mode="after")
    @classmethod
    def validate_dirs(cls, value: Path) -> Path:
        """Ensure directories exist and are absolute paths"""
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)
        return value.resolve()

@lru_cache()
def get_settings() -> Settings:
    return Settings()