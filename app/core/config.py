from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Geospatial Measurement API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    
    # Storage settings
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_UNCOMPRESSED_ZIP_BYTES: int = 150 * 1024 * 1024  # 150 MB (Zip Bomb protection)
    
    # Persistence
    DATABASE_URL: str = "sqlite:///./geospatial.db"
    
    # Supported file extensions
    ALLOWED_EXTENSIONS: set[str] = {".zip", ".kml"}
    
    # CRS defaults
    DEFAULT_CRS: str = "EPSG:4326"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
