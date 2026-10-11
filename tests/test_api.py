import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["drivers"]["shapefile"] is True
    assert data["drivers"]["kml"] is True


def test_upload_and_measure_kml(client: TestClient, sample_kml_path: Path):
    with open(sample_kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )
    assert response.status_code == 201
    upload_data = response.json()
    file_id = upload_data["id"]
    assert upload_data["filename"] == sample_kml_path.name
    assert upload_data["feature_count"] == 3
    assert upload_data["crs"] == "EPSG:4326"
    assert upload_data["status"] == "COMPLETED"

    # Test GET /api/files/{id}/
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 3
    assert info_data["crs"] == "EPSG:4326"

    # Test GET /api/files/{id}/measurements/
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["id"] == file_id
    assert meas_data["summary"]["total_features"] == 3
    assert meas_data["summary"]["polygon_count"] == 1
    assert meas_data["summary"]["linestring_count"] == 1
    assert meas_data["summary"]["point_count"] == 1
    assert meas_data["summary"]["total_area_sq_meters"] > 0
    assert meas_data["summary"]["total_length_meters"] > 0

    measurements = meas_data["measurements"]
    assert len(measurements) == 3

    # Check Polygon measurement
    poly_item = next(m for m in measurements if m["geometry_type"] == "Polygon")
    assert poly_item["measurement_type"] == "area"
    assert poly_item["area"]["sq_meters"] > 0
    assert poly_item["area"]["hectares"] > 0
    assert poly_item["area"]["sq_km"] > 0
    assert poly_item["projected_crs"] == "EPSG:32643"  # UTM Zone 43N

    # Check LineString measurement
    line_item = next(m for m in measurements if m["geometry_type"] == "LineString")
    assert line_item["measurement_type"] == "length"
    assert line_item["length"]["meters"] > 0
    assert line_item["length"]["km"] > 0

    # Check Point measurement
    point_item = next(m for m in measurements if m["geometry_type"] == "Point")
    assert point_item["measurement_type"] == "none"
    assert point_item["status"] == "SKIPPED"
    assert point_item["area"] is None
    assert point_item["length"] is None

    # Test GET /api/files/{id}/features/
    feat_res = client.get(f"/api/files/{file_id}/features/")
    assert feat_res.status_code == 200
    feat_data = feat_res.json()
    assert len(feat_data["features"]) == 3
    assert feat_data["features"][0]["geometry"]["type"] in ("Polygon", "LineString", "Point")


def test_upload_and_measure_shapefile_zip(client: TestClient, sample_shapefile_zip_path: Path):
    with open(sample_shapefile_zip_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_shapefile_zip_path.name, f, "application/zip")},
        )
    assert response.status_code == 201
    upload_data = response.json()
    file_id = upload_data["id"]
    assert upload_data["feature_count"] == 3
    assert upload_data["status"] == "COMPLETED"

    # Test measurements
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["summary"]["polygon_count"] == 3
    assert meas_data["summary"]["total_area_sq_meters"] > 0


def test_list_files(client: TestClient, sample_kml_path: Path):
    with open(sample_kml_path, "rb") as f:
        client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )
    res = client.get("/api/files/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["files"]) >= 1


def test_delete_file(client: TestClient, sample_kml_path: Path):
    with open(sample_kml_path, "rb") as f:
        res = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = res.json()["id"]

    # Delete
    del_res = client.delete(f"/api/files/{file_id}/")
    assert del_res.status_code == 204

    # Verify 404 on get
    get_res = client.get(f"/api/files/{file_id}/")
    assert get_res.status_code == 404


def test_invalid_file_extension(client: TestClient):
    file_bytes = io.BytesIO(b"Hello world")
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", file_bytes, "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_nonexistent_file_404(client: TestClient):
    response = client.get("/api/files/nonexistent-id-999/")
    assert response.status_code == 404
