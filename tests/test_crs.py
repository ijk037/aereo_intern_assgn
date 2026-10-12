import pytest
from shapely.geometry import Polygon, LineString, Point
from app.services.crs_service import CRSService


def test_parse_crs_string():
    assert CRSService.parse_crs_string("EPSG:4326") == "EPSG:4326"
    assert CRSService.parse_crs_string(4326) == "EPSG:4326"
    assert CRSService.parse_crs_string("urn:ogc:def:crs:EPSG::4326") == "EPSG:4326"
    assert CRSService.parse_crs_string(None) is None


def test_is_geographic():
    assert CRSService.is_geographic("EPSG:4326") is True
    assert CRSService.is_geographic("EPSG:3857") is False
    assert CRSService.is_geographic("EPSG:32643") is False
    assert CRSService.is_geographic(None) is True


def test_utm_zone_determination():
    # Bangalore, India (lat ~12.97, lon ~77.59) -> UTM Zone 43N
    assert CRSService.get_utm_epsg_for_lat_lon(lat=12.97, lon=77.59) == "EPSG:32643"

    # Sydney, Australia (lat ~-33.86, lon ~151.20) -> UTM Zone 56S
    assert CRSService.get_utm_epsg_for_lat_lon(lat=-33.86, lon=151.20) == "EPSG:32756"

    # San Francisco, USA (lat ~37.77, lon ~-122.41) -> UTM Zone 10N
    assert CRSService.get_utm_epsg_for_lat_lon(lat=37.77, lon=-122.41) == "EPSG:32610"

    # Polar North
    assert CRSService.get_utm_epsg_for_lat_lon(lat=85.0, lon=10.0) == "EPSG:32661"

    # Polar South
    assert CRSService.get_utm_epsg_for_lat_lon(lat=-85.0, lon=10.0) == "EPSG:32761"


def test_geometry_reprojection():
    # 1 degree box at equator in EPSG:4326
    poly = Polygon([(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01), (0.0, 0.0)])
    target_crs = CRSService.get_optimal_projected_crs(poly, "EPSG:4326")
    assert target_crs == "EPSG:32631"

    reprojected = CRSService.reproject_geometry(poly, "EPSG:4326", target_crs)
    # Area of 0.01 degree at equator is approx (1113 m * 1113 m) ≈ 1,230,000 m²
    assert 1_000_000 < reprojected.area < 1_500_000
