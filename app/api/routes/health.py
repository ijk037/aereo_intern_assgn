from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
import pyogrio

from app.api.deps import get_db_session
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
def health_check(db: Session = Depends(get_db_session)):
    # Check database
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check GDAL/pyogrio drivers
    drivers = pyogrio.list_drivers()
    shp_support = "ESRI Shapefile" in drivers
    kml_support = "KML" in drivers or "LIBKML" in drivers

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
        "drivers": {
            "shapefile": shp_support,
            "kml": kml_support,
        },
    }
