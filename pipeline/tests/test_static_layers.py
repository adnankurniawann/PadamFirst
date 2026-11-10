import geopandas
import h3
import numpy as np
import pandas as pd
import pytest
import rasterio
import shapely
from rasterio.transform import from_bounds
from sqlalchemy import text

from padamfirst.ingest import static_layers as sl

CENTER = h3.latlng_to_cell(-3.0, 105.0, 7)
CENTER_LAT, CENTER_LON = h3.cell_to_latlng(CENTER)
# Sel yang seluruhnya di barat 104.95, area nodata WorldPop di test.
WEST = h3.latlng_to_cell(-3.0, 104.92, 7)
RING = sorted(h3.grid_disk(CENTER, 1))
EAST = max(RING, key=lambda cell: h3.cell_to_latlng(cell)[1])
BOUNDS = (104.9, -3.1, 105.1, -2.9)


def write_tif(path, array, bounds, nodata=None):
    height, width = array.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=array.dtype,
        crs="EPSG:4326",
        transform=from_bounds(*bounds, width, height),
        nodata=nodata,
    ) as dst:
        dst.write(array, 1)
    return path


def lon_grid(bounds, resolution):
    width = round((bounds[2] - bounds[0]) / resolution)
    height = round((bounds[3] - bounds[1]) / resolution)
    lons = bounds[0] + (np.arange(width) + 0.5) * resolution
    return np.broadcast_to(lons, (height, width))


def test_archive_cells_dedupes_points(tmp_path):
    path = tmp_path / "2015.csv"
    path.write_text(
        "latitude,longitude,bright_ti4,confidence\n"
        "-3.0,105.0,330.1,n\n-3.0,105.0,331.0,h\n-3.0001,105.0001,331.0,l\n0.5,110.0,340,h\n"
    )
    assert sl.archive_cells([path]) == {CENTER, h3.latlng_to_cell(0.5, 110.0, 7)}


def test_study_cells_adds_ring_and_keeps_cells_touching_land():
    everywhere = shapely.box(100, -5, 110, 0)
    assert len(sl.study_cells({CENTER}, everywhere)) == 19

    tiny_island = shapely.Point(CENTER_LON, CENTER_LAT).buffer(0.001)
    assert sl.study_cells({CENTER}, tiny_island)["h3_index"].tolist() == [CENTER]


def test_population_and_peat(tmp_path):
    resolution = 0.001
    lons = lon_grid(BOUNDS, resolution)
    pop = np.where(lons < 104.95, -99999, 2.0).astype("float32")
    pop_path = write_tif(tmp_path / "pop.tif", pop, BOUNDS, nodata=-99999)
    # Gambut menutup semua yang di barat titik tengah sel CENTER.
    peat = geopandas.GeoSeries([shapely.box(104.9, -3.1, CENTER_LON, -2.9)])
    cells = sl.cell_polygons(RING + [WEST])

    # block kecil supaya sel terbelah ke beberapa window.
    result = sl.population_and_peat(cells, pop_path, peat, block=64)
    result.index = cells["h3_index"]

    pixel_km2 = (resolution * 111.32) ** 2 * np.cos(np.radians(-3.0))
    assert result.loc[CENTER, "pop_density"] == pytest.approx(2 / pixel_km2, rel=0.05)
    assert result.loc[WEST, "pop_density"] == 0
    assert result.loc[CENTER, "peat_pct"] == pytest.approx(50, abs=5)
    assert result.loc[WEST, "peat_pct"] == 100
    assert result.loc[EAST, "peat_pct"] == 0


def test_dominant_landcover_across_tiles(tmp_path):
    west_bounds = (104.9, -3.1, 105.0, -2.9)
    east_bounds = (105.0, -3.1, 105.1, -2.9)
    tiles = [
        write_tif(tmp_path / "w.tif", np.full((2000, 1000), 10, "uint8"), west_bounds, 0),
        write_tif(tmp_path / "e.tif", np.full((2000, 1000), 40, "uint8"), east_bounds, 0),
    ]
    outside = h3.latlng_to_cell(-3.0, 106.0, 7)
    cells = sl.cell_polygons([WEST, EAST, outside])

    result = sl.dominant_landcover(cells, tiles, pixels_per_degree=1000)
    result.index = cells["h3_index"]

    assert result[WEST] == "hutan"
    assert result[EAST] == "pertanian"
    assert pd.isna(result[outside])


def test_dominant_landcover_ignores_nodata(tmp_path):
    classes = np.zeros((2000, 2000), "uint8")
    classes[:, ::10] = 95
    # Nilai 0 adalah nodata di WorldCover.
    tile = write_tif(tmp_path / "t.tif", classes, BOUNDS, nodata=0)

    result = sl.dominant_landcover(sl.cell_polygons([CENTER]), [tile], pixels_per_degree=1000)
    assert result.tolist() == ["mangrove"]


@pytest.mark.parametrize("lat", [0.0, -10.0])
def test_nearest_km_matches_geodesic_distance(lat):
    cell = h3.latlng_to_cell(lat, 110.0, 7)
    cell_lat, cell_lon = h3.cell_to_latlng(cell)
    east = shapely.LineString([(cell_lon + 0.1, cell_lat - 1), (cell_lon + 0.1, cell_lat + 1)])
    north = shapely.LineString([(cell_lon - 1, cell_lat + 0.1), (cell_lon + 1, cell_lat + 0.1)])
    around = shapely.Point(cell_lon, cell_lat).buffer(0.01)
    cells = sl.cell_polygons([cell])

    def km(geom):
        return sl.nearest_km(cells, geopandas.GeoSeries([geom], crs="EPSG:4326"))[0]

    # Busur 0.1 derajat di elipsoid WGS84.
    assert km(east) == pytest.approx(11.132 * np.cos(np.radians(cell_lat)), abs=0.03)
    assert km(north) == pytest.approx(11.06, abs=0.03)
    assert km(around) == 0


def test_nearest_km_keeps_input_order():
    cells = sl.cell_polygons([h3.latlng_to_cell(0, lon, 7) for lon in (110.0, 110.5, 111.0)])
    road = geopandas.GeoSeries([shapely.LineString([(109.5, -1), (109.5, 1)])], crs="EPSG:4326")

    distance = pd.Series(sl.nearest_km(cells, road), index=cells["h3_index"])
    expected = cells["h3_index"].map(lambda cell: h3.cell_to_latlng(cell)[1] - 109.5) * 111.32
    np.testing.assert_allclose(distance, expected, atol=0.05)


def test_assign_admin_uses_nearest_region_for_sea_centroids():
    admin = geopandas.GeoDataFrame(
        {"adm1_name": ["P1", "P2"], "adm2_name": ["R1", "R2"]},
        geometry=[shapely.box(100, -1, 101, 1), shapely.box(101, -1, 102, 1)],
        crs="EPSG:4326",
    )
    # Dua sel terakhir centroidnya di luar kedua kotak.
    region_of = {
        h3.latlng_to_cell(0, lon, 7): region
        for lon, region in [(101.5, "2"), (100.5, "1"), (102.3, "2"), (99.7, "1")]
    }
    cells = sl.cell_polygons(region_of)

    result = sl.assign_admin(cells, admin)

    wanted = cells["h3_index"].map(region_of)
    assert result["regency"].tolist() == ("R" + wanted).tolist()
    assert result["province"].tolist() == ("P" + wanted).tolist()


OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="0.0" lon="110.0"/><node id="2" lat="0.0" lon="110.1"/>
  <node id="3" lat="0.1" lon="110.0"/><node id="4" lat="0.1" lon="110.1"/>
  <node id="5" lat="0.2" lon="110.0"/><node id="6" lat="0.2" lon="110.1"/>
  <node id="7" lat="0.3" lon="110.0"/><node id="8" lat="0.3" lon="110.1"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/></way>
  <way id="11"><nd ref="3"/><nd ref="4"/><tag k="highway" v="footway"/></way>
  <way id="12"><nd ref="5"/><nd ref="6"/><tag k="highway" v="track"/></way>
  <way id="20"><nd ref="1"/><nd ref="2"/><nd ref="4"/><nd ref="3"/><nd ref="1"/>
    <tag k="landuse" v="orchard"/><tag k="trees" v="oil_palms"/></way>
  <way id="21"><nd ref="3"/><nd ref="4"/><nd ref="6"/><nd ref="5"/><nd ref="3"/>
    <tag k="landuse" v="farmland"/><tag k="crop" v="rice"/></way>
  <way id="22"><nd ref="5"/><nd ref="6"/><nd ref="8"/><nd ref="7"/><nd ref="5"/>
    <tag k="landuse" v="farmland"/><tag k="produce" v="palm_oil"/></way>
</osm>
"""


def test_load_osm_filters_roads_and_plantations(tmp_path):
    path = tmp_path / "tiny.osm"
    path.write_text(OSM_XML)

    roads = sl.load_osm(path, "lines", f"highway IN {sl.ROAD_TYPES}")
    plantations = sl.load_osm(path, "multipolygons", sl.PLANTATION_WHERE)

    assert sorted(round(geom.coords[0][1], 1) for geom in roads) == [0.0, 0.2]
    # Kebun sawit dan farmland sawit masuk, sawah tidak.
    assert sorted(round(geom.bounds[1], 1) for geom in plantations) == [0.0, 0.2]


@pytest.fixture
def clean_static(engine):
    def truncate():
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE cell_static"))

    truncate()
    yield
    truncate()


def test_write_table_saves_parquet_and_upserts(engine, clean_static, tmp_path):
    table = pd.DataFrame(
        {
            "h3_index": [CENTER, EAST],
            "peat_pct": [50.0, np.nan],
            "peat_depth_cm": [np.nan, np.nan],
            "landcover_class": ["hutan", None],
            "pop_density": [12.5, 0.0],
            "dist_road_km": [1.0, 2.0],
            "dist_plantation_km": [0.0, 3.5],
            "province": ["Sumatera Selatan"] * 2,
            "regency": ["Ogan Komering Ilir"] * 2,
        }
    )
    path = tmp_path / "processed/cell_static.parquet"

    sl.write_table(engine, table, path)
    table.loc[0, "pop_density"] = 20.0
    sl.write_table(engine, table, path)

    pd.testing.assert_frame_equal(pd.read_parquet(path), table)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT h3_index, peat_pct, landcover_class, pop_density FROM cell_static")
        ).all()
    assert sorted(map(tuple, rows)) == sorted(
        [(CENTER, 50.0, "hutan", 20.0), (EAST, None, None, 0.0)]
    )
