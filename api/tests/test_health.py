def test_health_reports_latest_run_per_source(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert [(s["source"], s["status"], s["rows"]) for s in body["sources"]] == [
        ("VIIRS_NOAA20_NRT", "success", 5989)
    ]
