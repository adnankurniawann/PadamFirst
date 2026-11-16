import pandas as pd

from padamfirst.ingest.firms_archive import season_hotspots


def test_season_hotspots_keeps_vegetation_fires_june_to_november():
    raw = pd.DataFrame(
        {
            "latitude": [0.5, 0.5, 0.5, 0.5, 0.5],
            "longitude": [101.4] * 5,
            "acq_date": ["2019-05-31", "2019-06-01", "2019-11-30", "2019-12-01", "2019-09-10"],
            "acq_time": [600, 600, 1830, 600, 600],
            "satellite": ["N"] * 5,
            "instrument": ["VIIRS"] * 5,
            "confidence": ["n", "h", "l", "n", "n"],
            "frp": [1.0, 2.0, 3.0, 4.0, 5.0],
            "type": [0, 0, 0, 0, 2],
        }
    )

    result = season_hotspots(raw)

    assert result["frp"].tolist() == [2.0, 3.0]
    assert result["confidence"].tolist() == ["high", "low"]
