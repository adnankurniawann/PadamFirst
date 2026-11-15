"""Konstanta proyek dari PRD bagian 4 dan 5."""

# west, south, east, north
BBOX_INDONESIA = (94.5, -11.5, 141.5, 6.5)

H3_RESOLUTION = 7

# S = 100 * (0.45 * P_spread + 0.35 * D + 0.20 * A)
SCORE_WEIGHTS = {"p_spread": 0.45, "impact": 0.35, "fire": 0.20}

# Batas bawah skor tiap kelas, urut dari tertinggi
CLASS_THRESHOLDS = (("merah", 70), ("oranye", 50), ("kuning", 30), ("hijau", 0))

# P_spread sementara sebelum model ML (Fase 7), tiap komponen persentil historis 0 sampai 1
BASELINE_SPREAD_WEIGHTS = {"dc": 0.35, "persistence_days": 0.25, "wind_speed": 0.20, "peat": 0.20}
# D dari gambut dan penduduk searah angin, A dari FRP dan persistensi
IMPACT_WEIGHTS = {"peat": 0.5, "exposure": 0.5}
FIRE_WEIGHTS = {"frp_sum": 0.5, "persistence_days": 0.5}
BASELINE_MODEL_VERSION = "baseline-v1"
