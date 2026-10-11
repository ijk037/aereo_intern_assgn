import io
import os
import zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point


def generate_kml_sample(output_path: Path):
    """
    Generates a valid KML file with Polygon, LineString, and Point placemarks.
    """
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Sample Geospatial Survey</name>
    <description>Demonstration KML with mixed geometries for measurement evaluation</description>
    
    <!-- Polygon 1: Agricultural Plot A (Bangalore, India) -->
    <Placemark>
      <name>Plot Alpha (Polygon)</name>
      <description>Agricultural land parcel</description>
      <ExtendedData>
        <Data name="zone"><value>Agricultural</value></Data>
        <Data name="owner"><value>Farmer Green</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.5950,12.9700,0
              77.5950,12.9750,0
              77.5900,12.9750,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- LineString 1: Access Road / Pathway -->
    <Placemark>
      <name>Canal Pathway (LineString)</name>
      <description>Water irrigation canal boundary line</description>
      <ExtendedData>
        <Data name="type"><value>Irrigation Canal</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5850,12.9650,0
          77.5900,12.9700,0
          77.5950,12.9720,0
          77.6000,12.9750,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Point 1: Weather Monitoring Station -->
    <Placemark>
      <name>Weather Station (Point)</name>
      <description>IoT telemetry sensor pole</description>
      <ExtendedData>
        <Data name="sensor_id"><value>WS-902</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5925,12.9725,15</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Generated KML sample at: {output_path}")


def generate_shapefile_sample(zip_output_path: Path):
    """
    Generates a valid zipped Shapefile (.shp, .shx, .dbf, .prj)
    with Polygons, using EPSG:4326.
    """
    # Create GeoDataFrame with land parcels
    data = {
        "parcel_id": ["P-101", "P-102", "P-103"],
        "zoning": ["Residential", "Commercial", "Park"],
        "geometry": [
            Polygon([(77.580, 12.960), (77.585, 12.960), (77.585, 12.965), (77.580, 12.965), (77.580, 12.960)]),
            Polygon([(77.585, 12.960), (77.590, 12.960), (77.590, 12.965), (77.585, 12.965), (77.585, 12.960)]),
            Polygon([(77.580, 12.965), (77.590, 12.965), (77.590, 12.970), (77.580, 12.970), (77.580, 12.965)]),
        ],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

    temp_shp_dir = zip_output_path.parent / "temp_shp"
    temp_shp_dir.mkdir(parents=True, exist_ok=True)
    shp_path = temp_shp_dir / "parcels.shp"

    gdf.to_file(shp_path, driver="ESRI Shapefile")

    # Zip all components (.shp, .shx, .dbf, .prj, .cpg)
    zip_output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in temp_shp_dir.glob("parcels.*"):
            zf.write(file, arcname=file.name)

    # Clean up temporary shapefile components
    for file in temp_shp_dir.glob("parcels.*"):
        file.unlink()
    temp_shp_dir.rmdir()

    print(f"Generated Shapefile zip sample at: {zip_output_path}")


if __name__ == "__main__":
    base = Path(__file__).parent
    generate_kml_sample(base / "sample_survey.kml")
    generate_shapefile_sample(base / "sample_parcels.zip")
