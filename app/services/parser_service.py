import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry.base import BaseGeometry

from app.core.config import settings
from app.core.exceptions import CorruptFileException, InvalidFileFormatException
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


@dataclass
class ParsedFeature:
    feature_id: str
    feature_index: int
    geometry: Optional[BaseGeometry]
    geometry_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_crs: Optional[str] = None


@dataclass
class ParsedGeospatialData:
    crs: Optional[str]
    feature_count: int
    features: List[ParsedFeature]
    format: str


class ParserService:
    """
    Parses Shapefile (.zip) and KML geospatial files into structured feature data.
    Provides validation, Zip-Slip protection, and graceful error handling.
    """

    @classmethod
    def parse_file(cls, file_path: Path, filename: str) -> ParsedGeospatialData:
        lower_name = filename.lower()
        if lower_name.endswith(".zip"):
            return cls._parse_shapefile_zip(file_path)
        elif lower_name.endswith(".kml"):
            return cls._parse_kml(file_path)
        else:
            raise InvalidFileFormatException(
                f"Unsupported file format for '{filename}'. Allowed formats: .zip (Shapefile) or .kml."
            )

    @classmethod
    def _parse_shapefile_zip(cls, zip_path: Path) -> ParsedGeospatialData:
        """
        Extracts a .zip archive, verifies required Shapefile components (.shp, .dbf, .shx),
        and loads features.
        """
        extract_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
        try:
            cls._safe_extract_zip(zip_path, extract_dir)

            # Locate the .shp file(s)
            shp_files = list(extract_dir.rglob("*.shp"))
            if not shp_files:
                raise CorruptFileException(
                    "The provided zip archive does not contain a Shapefile (.shp file)."
                )

            # Pick the first valid shapefile found
            target_shp = shp_files[0]
            shp_stem = target_shp.stem
            parent_dir = target_shp.parent

            # Validate companion files: .shx and .dbf are required for a standard Shapefile
            dbf_file = parent_dir / f"{shp_stem}.dbf"
            shx_file = parent_dir / f"{shp_stem}.shx"
            prj_file = parent_dir / f"{shp_stem}.prj"

            if not dbf_file.exists():
                logger.warning("Shapefile companion .dbf file is missing for %s", target_shp.name)
            if not shx_file.exists():
                logger.warning("Shapefile companion .shx file is missing for %s", target_shp.name)

            has_prj = prj_file.exists()

            try:
                gdf = pyogrio.read_dataframe(str(target_shp))
            except Exception as e:
                # Fallback to geopandas read_file
                try:
                    gdf = gpd.read_file(str(target_shp))
                except Exception as ex:
                    raise CorruptFileException(f"Failed to read Shapefile: {str(ex)}") from ex

            detected_crs = None
            if gdf.crs is not None:
                detected_crs = CRSService.parse_crs_string(gdf.crs)
            elif not has_prj:
                # Shapefile missing .prj defaults to EPSG:4326 as standard GIS convention
                logger.warning("Shapefile has no .prj file. Assuming default EPSG:4326.")
                detected_crs = settings.DEFAULT_CRS
            else:
                detected_crs = settings.DEFAULT_CRS

            features = cls._extract_features_from_dataframe(gdf, detected_crs)

            return ParsedGeospatialData(
                crs=detected_crs,
                feature_count=len(features),
                features=features,
                format="shapefile",
            )

        finally:
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)

    @classmethod
    def _parse_kml(cls, kml_path: Path) -> ParsedGeospatialData:
        """
        Parses a KML file into features and standardizes CRS to EPSG:4326 (WGS 84).
        """
        try:
            gdf = pyogrio.read_dataframe(str(kml_path))
        except Exception as e:
            logger.info("pyogrio read failed for KML, attempting fallback via geopandas: %s", e)
            try:
                gdf = gpd.read_file(str(kml_path), driver="KML")
            except Exception as ex:
                raise CorruptFileException(f"Failed to parse KML file: {str(ex)}") from ex

        # Per OGC KML standard, coordinate reference system is always WGS84 (EPSG:4326)
        detected_crs = "EPSG:4326"
        if gdf.crs is not None:
            detected_crs = CRSService.parse_crs_string(gdf.crs) or "EPSG:4326"

        features = cls._extract_features_from_dataframe(gdf, detected_crs)

        return ParsedGeospatialData(
            crs=detected_crs,
            feature_count=len(features),
            features=features,
            format="kml",
        )

    @classmethod
    def _extract_features_from_dataframe(
        cls, gdf: gpd.GeoDataFrame, crs_str: Optional[str]
    ) -> List[ParsedFeature]:
        features: List[ParsedFeature] = []

        # List attribute column names (excluding geometry)
        attr_cols = [c for c in gdf.columns if c != "geometry"]

        for idx, row in gdf.iterrows():
            geom = row.get("geometry")
            geom_type = geom.geom_type if geom is not None and not geom.is_empty else "None"

            # Clean properties dictionary, converting non-serializable objects to strings
            props: Dict[str, Any] = {}
            for col in attr_cols:
                val = row.get(col)
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    continue
                # Format dates, timestamps, or complex objects
                if hasattr(val, "isoformat"):
                    props[str(col)] = val.isoformat()
                elif isinstance(val, (int, float, str, bool)):
                    props[str(col)] = val
                else:
                    props[str(col)] = str(val)

            feature_id = str(props.get("id") or props.get("FID") or props.get("Name") or f"feature_{idx}")

            features.append(
                ParsedFeature(
                    feature_id=feature_id,
                    feature_index=int(idx),
                    geometry=geom,
                    geometry_type=geom_type,
                    properties=props,
                    source_crs=crs_str,
                )
            )

        return features

    @classmethod
    def _safe_extract_zip(cls, zip_path: Path, target_dir: Path) -> None:
        """
        Safely extracts a ZIP archive with defenses against:
        - Directory traversal (Zip Slip vulnerability)
        - Decompression bombs (Zip Bomb vulnerability)
        """
        total_extracted_size = 0
        resolved_target = target_dir.resolve()

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                # Check for zip bomb
                total_extracted_size += member.file_size
                if total_extracted_size > settings.MAX_UNCOMPRESSED_ZIP_BYTES:
                    raise CorruptFileException(
                        f"Uncompressed archive size exceeds limit of "
                        f"{settings.MAX_UNCOMPRESSED_ZIP_BYTES / (1024 * 1024):.0f} MB."
                    )

                # Check for Zip Slip (directory traversal)
                dest_path = (target_dir / member.filename).resolve()
                if not str(dest_path).startswith(str(resolved_target)):
                    raise CorruptFileException(
                        f"Malicious archive entry detected (directory traversal): {member.filename}"
                    )

            # If all checks pass, extract all
            zf.extractall(target_dir)
