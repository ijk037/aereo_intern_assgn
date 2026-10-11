from typing import Any, Optional
from pydantic import BaseModel, Field


class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: Any


class FeatureItem(BaseModel):
    feature_id: str
    feature_index: int
    geometry_type: str
    geometry: Optional[GeoJSONGeometry] = None
    crs: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class FeatureCollectionResponse(BaseModel):
    file_id: str
    filename: str
    crs: Optional[str]
    features: list[FeatureItem]
