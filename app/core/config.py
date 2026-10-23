from typing import List, Optional

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API information
    PROJECT_NAME: str = "CLEAN Data API"
    DESCRIPTION: str = "API for accessing enzyme function data from the CLEAN database"
    VERSION: str = "0.1.0"

    # API behavior configuration
    AUTO_PAGINATION_THRESHOLD: int = 5000

    # CORS configuration
    CORS_ORIGINS: List[str] = ["*"]

    # Matomo usage tracking; disabled unless MATOMO_SITE_ID is set
    MATOMO_URL: str = "https://matomo.mmli2.ncsa.illinois.edu"
    MATOMO_SITE_ID: Optional[int] = None
    # Token of a user with write access to the site; lets Matomo record the caller's IP
    MATOMO_TOKEN: Optional[str] = None

    @field_validator("MATOMO_SITE_ID", "MATOMO_TOKEN", mode="before")
    @classmethod
    def empty_is_unset(cls, value):
        """Treat MATOMO_SITE_ID= (as in .env.example) as unset instead of failing to start."""
        return None if value == "" else value

    # Database configuration
    CLEAN_DB_USER: str
    CLEAN_DB_PASSWORD: str
    CLEAN_DB_HOST: str
    CLEAN_DB_PORT: str = "5432"
    CLEAN_DB_NAME: str = "CLEAN_data"

    # Database connection string
    @property
    def DATABASE_URL(self) -> str:
        """Get database connection URL."""
        return f"postgresql+asyncpg://{self.CLEAN_DB_USER}:{self.CLEAN_DB_PASSWORD}@{self.CLEAN_DB_HOST}:{self.CLEAN_DB_PORT}/{self.CLEAN_DB_NAME}"

    # Use model_config instead of class Config
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# Create settings instance
settings = Settings()
