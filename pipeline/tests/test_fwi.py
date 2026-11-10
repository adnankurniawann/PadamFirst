"""Uji FWI terhadap paket resmi cffdrs (Canadian Forest Service, GPL-2).

tests/data/cffdrs/fwi_01.csv adalah contoh standar Van Wagner & Pickett 1985 beserta keluaran
cffdrs 1.10.0. Berkas lain adalah data uji per komponen cffdrs, disaring ke input yang masuk akal
secara fisik. Sumber: https://github.com/cffdrs/cffdrs_r/tree/main/tests/testthat/data
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from padamfirst.features import fwi

DATA = Path(__file__).parent / "data/cffdrs"


def reference(name):
    return pd.read_csv(DATA / f"{name}.csv")


def standard_weather(lat=40.0):
    days = reference("fwi_01")
    return days, pd.DataFrame(
        {
            "h3_index": "a",
            "date": pd.to_datetime(
                days[["YR", "MON", "DAY"]].set_axis(["year", "month", "day"], axis=1)
            ),
            "lat": lat,
            "temp": days["TEMP"],
            "rh": days["RH"],
            "wind": days["WS"],
            "rain": days["PREC"],
        }
    )


def test_fwi_series_matches_standard_example():
    expected, weather = standard_weather()

    result = fwi.fwi_series(weather)

    assert len(result) == 48
    for code in ("ffmc", "dmc", "dc", "isi", "bui", "fwi"):
        np.testing.assert_allclose(result[code], expected[code.upper()], rtol=1e-3, atol=0.01)


def test_fwi_series_keeps_cells_apart():
    _, weather = standard_weather()
    both = pd.concat([weather, weather.assign(h3_index="b", lat=0.0)])

    result = fwi.fwi_series(both).set_index(["h3_index", "date"])

    np.testing.assert_allclose(
        result.loc["a", "dmc"], fwi.fwi_series(weather).set_index("date")["dmc"]
    )
    # FFMC tidak bergantung lintang, DMC dan DC bergantung.
    np.testing.assert_allclose(result.loc["a", "ffmc"], result.loc["b", "ffmc"])
    assert not np.allclose(result.loc["a", "dmc"], result.loc["b", "dmc"])
    assert not np.allclose(result.loc["a", "dc"], result.loc["b", "dc"])


@pytest.mark.parametrize(
    ("name", "function", "columns"),
    [
        ("FineFuelMoistureCode", fwi.ffmc, ["ffmc_yda", "temp", "rh", "ws", "prec"]),
        ("DuffMoistureCode", fwi.dmc, ["dmc_yda", "temp", "rh", "prec", "lat", "mon"]),
        ("DroughtCode", fwi.dc, ["dc_yda", "temp", "prec", "lat", "mon"]),
        ("InitialSpreadIndex", fwi.isi, ["ffmc", "ws"]),
        ("BuildupIndex", fwi.bui, ["dmc", "dc"]),
        ("FireWeatherIndex", fwi.fwi, ["isi", "bui"]),
    ],
)
def test_components_match_cffdrs(name, function, columns):
    data = reference(name)
    result = function(*(data[column].to_numpy() for column in columns))
    np.testing.assert_allclose(result, data[name], rtol=1e-3, atol=0.01)


@pytest.mark.parametrize(("lat", "day_length"), [(0.0, 9.0), (-5.0, 9.0), (-12.0, 8.3)])
def test_dmc_uses_tropical_day_length(lat, day_length):
    # Agustus, tanpa hujan: kenaikan DMC = 1.894 (T + 1.1) (100 - RH) Le 1e-4.
    result = fwi.dmc(10.0, 30.0, 50.0, 0.0, lat, 8)
    assert result == pytest.approx(10 + 1.894 * 31.1 * 50 * day_length * 1e-4)


def test_dc_uses_tropical_day_length():
    # Antara 20 LU dan 20 LS faktor panjang hari tetap 1.4 sepanjang tahun.
    for month in (1, 8):
        assert fwi.dc(100.0, 30.0, 0.0, -3.0, month) == pytest.approx(100 + (0.36 * 32.8 + 1.4) / 2)


def test_rain_lowers_dc_and_dry_days_raise_it():
    dry = fwi.dc(300.0, 33.0, 0.0, 0.5, 8)
    wet = fwi.dc(300.0, 33.0, 40.0, 0.5, 8)
    assert dry > 300 > wet
