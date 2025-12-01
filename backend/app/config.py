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

    # JWT settings
    SECRET_KEY: str = "pyarchinit-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Cloudinary settings (for image optimization)
    CLOUDINARY_CLOUD_NAME: str = "dkioeufik"
    CLOUDINARY_ENABLED: bool = True  # Set to False to use original storage server

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
