"""Canadian Forest Fire Weather Index System (Van Wagner 1987, pembaruan Wang dkk. 2015).

Semua fungsi menerima skalar atau array numpy. Input cuaca siang hari: suhu C, kelembapan %,
angin km/jam, dan hujan 24 jam mm.
"""

import numpy as np
import pandas as pd

INITIAL = {"ffmc": 85.0, "dmc": 6.0, "dc": 15.0}
FFMC_COEFFICIENT = 250 * 59.5 / 101

# Panjang hari efektif DMC per bulan untuk tiap pita lintang.
DMC_DAY_LENGTH = {
    "north": (6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0),
    "north_subtropic": (7.9, 8.4, 8.9, 9.5, 9.9, 10.2, 10.1, 9.7, 9.1, 8.6, 8.1, 7.8),
    "south_subtropic": (10.1, 9.6, 9.1, 8.5, 8.1, 7.8, 7.9, 8.3, 8.9, 9.4, 9.9, 10.2),
    "south": (11.5, 10.5, 9.2, 7.9, 6.8, 6.2, 6.5, 7.4, 8.7, 10.0, 11.2, 11.8),
}
DC_DAY_LENGTH = {
    "north": (-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6),
    "south": (6.4, 5.0, 2.4, 0.4, -1.6, -1.6, -1.6, -1.6, -1.6, 0.9, 3.8, 5.8),
}


def ffmc(prev, temp, rh, wind, rain):
    prev, temp, rh, wind, rain = np.broadcast_arrays(*map(np.asarray, (prev, temp, rh, wind, rain)))
    mo = FFMC_COEFFICIENT * (101 - prev) / (59.5 + prev)

    rf = np.where(rain > 0.5, rain - 0.5, 1.0)
    wetting = 42.5 * rf * np.exp(-100 / (251 - mo)) * (1 - np.exp(-6.93 / rf))
    wetting = wetting + np.where(mo > 150, 0.0015 * (mo - 150) ** 2 * np.sqrt(rf), 0)
    mo = np.minimum(np.where(rain > 0.5, mo + wetting, mo), 250)

    dry = 1 - np.exp(-0.115 * rh)
    ed = 0.942 * rh**0.679 + 11 * np.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * dry
    ew = 0.618 * rh**0.753 + 10 * np.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * dry

    def rate(humidity):
        k = 0.424 * (1 - (humidity / 100) ** 1.7) + 0.0694 * np.sqrt(wind) * (
            1 - (humidity / 100) ** 8
        )
        return k * 0.581 * np.exp(0.0365 * temp)

    m = np.where(mo > ed, ed + (mo - ed) / 10 ** rate(rh), mo)
    m = np.where((mo < ed) & (mo < ew), ew - (ew - mo) / 10 ** rate(100 - rh), m)
    return np.clip(59.5 * (250 - m) / (FFMC_COEFFICIENT + m), 0, 101)


def _dmc_day_length(lat, month):
    table = {key: np.asarray(value)[month - 1] for key, value in DMC_DAY_LENGTH.items()}
    return np.select(
        [lat > 30, lat > 10, lat > -10, lat > -30],
        [table["north"], table["north_subtropic"], 9.0, table["south_subtropic"]],
        table["south"],
    )


def dmc(prev, temp, rh, rain, lat, month):
    prev, temp, rh, rain, lat, month = np.broadcast_arrays(
        *map(np.asarray, (prev, temp, rh, rain, lat, month))
    )
    temp = np.maximum(temp, -1.1)
    drying = 1.894 * (temp + 1.1) * (100 - rh) * _dmc_day_length(lat, month) * 1e-4

    re = 0.92 * rain - 1.27
    mo = 20 + 280 / np.exp(0.023 * prev)
    with np.errstate(divide="ignore"):
        log_prev = np.log(prev)
    b = np.select(
        [prev <= 33, prev <= 65],
        [100 / (0.5 + 0.3 * prev), 14 - 1.3 * log_prev],
        6.2 * log_prev - 17.2,
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        mr = mo + 1000 * re / (48.77 + b * re)
        wetted = np.maximum(43.43 * (5.6348 - np.log(mr - 20)), 0)
    after_rain = np.where(rain > 1.5, wetted, prev)
    return np.maximum(after_rain + drying, 0)


def dc(prev, temp, rain, lat, month):
    prev, temp, rain, lat, month = np.broadcast_arrays(
        *map(np.asarray, (prev, temp, rain, lat, month))
    )
    temp = np.maximum(temp, -2.8)
    day_length = np.select(
        [lat > 20, lat > -20],
        [np.asarray(DC_DAY_LENGTH["north"])[month - 1], 1.4],
        np.asarray(DC_DAY_LENGTH["south"])[month - 1],
    )
    evaporation = np.maximum((0.36 * (temp + 2.8) + day_length) / 2, 0)

    rd = 0.83 * rain - 1.27
    with np.errstate(invalid="ignore"):
        wetted = np.maximum(prev - 400 * np.log(1 + 3.937 * rd / (800 * np.exp(-prev / 400))), 0)
    after_rain = np.where(rain > 2.8, wetted, prev)
    return np.maximum(after_rain + evaporation, 0)


def isi(ffmc_value, wind):
    m = FFMC_COEFFICIENT * (101 - np.asarray(ffmc_value)) / (59.5 + np.asarray(ffmc_value))
    fine_fuel = 91.9 * np.exp(-0.1386 * m) * (1 + m**5.31 / 4.93e7)
    return 0.208 * np.exp(0.05039 * np.asarray(wind)) * fine_fuel


def bui(dmc_value, dc_value):
    p, d = np.broadcast_arrays(np.asarray(dmc_value, float), np.asarray(dc_value, float))
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.where((p == 0) & (d == 0), 0, 0.8 * p * d / (p + 0.4 * d))
        reduced = p - (1 - u / p) * (0.92 + (0.0114 * p) ** 1.7)
    return np.where(u < p, np.maximum(np.nan_to_num(reduced), 0), u)


def fwi(isi_value, bui_value):
    r, u = np.broadcast_arrays(np.asarray(isi_value, float), np.asarray(bui_value, float))
    duff = np.where(u > 80, 1000 / (25 + 108.64 * np.exp(-0.023 * u)), 0.626 * u**0.809 + 2)
    b = 0.1 * r * duff
    with np.errstate(divide="ignore", invalid="ignore"):
        scaled = np.exp(2.72 * (0.434 * np.log(b)) ** 0.647)
    return np.where(b > 1, scaled, b)


def fwi_series(weather: pd.DataFrame, initial: dict = INITIAL) -> pd.DataFrame:
    """Hitung kode FWI berantai per hari untuk banyak sel sekaligus.

    weather berisi h3_index, date, lat, temp, rh, wind, rain, satu baris per sel per hari tanpa
    hari bolong. Hari pertama tiap sel mulai dari nilai awal, jadi buang hari spin-up sesudahnya.
    """
    table = weather.pivot(index="date", columns="h3_index")
    lat = table["lat"].iloc[0].to_numpy()
    state = {code: np.full(len(lat), value) for code, value in initial.items()}
    frames = []
    for day in table.index:
        row = {name: table[name].loc[day].to_numpy() for name in ("temp", "rh", "wind", "rain")}
        month = pd.Timestamp(day).month
        state = {
            "ffmc": ffmc(state["ffmc"], row["temp"], row["rh"], row["wind"], row["rain"]),
            "dmc": dmc(state["dmc"], row["temp"], row["rh"], row["rain"], lat, month),
            "dc": dc(state["dc"], row["temp"], row["rain"], lat, month),
        }
        spread = isi(state["ffmc"], row["wind"])
        buildup = bui(state["dmc"], state["dc"])
        frames.append(
            pd.DataFrame(
                {
                    "h3_index": table["lat"].columns,
                    "date": day,
                    **state,
                    "isi": spread,
                    "bui": buildup,
                    "fwi": fwi(spread, buildup),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
