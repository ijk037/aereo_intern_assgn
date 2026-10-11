from typing import Any, Optional
from pydantic import BaseModel, Field


class AreaMeasurement(BaseModel):
    sq_meters: float = Field(..., description="Area in square meters (m²)")
    hectares: float = Field(..., description="Area in hectares (ha)")
    sq_km: float = Field(..., description="Area in square kilometers (km²)")


class LengthMeasurement(BaseModel):
    meters: float = Field(..., description="Length in meters (m)")
    km: float = Field(..., description="Length in kilometers (km)")


class FeatureMeasurementItem(BaseModel):
    feature_id: str
    feature_index: int
    geometry_type: str
    source_crs: Optional[str] = None
    projected_crs: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    measurement_type: str  # "area", "length", "none", "unsupported"
    area: Optional[AreaMeasurement] = None
    length: Optional[LengthMeasurement] = None
    status: str  # "SUCCESS", "SKIPPED", "ERROR"
    notes: Optional[str] = None


class MeasurementSummary(BaseModel):
    total_features: int
    polygon_count: int
    linestring_count: int
    point_count: int
    unsupported_count: int
    total_area_sq_meters: float
    total_length_meters: float


class FileMeasurementsResponse(BaseModel):
    id: str
    filename: str
    crs: Optional[str]
    status: str
    summary: MeasurementSummary
    measurements: list[FeatureMeasurementItem]
