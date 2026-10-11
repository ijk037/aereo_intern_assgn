import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(String(36), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_format = Column(String(50), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    feature_count = Column(Integer, nullable=False, default=0)
    crs = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="PROCESSING")  # PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    features = relationship("FeatureRecord", back_populates="file_record", cascade="all, delete-orphan")


class FeatureRecord(Base):
    __tablename__ = "feature_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False)
    feature_identifier = Column(String(100), nullable=False)
    geometry_type = Column(String(50), nullable=False)
    geometry_geojson = Column(Text, nullable=True)
    properties_json = Column(Text, nullable=True)
    source_crs = Column(String(100), nullable=True)
    projected_crs = Column(String(100), nullable=True)
    
    measurement_type = Column(String(50), nullable=False)  # area, length, none, unsupported
    area_sq_meters = Column(Float, nullable=True)
    area_hectares = Column(Float, nullable=True)
    area_sq_km = Column(Float, nullable=True)
    length_meters = Column(Float, nullable=True)
    length_km = Column(Float, nullable=True)
    
    status = Column(String(50), nullable=False, default="SUCCESS")  # SUCCESS, SKIPPED, ERROR
    notes = Column(Text, nullable=True)

    file_record = relationship("FileRecord", back_populates="features")
