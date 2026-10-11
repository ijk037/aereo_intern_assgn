import pytest
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, GeometryCollection
from app.services.measurement_service import MeasurementService


def test_polygon_measurement():
    # Square in Bangalore in EPSG:4326
    poly = Polygon([(77.590, 12.970), (77.595, 12.970), (77.595, 12.975), (77.590, 12.975), (77.590, 12.970)])
    result = MeasurementService.calculate_measurement(
        feature_id="poly_1",
        feature_index=0,
        geometry=poly,
        source_crs="EPSG:4326",
        properties={"parcel": "A"},
    )
    assert result.status == "SUCCESS"
    assert result.measurement_type == "area"
    assert result.area is not None
    assert result.area.sq_meters > 0
    assert result.area.hectares > 0
    assert result.area.sq_km > 0
    assert result.projected_crs == "EPSG:32643"
    assert result.length is None


def test_linestring_measurement():
    line = LineString([(77.585, 12.965), (77.590, 12.970), (77.595, 12.972)])
    result = MeasurementService.calculate_measurement(
        feature_id="line_1",
        feature_index=1,
        geometry=line,
        source_crs="EPSG:4326",
    )
    assert result.status == "SUCCESS"
    assert result.measurement_type == "length"
    assert result.length is not None
    assert result.length.meters > 0
    assert result.length.km > 0
    assert result.area is None


def test_point_measurement():
    point = Point(77.5925, 12.9725)
    result = MeasurementService.calculate_measurement(
        feature_id="pt_1",
        feature_index=2,
        geometry=point,
        source_crs="EPSG:4326",
    )
    assert result.status == "SKIPPED"
    assert result.measurement_type == "none"
    assert result.area is None
    assert result.length is None
    assert "Point geometries represent dimensionless coordinates" in result.notes


def test_unsupported_geometry():
    geom_col = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    result = MeasurementService.calculate_measurement(
        feature_id="col_1",
        feature_index=3,
        geometry=geom_col,
        source_crs="EPSG:4326",
    )
    assert result.status == "SKIPPED"
    assert result.measurement_type == "unsupported"
    assert result.area is None
    assert result.length is None


def test_empty_geometry():
    empty_poly = Polygon()
    result = MeasurementService.calculate_measurement(
        feature_id="empty_1",
        feature_index=4,
        geometry=empty_poly,
        source_crs="EPSG:4326",
    )
    assert result.status == "SKIPPED"
    assert "null or empty" in result.notes
