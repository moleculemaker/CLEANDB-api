from typing import List

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API information
    PROJECT_NAME: str = "CLEAN Data API"
    DESCRIPTION: str = (
        "API for accessing enzyme EC number predictions from the CLEAN database. "
        "CLEAN (Contrastive Learning-Enabled Enzyme ANnotation) is a machine-learning "
        "tool that predicts enzyme function using contrastive learning on protein sequences. "
        "This API provides access to CLEAN-predicted EC numbers combined with UniProt protein "
        "annotations, enabling researchers to explore and download enzyme function predictions "
        "at scale."
    )
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
