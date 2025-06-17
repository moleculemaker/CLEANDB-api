from typing import List

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API information
    PROJECT_NAME: str = "CLEAN Data API"
    DESCRIPTION: str = "API for accessing enzyme kinetic data from the CLEAN database"
    VERSION: str = "0.1.0"

    # API behavior configuration
    AUTO_PAGINATION_THRESHOLD: int = 5000

    # CORS configuration
    CORS_ORIGINS: List[str] = ["*"]

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
