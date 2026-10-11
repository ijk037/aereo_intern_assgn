import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.exceptions import FileRecordNotFoundException
from app.db.models import FeatureRecord, FileRecord
from app.schemas.feature import FeatureCollectionResponse, FeatureItem, GeoJSONGeometry
from app.schemas.file import FileInfoResponse, FileListResponse, FileUploadResponse
from app.schemas.measurement import (
    AreaMeasurement,
    FeatureMeasurementItem,
    FileMeasurementsResponse,
    LengthMeasurement,
    MeasurementSummary,
)
from app.services.measurement_service import MeasurementService
from app.services.parser_service import ParserService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file (.zip Shapefile or .kml)",
    description="Accepts a zipped Shapefile or KML file, extracts features, detects CRS, and computes measurements.",
)
async def upload_file(
    file: UploadFile = File(..., description="Zipped Shapefile (.zip) or KML file (.kml)"),
    db: Session = Depends(get_db_session),
):
    # 1. Save uploaded file securely
    file_id, saved_path, file_size = await StorageService.save_upload(file)

    # 2. Create initial database record
    file_record = FileRecord(
        id=file_id,
        filename=file.filename or "unknown",
        file_format="shapefile" if file.filename and file.filename.lower().endswith(".zip") else "kml",
        file_path=str(saved_path),
        file_size_bytes=file_size,
        feature_count=0,
        crs=None,
        status="PROCESSING",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    try:
        # 3. Parse features from geospatial file
        parsed_data = ParserService.parse_file(saved_path, file_record.filename)

        # 4. Process each feature and calculate measurements
        feature_records: List[FeatureRecord] = []
        for feat in parsed_data.features:
            measurement = MeasurementService.calculate_measurement(
                feature_id=feat.feature_id,
                feature_index=feat.feature_index,
                geometry=feat.geometry,
                source_crs=feat.source_crs,
                properties=feat.properties,
            )

            geom_geojson = None
            if feat.geometry is not None and not feat.geometry.is_empty:
                import shapely
                geom_geojson = shapely.to_geojson(feat.geometry)

            feat_rec = FeatureRecord(
                file_id=file_id,
                feature_index=feat.feature_index,
                feature_identifier=feat.feature_id,
                geometry_type=feat.geometry_type,
                geometry_geojson=geom_geojson,
                properties_json=json.dumps(feat.properties),
                source_crs=feat.source_crs,
                projected_crs=measurement.projected_crs,
                measurement_type=measurement.measurement_type,
                area_sq_meters=measurement.area.sq_meters if measurement.area else None,
                area_hectares=measurement.area.hectares if measurement.area else None,
                area_sq_km=measurement.area.sq_km if measurement.area else None,
                length_meters=measurement.length.meters if measurement.length else None,
                length_km=measurement.length.km if measurement.length else None,
                status=measurement.status,
                notes=measurement.notes,
            )
            feature_records.append(feat_rec)

        db.bulk_save_objects(feature_records)

        # 5. Update file record to COMPLETED
        file_record.feature_count = parsed_data.feature_count
        file_record.crs = parsed_data.crs
        file_record.status = "COMPLETED"
        db.commit()
        db.refresh(file_record)

        logger.info(
            "Successfully processed file %s with %d features.",
            file_id,
            file_record.feature_count,
        )

        return file_record

    except Exception as e:
        logger.error("Processing failed for file %s: %s", file_id, e, exc_info=True)
        file_record.status = "FAILED"
        file_record.error_message = str(e)
        db.commit()
        raise


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded files",
)
def list_files(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Limit for pagination"),
    db: Session = Depends(get_db_session),
):
    total = db.query(FileRecord).count()
    records = db.query(FileRecord).order_by(FileRecord.created_at.desc()).offset(skip).limit(limit).all()
    return FileListResponse(
        total=total,
        files=[FileInfoResponse.model_validate(r) for r in records],
    )


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
    description="Returns metadata and processing status for an uploaded file.",
)
@router.get(
    "/{id}",
    response_model=FileInfoResponse,
    include_in_schema=False,
)
def get_file_info(id: str, db: Session = Depends(get_db_session)):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise FileRecordNotFoundException(id)
    return file_record


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get measurements for features in the file",
    description="Calculates and returns metric area, length, or skip notices for all features.",
)
@router.get(
    "/{id}/measurements",
    response_model=FileMeasurementsResponse,
    include_in_schema=False,
)
def get_file_measurements(id: str, db: Session = Depends(get_db_session)):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise FileRecordNotFoundException(id)

    features = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.file_id == id)
        .order_by(FeatureRecord.feature_index.asc())
        .all()
    )

    measurement_items: List[FeatureMeasurementItem] = []
    total_area = 0.0
    total_length = 0.0
    poly_count = 0
    line_count = 0
    point_count = 0
    unsupported_count = 0

    for feat in features:
        # Reconstruct Area
        area_obj = None
        if feat.area_sq_meters is not None:
            area_obj = AreaMeasurement(
                sq_meters=feat.area_sq_meters,
                hectares=feat.area_hectares or 0.0,
                sq_km=feat.area_sq_km or 0.0,
            )
            total_area += feat.area_sq_meters
            poly_count += 1

        # Reconstruct Length
        length_obj = None
        if feat.length_meters is not None:
            length_obj = LengthMeasurement(
                meters=feat.length_meters,
                km=feat.length_km or 0.0,
            )
            total_length += feat.length_meters
            line_count += 1

        if feat.geometry_type in ("Point", "MultiPoint"):
            point_count += 1
        elif feat.measurement_type == "unsupported":
            unsupported_count += 1

        props = {}
        if feat.properties_json:
            try:
                props = json.loads(feat.properties_json)
            except Exception:
                props = {}

        measurement_items.append(
            FeatureMeasurementItem(
                feature_id=feat.feature_identifier,
                feature_index=feat.feature_index,
                geometry_type=feat.geometry_type,
                source_crs=feat.source_crs,
                projected_crs=feat.projected_crs,
                properties=props,
                measurement_type=feat.measurement_type,
                area=area_obj,
                length=length_obj,
                status=feat.status,
                notes=feat.notes,
            )
        )

    summary = MeasurementSummary(
        total_features=len(features),
        polygon_count=poly_count,
        linestring_count=line_count,
        point_count=point_count,
        unsupported_count=unsupported_count,
        total_area_sq_meters=round(total_area, 4),
        total_length_meters=round(total_length, 4),
    )

    return FileMeasurementsResponse(
        id=file_record.id,
        filename=file_record.filename,
        crs=file_record.crs,
        status=file_record.status,
        summary=summary,
        measurements=measurement_items,
    )


@router.get(
    "/{id}/features/",
    response_model=FeatureCollectionResponse,
    summary="Get GeoJSON features for an uploaded file",
    description="Returns all features with their GeoJSON geometry and properties.",
)
@router.get(
    "/{id}/features",
    response_model=FeatureCollectionResponse,
    include_in_schema=False,
)
def get_file_features(id: str, db: Session = Depends(get_db_session)):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise FileRecordNotFoundException(id)

    features = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.file_id == id)
        .order_by(FeatureRecord.feature_index.asc())
        .all()
    )

    feature_items: List[FeatureItem] = []
    for feat in features:
        geom_obj = None
        if feat.geometry_geojson:
            try:
                raw_geom = json.loads(feat.geometry_geojson)
                geom_obj = GeoJSONGeometry(type=raw_geom.get("type", "Unknown"), coordinates=raw_geom.get("coordinates"))
            except Exception:
                geom_obj = None

        props = {}
        if feat.properties_json:
            try:
                props = json.loads(feat.properties_json)
            except Exception:
                props = {}

        feature_items.append(
            FeatureItem(
                feature_id=feat.feature_identifier,
                feature_index=feat.feature_index,
                geometry_type=feat.geometry_type,
                geometry=geom_obj,
                crs=feat.source_crs,
                properties=props,
            )
        )

    return FeatureCollectionResponse(
        file_id=file_record.id,
        filename=file_record.filename,
        crs=file_record.crs,
        features=feature_items,
    )


@router.delete(
    "/{id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded file and its measurements",
)
@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_file(id: str, db: Session = Depends(get_db_session)):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise FileRecordNotFoundException(id)

    # Remove file from disk
    if file_record.file_path:
        StorageService.remove_file(Path(file_record.file_path))

    db.delete(file_record)
    db.commit()
    return None
