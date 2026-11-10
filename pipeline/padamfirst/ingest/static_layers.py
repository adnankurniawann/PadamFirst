"""Hitung faktor statis per sel H3 ke tabel cell_static dan data/processed/cell_static.parquet.

python -m padamfirst.ingest.static_layers
"""

import argparse
import warnings
from pathlib import Path

import geopandas
import h3
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.windows import Window
from sqlalchemy import Engine, text

from padamfirst.config import H3_RESOLUTION
from padamfirst.db import get_engine, upsert
from padamfirst.ingest.firms import LAND_PATH, load_land

ROOT = Path(__file__).parents[3]
RAW = ROOT / "data/raw"
ARCHIVE_DIR = RAW / "firms_archive"
PEAT_PATH = RAW / "peat/W_R_MoA_IND_MYS_diss_WGS84.zip"
POP_PATH = RAW / "worldpop/idn_ppp_2020.tif"
WORLDCOVER_DIR = RAW / "worldcover"
OSM_PATH = RAW / "osm/indonesia-latest.osm.pbf"
OUTPUT_PATH = ROOT / "data/processed/cell_static.parquet"

RING = 2
# Mercator konformal, jadi jarak lokal benar setelah dikali cos(lintang).
MERCATOR = "EPSG:3395"
# Kode kelas ESA WorldCover v200.
LANDCOVER = {
    10: "hutan",
    20: "semak",
    30: "padang_rumput",
    40: "pertanian",
    50: "permukiman",
    60: "lahan_terbuka",
    70: "salju_es",
    80: "air",
    90: "lahan_basah",
    95: "mangrove",
    100: "lumut",
}
# Jalan yang bisa dilewati kendaraan, termasuk track kebun. Jalan setapak tidak dihitung.
ROAD_TYPES = (
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "track",
)
# OSM Indonesia hampir tidak memakai landuse=plantation. Kebun sawit, kelapa, dan karet ditandai
# orchard, sebagian kecil farmland dengan tag sawit. LIKE di OGR SQL tidak peka huruf besar.
PLANTATION_WHERE = (
    "landuse IN ('plantation', 'orchard') OR (landuse = 'farmland' AND other_tags LIKE '%palm%')"
)
COLUMNS = [
    "h3_index",
    "peat_pct",
    "peat_depth_cm",
    "landcover_class",
    "pop_density",
    "dist_road_km",
    "dist_plantation_km",
    "province",
    "regency",
]


def archive_cells(paths: list[Path]) -> set[str]:
    cells = set()
    for path in paths:
        points = pd.read_csv(path, usecols=["latitude", "longitude"])
        cells.update(
            h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            for lat, lon in zip(points["latitude"], points["longitude"], strict=True)
        )
    return cells


def cell_polygons(cells) -> geopandas.GeoDataFrame:
    cells = sorted(cells)
    polygons = [shapely.Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(c)]) for c in cells]
    return geopandas.GeoDataFrame({"h3_index": cells}, geometry=polygons, crs="EPSG:4326")


def study_cells(
    seeds: set[str], land: shapely.Geometry, ring: int = RING
) -> geopandas.GeoDataFrame:
    """Sel bertitik api plus ring di sekitarnya, dibatasi yang menyentuh daratan Indonesia."""
    disk = set().union(*(h3.grid_disk(cell, ring) for cell in seeds))
    cells = cell_polygons(disk)
    return cells[shapely.intersects(land, cells.geometry.values)].reset_index(drop=True)


def _cell_ids(cells, hit, transform, shape) -> np.ndarray:
    """Gambar sel ke grid. Nilai piksel = posisi baris sel + 1, 0 berarti bukan sel mana pun."""
    shapes = zip(cells.geometry.values[hit], (hit + 1).tolist(), strict=True)
    return rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="int32").ravel()


def population_and_peat(cells, pop_path: Path, peat: geopandas.GeoSeries, block: int = 4096):
    """Jumlah penduduk per km2 dan persen luas gambut, dihitung di grid WorldPop.

    Piksel masuk ke sel yang memuat titik tengahnya.
    """
    size = len(cells) + 1
    pixels, people, peat_pixels = np.zeros(size), np.zeros(size), np.zeros(size)
    with rasterio.open(pop_path) as src:
        for row in range(0, src.height, block):
            for col in range(0, src.width, block):
                window = Window(col, row, min(block, src.width - col), min(block, src.height - row))
                area = shapely.box(*src.window_bounds(window))
                hit = cells.sindex.query(area)
                if not len(hit):
                    continue
                transform = src.window_transform(window)
                shape = (window.height, window.width)
                ids = _cell_ids(cells, hit, transform, shape)

                values = src.read(1, window=window).ravel()
                # Nodata WorldPop bernilai negatif, NaN juga jadi 0 di sini.
                values = np.where(values > 0, values, 0)
                pixels += np.bincount(ids, minlength=size)
                people += np.bincount(ids, weights=values, minlength=size)

                parts = peat.values[peat.sindex.query(area)]
                if len(parts):
                    mask = rasterize(parts, out_shape=shape, transform=transform, dtype="uint8")
                    peat_pixels += np.bincount(ids, weights=mask.ravel(), minlength=size)

    area_km2 = np.array([h3.cell_area(cell, "km^2") for cell in cells["h3_index"]])
    with np.errstate(invalid="ignore", divide="ignore"):
        peat_pct = np.where(pixels[1:] > 0, 100 * peat_pixels[1:] / pixels[1:], np.nan)
    return pd.DataFrame({"pop_density": people[1:] / area_km2, "peat_pct": peat_pct})


def dominant_landcover(cells, tile_paths: list[Path], pixels_per_degree: int = 1200) -> pd.Series:
    """Kelas WorldCover paling banyak per sel, dibaca di resolusi kasar pakai resampling mode.

    1200 piksel per derajat sekitar 90 m, satu sel masih kebagian ratusan piksel.
    """
    codes = np.array(sorted(LANDCOVER))
    lookup = np.full(256, -1)
    lookup[codes] = np.arange(len(codes))
    size = len(cells) + 1
    counts = np.zeros(size * len(codes))

    for path in tile_paths:
        with rasterio.open(path) as src:
            hit = cells.sindex.query(shapely.box(*src.bounds))
            if not len(hit):
                continue
            left, bottom, right, top = src.bounds
            shape = (
                round((top - bottom) * pixels_per_degree),
                round((right - left) * pixels_per_degree),
            )
            classes = src.read(1, out_shape=shape, resampling=Resampling.mode).ravel()
        ids = _cell_ids(cells, hit, from_bounds(*src.bounds, shape[1], shape[0]), shape)
        index = lookup[classes]
        valid = (ids > 0) & (index >= 0)
        counts += np.bincount(ids[valid] * len(codes) + index[valid], minlength=counts.size)

    counts = counts.reshape(size, len(codes))[1:]
    labels = np.array([LANDCOVER[code] for code in codes], dtype=object)
    return pd.Series(np.where(counts.sum(1) > 0, labels[counts.argmax(1)], None))


def nearest_km(cells, targets: geopandas.GeoSeries) -> np.ndarray:
    """Jarak dari centroid sel ke geometri target terdekat, 0 kalau centroid di dalamnya."""
    lat, lon = np.array([h3.cell_to_latlng(cell) for cell in cells["h3_index"]]).T
    points = geopandas.GeoSeries.from_xy(lon, lat, crs="EPSG:4326").to_crs(MERCATOR)
    tree = shapely.STRtree(targets.to_crs(MERCATOR).values)
    # all_matches=False memberi tepat satu hasil per titik, urut sesuai titik input.
    _, distance = tree.query_nearest(points.values, all_matches=False, return_distance=True)
    return distance * np.cos(np.radians(lat)) / 1000


def assign_admin(cells, admin: geopandas.GeoDataFrame) -> pd.DataFrame:
    """Provinsi dan kabupaten dari centroid. Centroid di laut pakai wilayah terdekat."""
    lat, lon = np.array([h3.cell_to_latlng(cell) for cell in cells["h3_index"]]).T
    points = geopandas.GeoDataFrame(geometry=geopandas.points_from_xy(lon, lat), crs="EPSG:4326")
    regions = admin[["adm1_name", "adm2_name", "geometry"]]

    names = ["adm1_name", "adm2_name"]
    inside = points.sjoin(regions, predicate="within")[names]
    outside = points[~points.index.isin(inside.index)]
    if len(outside):
        nearest = outside.to_crs(MERCATOR).sjoin_nearest(regions.to_crs(MERCATOR))
        inside = pd.concat([inside, nearest[names]])

    # Titik tepat di perbatasan bisa cocok dua wilayah, ambil yang pertama.
    joined = inside[~inside.index.duplicated()].sort_index()
    return pd.DataFrame(
        {"province": joined["adm1_name"].to_numpy(), "regency": joined["adm2_name"].to_numpy()}
    )


def load_peat() -> geopandas.GeoSeries:
    # shortcut: peta cadangan tanpa kedalaman gambut, ganti ke BBSDLP kalau situsnya bisa diakses
    peat = geopandas.read_file(PEAT_PATH).geometry.force_2d().make_valid()
    parts = peat.explode(index_parts=False)
    return parts[parts.geom_type == "Polygon"].reset_index(drop=True)


def load_osm(path: Path, layer: str, where: str) -> geopandas.GeoSeries:
    # Indeks node OSM disimpan di memori sampai 2 GB supaya tidak lambat ke disk.
    frame = pyogrio.read_dataframe(
        path, layer=layer, columns=[], where=where, MAX_TMPFILE_SIZE=2000
    )
    return frame.geometry


def load_admin() -> geopandas.GeoDataFrame:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="organizePolygons")
        return geopandas.read_file(
            LAND_PATH, layer="idn_admin2", columns=["adm1_name", "adm2_name"]
        )


def build_table(cells, peat, tile_paths, roads, plantations, admin) -> pd.DataFrame:
    table = pd.concat(
        [
            cells[["h3_index"]],
            population_and_peat(cells, POP_PATH, peat),
            assign_admin(cells, admin),
        ],
        axis=1,
    )
    table["peat_depth_cm"] = np.nan
    table["landcover_class"] = dominant_landcover(cells, tile_paths)
    table["dist_road_km"] = nearest_km(cells, roads)
    table["dist_plantation_km"] = nearest_km(cells, plantations)
    return table[COLUMNS]


def write_table(engine: Engine, table: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=False)
    rows = table.astype(object).where(table.notna(), None).to_dict("records")
    with engine.begin() as conn:
        upsert(conn, "cell_static", rows, ("h3_index",))


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    engine = get_engine()

    with engine.connect() as conn:
        recent = set(conn.execute(text("SELECT DISTINCT h3_index FROM hotspots")).scalars())
    archives = sorted(ARCHIVE_DIR.glob("*.csv"))
    seeds = archive_cells(archives) | recent
    if not seeds:
        raise SystemExit(f"Tidak ada titik api, isi {ARCHIVE_DIR} atau jalankan ingest FIRMS dulu")

    cells = study_cells(seeds, load_land())
    print(f"{len(seeds)} sel bertitik api dari {len(archives)} arsip, {len(cells)} sel diproses")
    table = build_table(
        cells,
        load_peat(),
        sorted(WORLDCOVER_DIR.glob("*.tif")),
        load_osm(OSM_PATH, "lines", f"highway IN {ROAD_TYPES}"),
        load_osm(OSM_PATH, "multipolygons", PLANTATION_WHERE),
        load_admin(),
    )
    write_table(engine, table, OUTPUT_PATH)
    print(table.describe(include="all").T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
