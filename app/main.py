import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import files, health
from app.core.config import settings
from app.core.exceptions import GeospatialAPIException
from app.db.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geospatial_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Application startup complete.")
    yield
    # Shutdown
    logger.info("Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
# Geospatial File Measurement API

A robust, production-ready backend service built with **FastAPI** to parse, inspect, and calculate high-precision geometric measurements for geospatial datasets.

### Capabilities:
* **Supported Formats**:
  * Shapefile (`.zip` containing `.shp`, `.dbf`, `.shx`, and optional `.prj`)
  * Keyhole Markup Language (`.kml`)
* **Intelligent CRS Reprojection**:
  * Automatically detects geographic coordinate systems (e.g., `EPSG:4326`)
  * Dynamically reprojects coordinates to the optimal local **Universal Transverse Mercator (UTM)** zone or metric projected coordinate system before calculating measurements.
  * Avoids erroneous calculations in angular degree units.
* **Geometric Measurements**:
  * **Polygons / MultiPolygons**: Area in square meters ($m^2$), hectares ($ha$), and square kilometers ($km^2$).
  * **LineStrings / MultiLineStrings**: Length in meters ($m$) and kilometers ($km$).
  * **Points / MultiPoints**: Gracefully skipped with explicit rationale.
  * **Unsupported / Invalid Geometries**: Handled gracefully without server errors.
* **Security & Reliability**:
  * Zip Slip path traversal mitigation.
  * Zip Bomb decompression limit checks.
  * Strict file size and MIME/extension validations.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(GeospatialAPIException)
async def geospatial_exception_handler(request: Request, exc: GeospatialAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."},
    )


# Include API routers
app.include_router(files.router, prefix=settings.API_PREFIX)
app.include_router(health.router)
