from datetime import date

import pandas as pd
import pytest

from padamfirst.features.cells import aggregate_hotspots, local_date


def test_local_date_keeps_night_pass_on_local_day():
    # 18:30 UTC di bujur 105 adalah 01:30 waktu setempat tanggal berikutnya.
    times = pd.Series(pd.to_datetime(["2026-11-10 18:30", "2026-11-10 06:30"], utc=True))
    assert local_date(times, pd.Series([105.0, 105.0])).tolist() == [
        date(2026, 11, 11),
        date(2026, 11, 10),
    ]


def test_aggregate_hotspots_per_cell_per_day():
    hotspots = pd.DataFrame(
        {
            "h3_index": ["a", "a", "a", "b"],
            "acq_datetime": pd.to_datetime(
                ["2026-11-10 06:00", "2026-11-10 07:00", "2026-11-11 06:00", "2026-11-10 06:00"],
                utc=True,
            ),
            "lon": [105.0] * 4,
            "frp": [10.0, 30.0, 5.0, 2.0],
            "confidence": ["high", "low", "nominal", "nominal"],
        }
    )
    result = aggregate_hotspots(hotspots).set_index(["h3_index", "date"])

    a = result.loc[("a", date(2026, 11, 10))]
    assert a["n_hotspots"] == 2
    assert a["frp_sum"] == 40.0
    assert a["frp_max"] == 30.0
    assert a["conf_mean"] == pytest.approx(0.5)
    assert len(result) == 3
