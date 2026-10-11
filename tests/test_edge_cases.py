import io
import zipfile
from pathlib import Path
import pytest
from shapely.geometry import Polygon, MultiPolygon, MultiLineString
from app.services.measurement_service import MeasurementService
from app.services.parser_service import ParserService
from app.core.exceptions import CorruptFileException


def test_bowtie_self_intersecting_polygon_make_valid():
    # Bowtie polygon (self-intersecting, invalid in standard topology)
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid

    result = MeasurementService.calculate_measurement(
        feature_id="bowtie_1",
        feature_index=0,
        geometry=bowtie,
        source_crs="EPSG:4326",
    )
    # Measurement service should automatically repair using shapely.make_valid and calculate area
    assert result.status == "SUCCESS"
    assert result.measurement_type == "area"
    assert result.area is not None
    assert result.area.sq_meters > 0


def test_multipolygon_measurement():
    poly1 = Polygon([(77.58, 12.96), (77.585, 12.96), (77.585, 12.965), (77.58, 12.965), (77.58, 12.96)])
    poly2 = Polygon([(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)])
    multipoly = MultiPolygon([poly1, poly2])

    result = MeasurementService.calculate_measurement(
        feature_id="multi_1",
        feature_index=0,
        geometry=multipoly,
        source_crs="EPSG:4326",
    )
    assert result.status == "SUCCESS"
    assert result.measurement_type == "area"
    assert result.area is not None
    assert result.area.sq_meters > 0


def test_multilinestring_measurement():
    multi_line = MultiLineString([
        [(77.58, 12.96), (77.585, 12.965)],
        [(77.59, 12.97), (77.595, 12.975)],
    ])
    result = MeasurementService.calculate_measurement(
        feature_id="multiline_1",
        feature_index=0,
        geometry=multi_line,
        source_crs="EPSG:4326",
    )
    assert result.status == "SUCCESS"
    assert result.measurement_type == "length"
    assert result.length is not None
    assert result.length.meters > 0


def test_zip_without_shp_raises_corrupt(tmp_path: Path):
    empty_zip = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty_zip, "w") as zf:
        zf.writestr("notes.txt", "No shapefile here")

    with pytest.raises(CorruptFileException) as exc_info:
        ParserService.parse_file(empty_zip, "empty.zip")
    assert "does not contain a Shapefile" in str(exc_info.value.detail)


def test_corrupt_zip_bytes(tmp_path: Path):
    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"PK\x03\x04randomcorruptdata")

    with pytest.raises(Exception):
        ParserService.parse_file(corrupt_zip, "corrupt.zip")
