"""Agregasi titik api mentah ke sel H3 per hari."""

import pandas as pd

# Confidence jadi angka 0 sampai 1 supaya bisa dirata-rata per sel.
CONFIDENCE_SCORE = {"low": 0.0, "nominal": 0.5, "high": 1.0}


def local_date(acq_datetime: pd.Series, lon: pd.Series) -> pd.Series:
    """Tanggal waktu matahari setempat (UTC + lon/15 jam).

    Lintasan malam VIIRS sekitar jam 01.30 setempat jatuh ke tanggal UTC sebelumnya, jadi tanggal
    UTC akan memecah satu malam kebakaran ke dua hari.
    """
    return (acq_datetime + pd.to_timedelta(lon / 15, unit="h")).dt.date


def aggregate_hotspots(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per sel per hari dari kolom h3_index, acq_datetime (UTC), lon, frp, confidence."""
    frame = hotspots.assign(
        date=local_date(hotspots["acq_datetime"], hotspots["lon"]),
        conf=hotspots["confidence"].map(CONFIDENCE_SCORE),
    )
    return (
        frame.groupby(["h3_index", "date"])
        .agg(
            n_hotspots=("frp", "size"),
            frp_sum=("frp", "sum"),
            frp_max=("frp", "max"),
            conf_mean=("conf", "mean"),
        )
        .reset_index()
    )
