import logging
from typing import Optional, Dict, Any
import shapely
from shapely.geometry.base import BaseGeometry

from app.schemas.measurement import (
    AreaMeasurement,
    LengthMeasurement,
    FeatureMeasurementItem,
)
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class MeasurementService:
    """
    Calculates metric measurements for geometries, ensuring re-projection from
    geographic coordinates to metric projected coordinates (such as UTM).
    Handles edge cases and unsupported geometries gracefully.
    """

    @classmethod
    def calculate_measurement(
        cls,
        feature_id: str,
        feature_index: int,
        geometry: Optional[BaseGeometry],
        source_crs: Optional[str],
        properties: Optional[Dict[str, Any]] = None,
    ) -> FeatureMeasurementItem:
        """
        Calculates area or length for a given feature geometry.
        Transforms to metric projected CRS if the source CRS is geographic.
        """
        props = properties or {}

        if geometry is None or geometry.is_empty:
            return FeatureMeasurementItem(
                feature_id=feature_id,
                feature_index=feature_index,
                geometry_type="None" if geometry is None else geometry.geom_type,
                source_crs=source_crs,
                projected_crs=None,
                properties=props,
                measurement_type="unsupported",
                status="SKIPPED",
                notes="Geometry is null or empty.",
            )

        geom_type = geometry.geom_type

        # Validate and fix minor topological self-intersections if necessary
        if not geometry.is_valid:
            try:
                geometry = shapely.make_valid(geometry)
                geom_type = geometry.geom_type
            except Exception as e:
                logger.warning("Failed to fix invalid geometry for feature %s: %s", feature_id, e)
                return FeatureMeasurementItem(
                    feature_id=feature_id,
                    feature_index=feature_index,
                    geometry_type=geom_type,
                    source_crs=source_crs,
                    projected_crs=None,
                    properties=props,
                    measurement_type="unsupported",
                    status="ERROR",
                    notes=f"Invalid geometry topology: {str(e)}",
                )

        # 1. Point / MultiPoint Handling
        if geom_type in ("Point", "MultiPoint"):
            return FeatureMeasurementItem(
                feature_id=feature_id,
                feature_index=feature_index,
                geometry_type=geom_type,
                source_crs=source_crs,
                projected_crs=None,
                properties=props,
                measurement_type="none",
                status="SKIPPED",
                notes="Point geometries represent dimensionless coordinates; area and length are not applicable.",
            )

        # 2. Polygon / MultiPolygon Handling
        if geom_type in ("Polygon", "MultiPolygon"):
            try:
                projected_crs = CRSService.get_optimal_projected_crs(geometry, source_crs)
                
                # If source is geographic, reproject to metric projected CRS (e.g. UTM)
                effective_src = source_crs or "EPSG:4326"
                if CRSService.is_geographic(effective_src):
                    proj_geom = CRSService.reproject_geometry(geometry, effective_src, projected_crs)
                else:
                    proj_geom = geometry
                    projected_crs = source_crs

                raw_area = float(proj_geom.area)
                area_sq_m = round(raw_area, 4)
                hectares = round(raw_area / 10000.0, 6)
                sq_km = round(raw_area / 1000000.0, 8)

                return FeatureMeasurementItem(
                    feature_id=feature_id,
                    feature_index=feature_index,
                    geometry_type=geom_type,
                    source_crs=source_crs,
                    projected_crs=projected_crs,
                    properties=props,
                    measurement_type="area",
                    area=AreaMeasurement(
                        sq_meters=area_sq_m,
                        hectares=hectares,
                        sq_km=sq_km,
                    ),
                    status="SUCCESS",
                )
            except Exception as e:
                logger.error("Error calculating area for feature %s: %s", feature_id, e, exc_info=True)
                return FeatureMeasurementItem(
                    feature_id=feature_id,
                    feature_index=feature_index,
                    geometry_type=geom_type,
                    source_crs=source_crs,
                    projected_crs=None,
                    properties=props,
                    measurement_type="area",
                    status="ERROR",
                    notes=f"Failed to calculate area: {str(e)}",
                )

        # 3. LineString / MultiLineString Handling
        if geom_type in ("LineString", "MultiLineString", "LinearRing"):
            try:
                projected_crs = CRSService.get_optimal_projected_crs(geometry, source_crs)
                effective_src = source_crs or "EPSG:4326"

                if CRSService.is_geographic(effective_src):
                    proj_geom = CRSService.reproject_geometry(geometry, effective_src, projected_crs)
                else:
                    proj_geom = geometry
                    projected_crs = source_crs

                raw_length = float(proj_geom.length)
                length_m = round(raw_length, 4)
                length_km = round(raw_length / 1000.0, 6)

                return FeatureMeasurementItem(
                    feature_id=feature_id,
                    feature_index=feature_index,
                    geometry_type=geom_type,
                    source_crs=source_crs,
                    projected_crs=projected_crs,
                    properties=props,
                    measurement_type="length",
                    length=LengthMeasurement(
                        meters=length_m,
                        km=length_km,
                    ),
                    status="SUCCESS",
                )
            except Exception as e:
                logger.error("Error calculating length for feature %s: %s", feature_id, e, exc_info=True)
                return FeatureMeasurementItem(
                    feature_id=feature_id,
                    feature_index=feature_index,
                    geometry_type=geom_type,
                    source_crs=source_crs,
                    projected_crs=None,
                    properties=props,
                    measurement_type="length",
                    status="ERROR",
                    notes=f"Failed to calculate length: {str(e)}",
                )

        # 4. GeometryCollection or Other Unsupported Types
        return FeatureMeasurementItem(
            feature_id=feature_id,
            feature_index=feature_index,
            geometry_type=geom_type,
            source_crs=source_crs,
            projected_crs=None,
            properties=props,
            measurement_type="unsupported",
            status="SKIPPED",
            notes=f"Geometry type '{geom_type}' is not supported for standard planar measurement.",
        )
