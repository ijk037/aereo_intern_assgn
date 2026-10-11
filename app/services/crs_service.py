import logging
import math
from typing import Optional, Union, Tuple
import numpy as np
import pyproj
import shapely
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class CRSService:
    """
    Handles Coordinate Reference System (CRS) inspection, UTM zone determination,
    and geometric transformations from geographic (angular) to projected (metric) systems.
    """

    @staticmethod
    def parse_crs_string(crs_input: Union[str, int, dict, None]) -> Optional[str]:
        """
        Normalizes any CRS input (int, EPSG string, dict, or WKT) into a standard EPSG string.
        """
        if not crs_input:
            return None
        
        try:
            crs_obj = pyproj.CRS.from_user_input(crs_input)
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            # If no EPSG code exists, return the authority name or standard string representation
            auth = crs_obj.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            return crs_obj.name or "UNKNOWN_CRS"
        except Exception as e:
            logger.warning("Failed to parse CRS '%s': %s", crs_input, e)
            return str(crs_input)

    @classmethod
    def is_geographic(cls, crs_str: Optional[str]) -> bool:
        """
        Returns True if the CRS uses angular units (e.g. degrees, like EPSG:4326),
        meaning direct planar distance/area calculation would be erroneous.
        """
        if not crs_str:
            # Default assumption for unassigned GIS files is often WGS84
            return True

        try:
            crs_obj = pyproj.CRS.from_user_input(crs_str)
            return crs_obj.is_geographic
        except Exception:
            # If unable to parse, check for common geographic tokens
            lower_crs = crs_str.lower()
            return "4326" in lower_crs or "wgs84" in lower_crs or "geographic" in lower_crs or "deg" in lower_crs

    @classmethod
    def get_utm_epsg_for_lat_lon(cls, lat: float, lon: float) -> str:
        """
        Determines the optimal WGS84 UTM Zone EPSG code for a given latitude and longitude.
        Handles polar regions via Universal Polar Stereographic (UPS).
        """
        # Clamp longitude to [-180, 180]
        norm_lon = ((lon + 180) % 360) - 180

        # Polar regions
        if lat > 84.0:
            return "EPSG:32661"  # UPS North
        if lat < -80.0:
            return "EPSG:32761"  # UPS South

        # Standard UTM zones 1 through 60
        zone = int(math.floor((norm_lon + 180) / 6.0)) + 1
        zone = max(1, min(60, zone))

        if lat >= 0.0:
            epsg_code = 32600 + zone
        else:
            epsg_code = 32700 + zone

        return f"EPSG:{epsg_code}"

    @classmethod
    def get_optimal_projected_crs(cls, geometry: BaseGeometry, source_crs: Optional[str] = None) -> str:
        """
        Determines the optimal metric projected CRS for a geometry.
        - If already projected in meters, preserves the projected CRS.
        - If geographic or unspecified, calculates the local UTM zone based on the geometry's centroid.
        """
        # If source CRS is already projected in meters, check its units
        if source_crs and not cls.is_geographic(source_crs):
            try:
                crs_obj = pyproj.CRS.from_user_input(source_crs)
                axis_units = [axis.unit_name for axis in crs_obj.axis_info]
                if any("metre" in u.lower() or "meter" in u.lower() for u in axis_units):
                    epsg = crs_obj.to_epsg()
                    return f"EPSG:{epsg}" if epsg else source_crs
            except Exception as e:
                logger.debug("Could not verify projected axis units for %s: %s", source_crs, e)

        # Compute centroid to determine the optimal local UTM zone
        try:
            centroid = geometry.centroid
            lon, lat = centroid.x, centroid.y
            
            # If coordinates look geographic (lon in [-180, 180] and lat in [-90, 90])
            if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
                return cls.get_utm_epsg_for_lat_lon(lat=lat, lon=lon)
        except Exception as e:
            logger.warning("Failed to calculate geometry centroid for UTM zone: %s", e)

        # Fallback to World Mercator / Pseudo-Mercator if coordinates cannot determine UTM
        return "EPSG:3857"

    @classmethod
    def reproject_geometry(
        cls, geometry: BaseGeometry, source_crs: str, target_crs: str
    ) -> BaseGeometry:
        """
        Reprojects a Shapely geometry from source_crs to target_crs using PyProj.
        Uses Shapely 2.x vectorized coordinate transformations.
        """
        if source_crs == target_crs:
            return geometry

        src = pyproj.CRS.from_user_input(source_crs)
        tgt = pyproj.CRS.from_user_input(target_crs)
        
        transformer = pyproj.Transformer.from_crs(src, tgt, always_xy=True)

        def transform_coords(coords: np.ndarray) -> np.ndarray:
            x, y = transformer.transform(coords[:, 0], coords[:, 1])
            if coords.shape[1] > 2:
                return np.column_stack([x, y, coords[:, 2]])
            return np.column_stack([x, y])

        return shapely.transform(geometry, transform_coords)

    @classmethod
    def calculate_geodesic_measurements(
        cls, geometry: BaseGeometry
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculates ellipsoidal geodesic area and length using WGS84 ellipsoid via PyProj Geod
        (Karney's algorithm). Used for verification and high-precision reference.
        Returns: (area_sq_meters, length_meters)
        """
        geod = pyproj.Geod(ellps="WGS84")
        g_type = geometry.geom_type

        try:
            if g_type in ("Polygon", "MultiPolygon"):
                area, _ = geod.geometry_area_perimeter(geometry)
                return abs(float(area)), None
            elif g_type in ("LineString", "MultiLineString"):
                length = geod.geometry_length(geometry)
                return None, abs(float(length))
        except Exception as e:
            logger.debug("Geodesic calculation failed: %s", e)

        return None, None
