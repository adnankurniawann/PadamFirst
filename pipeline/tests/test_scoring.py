from datetime import date

import h3
import numpy as np
import pandas as pd
import pytest

from padamfirst import scoring
from padamfirst.scoring import downwind_density, percentile_rank, priority_class, score_cells

CELL = h3.latlng_to_cell(-3.3, 105.6, 7)


def test_percentile_rank_gives_minimum_zero():
    reference = [0, 0, 0, 10, 20]
    assert percentile_rank([0, 10, 25], reference).tolist() == [0.0, 0.6, 1.0]


def test_percentile_rank_ignores_missing_reference():
    assert percentile_rank([5], [np.nan, 1, 10]).tolist() == [0.5]
    assert percentile_rank([5], []).tolist() == [0.0]


@pytest.mark.parametrize(
    ("score", "expected"),
    [(100, "merah"), (70, "merah"), (69.9, "oranye"), (50, "oranye"), (30, "kuning"), (0, "hijau")],
)
def test_priority_class_boundaries(score, expected):
    assert priority_class(score) == expected


def cell_toward(bearing_deg):
    """Sel tetangga ring 3 yang arahnya paling dekat dengan bearing_deg dari CELL."""
    lat0, lon0 = h3.cell_to_latlng(CELL)

    def bearing(cell):
        lat, lon = h3.cell_to_latlng(cell)
        angle = np.degrees(np.arctan2((lon - lon0) * np.cos(np.radians(lat0)), lat - lat0))
        return abs((angle - bearing_deg + 180) % 360 - 180)

    return min(h3.grid_ring(CELL, 3), key=bearing)


def test_downwind_density_counts_only_cells_downwind():
    north, south = cell_toward(0), cell_toward(180)
    density = pd.Series({CELL: 0.0, north: 1000.0, south: 50.0})
    # Angin dari selatan (180) membawa asap ke utara.
    from_south = downwind_density(CELL, 180, density)
    from_north = downwind_density(CELL, 0, density)
    assert from_south > from_north > 0
    assert downwind_density(CELL, 90, density) == 0.0


def test_score_cells_ranks_worse_fire_higher():
    calm, severe = CELL, h3.latlng_to_cell(0.5, 101.4, 7)
    cells = pd.DataFrame(
        {
            "h3_index": [calm, severe],
            "date": date(2026, 11, 11),
            "dc": [50.0, 450.0],
            "wind_speed": [2.0, 15.0],
            "persistence_days": [1, 5],
            "frp_sum": [2.0, 300.0],
            "wind_dir": [90.0, 90.0],
            "peat_pct": [None, 80.0],
        }
    )
    static = pd.DataFrame(
        {"h3_index": [severe, cell_toward(0)], "peat_pct": [80.0, 0.0], "pop_density": [500.0, 5.0]}
    )
    result = score_cells(cells, cells, static)

    low, high = result["priority_score"]
    assert 0 <= low < high <= 100
    assert result["model_version"].unique().tolist() == [scoring.BASELINE_MODEL_VERSION]
    assert result[["p_spread", "impact_score", "fire_score"]].le(1).all(axis=None)
    assert result["priority_class"].tolist() == [priority_class(low), priority_class(high)]
