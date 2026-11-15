"""14 layer dari PRD bagian 3: id, kolom sumber, satuan, dan skema warna untuk dashboard."""

LAYERS = [
    ("priority", "priority_score", "Prioritas gabungan", "Hasil", "skor 0-100", "priority"),
    ("intensity", "frp_sum", "Intensitas", "Api", "MW per sel", "YlOrRd"),
    ("detection", "conf_mean", "Keyakinan deteksi", "Api", "0 low, 0,5 nominal, 1 high", "Greys"),
    ("persistence", "persistence_days", "Persistensi", "Api", "hari berturut-turut", "OrRd"),
    ("growth", "growth_24h", "Pertumbuhan", "Api", "perubahan titik per 24 jam", "RdBu"),
    ("peat", "peat_pct", "Gambut", "Bahan bakar", "persen area", "BrBG"),
    ("landcover", "landcover_class", "Tutupan lahan", "Bahan bakar", "kelas tutupan", "landcover"),
    ("wind", "wind_speed", "Angin", "Cuaca", "km/jam", "Blues"),
    ("rain", "rain_7d", "Curah hujan 7 hari", "Cuaca", "mm", "GnBu"),
    ("drought", "dc", "Kekeringan (Drought Code)", "Cuaca", "indeks", "YlOrBr"),
    ("temperature", "temp_max", "Suhu maksimum", "Cuaca", "derajat C", "Reds"),
    ("population", "pop_density", "Kepadatan penduduk", "Dampak", "jiwa per km2", "PuRd"),
    ("human", "dist_road_km", "Jarak ke jalan", "Dampak", "km ke jalan terdekat", "YlGn"),
    (
        "confidence",
        "confidence_level",
        "Keyakinan prediksi",
        "Model",
        "rendah, sedang, tinggi",
        "Purples",
    ),
]

LAYER_COLUMNS = {layer_id: column for layer_id, column, *_ in LAYERS}
