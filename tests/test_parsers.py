import pytest
from pathlib import Path
from app.services.parser_service import ParserService
from app.core.exceptions import InvalidFileFormatException, CorruptFileException


def test_parse_kml_file(sample_kml_path: Path):
    assert sample_kml_path.exists(), "Sample KML file must exist"
    data = ParserService.parse_file(sample_kml_path, sample_kml_path.name)
    assert data.format == "kml"
    assert data.feature_count == 3
    assert data.crs == "EPSG:4326"

    geom_types = [f.geometry_type for f in data.features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types


def test_parse_shapefile_zip(sample_shapefile_zip_path: Path):
    assert sample_shapefile_zip_path.exists(), "Sample Shapefile zip must exist"
    data = ParserService.parse_file(sample_shapefile_zip_path, sample_shapefile_zip_path.name)
    assert data.format == "shapefile"
    assert data.feature_count == 3
    assert data.crs == "EPSG:4326"

    for f in data.features:
        assert f.geometry_type == "Polygon"
        assert "parcel_id" in f.properties
        assert "zoning" in f.properties


def test_invalid_file_extension():
    fake_path = Path("test.csv")
    with pytest.raises(InvalidFileFormatException):
        ParserService.parse_file(fake_path, "test.csv")
