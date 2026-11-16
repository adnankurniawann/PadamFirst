import csv
import io

from tests.conftest import DAY, HOT, MILD


def test_priorities_sorted_with_summary(client):
    body = client.get("/api/priorities?limit=50").json()
    assert body["date"] == DAY
    assert [item["h3_index"] for item in body["items"]] == [HOT, MILD]
    assert [item["rank"] for item in body["items"]] == [1, 2]
    assert body["summary"] == {"merah": 1, "oranye": 0, "kuning": 0, "hijau": 1}


def test_priorities_limit_and_province(client):
    assert len(client.get("/api/priorities?limit=1").json()["items"]) == 1
    riau = client.get("/api/priorities?province=Riau").json()
    assert [item["h3_index"] for item in riau["items"]] == [MILD]
    assert client.get("/api/priorities?limit=0").status_code == 422


def test_cells_is_valid_geojson_with_layer_value(client):
    body = client.get("/api/cells?layer=peat").json()
    assert body["type"] == "FeatureCollection"
    feature = next(f for f in body["features"] if f["properties"]["h3_index"] == HOT)
    ring = feature["geometry"]["coordinates"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert len(ring) == 7 and ring[0] == ring[-1]
    lon, lat = ring[0]
    assert 104 < lon < 107 and -4 < lat < -2
    assert feature["properties"]["value"] == 80


def test_cells_rejects_unknown_layer(client):
    assert client.get("/api/cells?layer=nope").status_code == 422


def test_layers_lists_fourteen(client):
    layers = client.get("/api/layers").json()
    assert len(layers) == 14
    assert {"priority", "confidence", "wind"} <= {layer["id"] for layer in layers}


def test_cell_detail_with_history(client):
    body = client.get(f"/api/cells/{HOT}").json()
    assert body["priority_class"] == "merah"
    assert body["regency"] == "Ogan Komering Ilir"
    assert [(h["date"], h["n_hotspots"]) for h in body["history"]] == [
        ("2026-11-10", 8),
        (DAY, 12),
    ]
    assert client.get("/api/cells/8f2830828052d25?date=2026-11-11").status_code == 404
    assert client.get("/api/cells/bukan-h3").status_code == 422


def test_hotspots_uses_local_date_and_bbox(client):
    body = client.get("/api/hotspots?bbox=105,-4,106,-3").json()
    times = sorted(f["properties"]["acq_datetime"] for f in body["features"])
    assert times == ["2026-11-10T18:30:00Z", "2026-11-11T06:00:00Z"]
    assert client.get("/api/hotspots?bbox=100,0,101,1").json()["features"] == []
    assert client.get("/api/hotspots?bbox=1,2,3").status_code == 422


def test_wind_one_vector_per_weather_point(client):
    vectors = client.get("/api/wind").json()["vectors"]
    assert sorted(v["wind_dir"] for v in vectors) == [90, 180]
    assert len(client.get("/api/wind?bbox=105,-4,106,-3").json()["vectors"]) == 1


def test_export_csv_has_all_rows(client):
    response = client.get("/api/export.csv")
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["h3_index"] for row in rows] == [HOT, MILD]
    assert rows[0]["province"] == "Sumatera Selatan"


def test_cors_allows_dashboard_origin(client):
    response = client.get("/api/layers", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
