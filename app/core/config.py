import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Geospatial Measurement API")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_PREFIX: str = "/api"
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 50 * 1024 * 1024))
    MAX_UNCOMPRESSED_ZIP_BYTES: int = int(os.getenv("MAX_UNCOMPRESSED_ZIP_BYTES", 150 * 1024 * 1024))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./geospatial.db")
    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".zip", ".kml"})
    DEFAULT_CRS: str = os.getenv("DEFAULT_CRS", "EPSG:4326")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
