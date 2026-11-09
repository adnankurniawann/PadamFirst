"""Konstanta proyek dari PRD bagian 4 dan 5."""

# west, south, east, north
BBOX_INDONESIA = (94.5, -11.5, 141.5, 6.5)

H3_RESOLUTION = 7

# S = 100 * (0.45 * P_spread + 0.35 * D + 0.20 * A)
SCORE_WEIGHTS = {"p_spread": 0.45, "impact": 0.35, "fire": 0.20}

# Batas bawah skor tiap kelas, urut dari tertinggi
CLASS_THRESHOLDS = (("merah", 70), ("oranye", 50), ("kuning", 30), ("hijau", 0))
