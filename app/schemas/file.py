import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: Optional[str]
    status: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class FileInfoResponse(BaseModel):
    id: str
    filename: str
    file_format: str
    feature_count: int
    crs: Optional[str]
    status: str
    file_size_bytes: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    total: int
    files: list[FileInfoResponse]
