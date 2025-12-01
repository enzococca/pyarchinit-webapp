"""
Configuration settings for PyArchInit Web App
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/pyarchinit"

    # Storage server URL (for media files)
    STORAGE_SERVER_URL: str = "https://pyarchinit-storage-server.up.railway.app"
    STORAGE_API_KEY: str = ""

    # App settings
    APP_NAME: str = "PyArchInit Web Viewer"
    DEBUG: bool = False

    # CORS origins
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
