# PRD PadamFirst

Versi 1.0, 9 November 2026, Adnan

## 1. Ringkasan

PadamFirst adalah dashboard peta Indonesia yang mengurutkan titik api karhutla berdasarkan mana yang paling perlu dipadamkan duluan. Setiap titik api dari satelit diberi skor prioritas 0 sampai 100 dari gabungan kondisi api, cuaca, lahan, dan dampak ke penduduk, lalu ditampilkan merah sampai hijau.

Saat musim kemarau jumlah titik api bisa ratusan per hari, sedangkan regu pemadam dan water bombing terbatas. Peta hotspot yang ada sekarang menunjukkan di mana api berada, tapi belum menjawab api mana yang paling berbahaya kalau dibiarkan. PadamFirst menjawab itu dengan model machine learning yang memprediksi peluang api bertahan atau menyebar dalam 48 jam, lalu digabung dengan dampaknya.

User bisa melihat satu peta gabungan (prioritas) atau berganti ke peta per faktor seperti gambut, angin, curah hujan, kekeringan, dan kepadatan penduduk untuk tahu kenapa suatu titik jadi merah.

## 2. Tujuan dan pengguna

Versi 1 harus bisa menampilkan titik api terbaru se-Indonesia, menghitung skor prioritas tiap titik, dan menjelaskan faktor apa yang bikin skornya tinggi. Data diperbarui otomatis minimal tiap 3 jam.

### Tujuan

- Peta gabungan prioritas dengan 4 kelas warna (merah, oranye, kuning, hijau)
- Peta per faktor yang bisa dipilih satu per satu
- Daftar titik terurut dari prioritas tertinggi, bisa difilter per provinsi
- Model ML yang memprediksi peluang api bertahan atau menyebar 48 jam ke depan, lengkap dengan penjelasan per titik
- Semua data dari sumber publik yang real, bukan dummy

### Bukan tujuan versi 1

- Rute atau penugasan regu pemadam secara otomatis
- Prediksi titik api baru di lokasi yang belum terbakar sama sekali
- Aplikasi mobile dan notifikasi push
- Menggantikan sistem resmi seperti SiPongi atau FDRS BMKG

### Pengguna sasaran

| Pengguna | Kebutuhan utama |
| --- | --- |
| Petugas BPBD dan Manggala Agni | Tahu titik mana yang didatangi duluan hari ini |
| Peneliti dan mahasiswa | Lihat pola faktor penyebab per wilayah |
| Juri lomba atau dosen | Paham alasan di balik skor dalam sekali lihat |
| Masyarakat umum | Cek apakah ada api berbahaya dekat tempat tinggalnya |

## 3. Faktor dan layer peta

Ada 12 layer faktor, 1 layer keyakinan prediksi, dan 1 layer gabungan. Faktornya dibagi ke kelompok kondisi api saat ini, bahan bakar, cuaca, dan dampak kalau api dibiarkan. Penyebab utama karhutla di Indonesia adalah pembukaan lahan dengan cara membakar, sedangkan kemarau panjang dan El Nino memperparah. Karena itu jarak ke perkebunan dan jalan dipakai sebagai proksi aktivitas manusia.

| Layer | Kelompok | Kenapa berpengaruh | Satuan di peta |
| --- | --- | --- | --- |
| Intensitas | Api | Fire Radiative Power tinggi berarti api besar dan panas | MW per sel |
| Keyakinan deteksi | Api | Titik dengan confidence rendah bisa jadi false positive | low, nominal, high |
| Persistensi | Api | Api yang muncul berhari-hari di sel sama kemungkinan api gambut yang membara di bawah tanah | hari berturut-turut |
| Pertumbuhan | Api | Jumlah titik di klaster yang naik cepat berarti api sedang meluas | perubahan titik per 24 jam |
| Gambut | Bahan bakar | Gambut kering terbakar lama, susah dipadamkan, dan penyumbang asap terbesar | persen area dan kedalaman |
| Tutupan lahan | Bahan bakar | Semak, kebun, dan hutan sekunder lebih gampang terbakar | kelas tutupan |
| Arah dan kecepatan angin | Cuaca | Angin mempercepat sebaran api dan membawa asap ke pemukiman | km/jam dan derajat |
| Curah hujan | Cuaca | Hujan 7 dan 30 hari terakhir menentukan kebasahan bahan bakar | mm |
| Kekeringan | Cuaca | Hari tanpa hujan dan Drought Code dari Fire Weather Index | indeks |
| Suhu dan kelembapan | Cuaca | Suhu tinggi dan kelembapan rendah bikin bahan bakar cepat kering | derajat C dan persen |
| Kepadatan penduduk | Dampak | Makin banyak orang di sekitar dan searah angin, makin besar dampak asap | jiwa per km2 |
| Aktivitas manusia | Dampak | Dekat jalan dan perkebunan berarti risiko pembakaran ulang lebih tinggi, tapi juga lebih mudah diakses regu | km ke jalan terdekat |
| Keyakinan prediksi | Model | Seberapa yakin model terhadap skornya, pakai skema warna ungu supaya tidak tertukar dengan keyakinan deteksi | rendah, sedang, tinggi |
| **Prioritas gabungan** | Hasil | Gabungan semua faktor plus prediksi ML | skor 0 sampai 100 |

## 4. Sumber data

Semua sumber gratis. Hanya NASA FIRMS yang butuh API key, dan itu gratis cukup daftar pakai email.

| Data | Sumber | Akses | Update | Dipakai untuk |
| --- | --- | --- | --- | --- |
| Titik api | NASA FIRMS VIIRS SNPP, NOAA-20, NOAA-21 (375 m) dan MODIS (1 km) | REST CSV, butuh MAP_KEY | Near real-time | Intensitas, keyakinan, persistensi, pertumbuhan, label ML |
| Arsip titik api | NASA FIRMS produk `_SP` | REST CSV atau unduh arsip | Historis sejak 2012 untuk VIIRS | Data latih ML |
| Cuaca saat ini dan prakiraan | Open-Meteo Forecast API | REST JSON, tanpa key | Per jam, prakiraan sampai 16 hari | Angin, hujan, suhu, kelembapan, soil moisture |
| Cuaca historis | Open-Meteo Archive API (ERA5) | REST JSON, tanpa key | Historis sejak 1940 | Fitur cuaca data latih |
| Gambut | Peta sebaran lahan gambut BBSDLP Kementan sebagai sumber utama, Wetlands International sebagai cadangan | Shapefile atau GeoNode | Statis | Layer gambut dan kedalaman |
| Penduduk | WorldPop Indonesia 100 m | GeoTIFF, CC BY 4.0 | Tahunan | Kepadatan dan paparan penduduk |
| Tutupan lahan | ESA WorldCover 10 m | GeoTIFF | Statis (2021) | Jenis bahan bakar |
| Jalan dan perkebunan | OpenStreetMap (Geofabrik extract Indonesia) | PBF atau shapefile | Mingguan | Jarak ke jalan dan kebun |
| Batas wilayah | GADM atau HDX batas administrasi Indonesia | GeoJSON atau shapefile | Statis | Filter provinsi dan kabupaten |

Catatan teknis

- Endpoint FIRMS: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}`
- Bounding box Indonesia: `94.5,-11.5,141.5,6.5`
- Batas FIRMS 5.000 request per 10 menit
- Open-Meteo menerima banyak koordinat dalam satu request, jadi cuaca diambil per centroid sel yang punya titik api saja
- Open-Meteo gratis untuk non-komersial
- Drought Code dan FWI dihitung sendiri dari data Open-Meteo pakai rumus Canadian FWI, karena FDRS BMKG berbasis rumus yang sama dan datanya tidak ada di API publik

## 5. Skor prioritas dan machine learning

### Unit analisis

Titik api dikelompokkan ke sel heksagon H3 resolusi 7 (sekitar 5 km2 per sel). Semua faktor dihitung per sel per hari.

### Target yang diprediksi

Untuk sel yang punya titik api di hari t, label = 1 kalau dalam 48 jam berikutnya sel itu masih ada titik api atau sel tetangganya (ring 1 H3) muncul titik api baru. Label = 0 kalau api hilang. Model belajar membedakan api yang akan padam sendiri dengan api yang akan bertahan atau meluas.

### Fitur

- Api: jumlah titik, total dan maksimum FRP, rata-rata confidence, hari persistensi, perubahan jumlah titik 24 jam, jumlah sel tetangga yang terbakar
- Cuaca: kecepatan dan arah angin, hujan 1, 7, dan 30 hari, hari tanpa hujan, suhu maksimum, kelembapan minimum, soil moisture, FFMC, DC, FWI
- Lahan: persen area gambut, kelas tutupan lahan dominan, jarak ke jalan, jarak ke perkebunan
- Waktu: bulan dan hari ke berapa dalam musim kemarau

### Model

1. Baseline skor berbobot rule-based, supaya dashboard sudah bisa jalan sebelum ML siap
2. Model utama LightGBM classifier dengan class weight
3. Kalibrasi probabilitas pakai isotonic regression
4. Penjelasan per sel pakai SHAP

### Validasi

Split berdasarkan waktu. Latih 2015 sampai 2022, validasi 2023, uji 2024 sampai 2025. Metrik utama PR-AUC dan recall di 50 sel teratas per hari. Model harus mengalahkan baseline.

### Rumus skor akhir

```
S = 100 * (0.45 * P_spread + 0.35 * D + 0.20 * A)
```

- `P_spread` probabilitas dari model ML
- `D` skor dampak 0 sampai 1, gabungan persen gambut dan penduduk terpapar dalam radius 10 km searah angin
- `A` skor kondisi api 0 sampai 1 dari FRP dan persistensi yang dinormalisasi
- Bobot disimpan di config

| Kelas | Rentang skor | Arti |
| --- | --- | --- |
| Merah | 70 sampai 100 | Tangani hari ini |
| Oranye | 50 sampai 69 | Tangani dalam 24 jam |
| Kuning | 30 sampai 49 | Pantau |
| Hijau | 0 sampai 29 | Kemungkinan padam sendiri |

Keyakinan prediksi dihitung dari probabilitas terkalibrasi dan seberapa jauh fitur sel itu dari data latih. Sel dengan fitur yang jarang muncul di data latih diberi label keyakinan rendah.

## 6. Fitur dashboard

Halaman utama adalah satu peta Indonesia layar penuh dengan panel kiri untuk memilih layer dan panel kanan untuk daftar prioritas.

### Peta

- Basemap MapLibre tile gelap, zoom awal seluruh Indonesia
- Heksagon H3 diwarnai sesuai layer aktif, titik api mentah muncul saat zoom di atas level 9
- Layer angin ditampilkan sebagai panah arah dengan panjang sesuai kecepatan
- Legenda berubah mengikuti layer aktif
- Slider waktu 7 hari terakhir

### Panel layer (kiri)

- Tombol utama Prioritas Gabungan, aktif secara default
- 13 layer lain dikelompokkan per kelompok (Api, Bahan bakar, Cuaca, Dampak, Model)
- Hanya satu layer aktif sekaligus
- Filter provinsi dan kabupaten

### Panel prioritas (kanan)

- Daftar sel terurut dari skor tertinggi, berisi peringkat, kabupaten, provinsi, skor, dan kelas warna
- Klik baris langsung zoom ke sel itu
- Ringkasan jumlah sel per kelas hari ini
- Tombol ekspor CSV

### Panel detail sel

Muncul saat sel diklik. Isinya skor dan kelas, koordinat centroid, jumlah titik api dan FRP, nilai tiap faktor, bar chart SHAP 5 faktor teratas, keyakinan prediksi, dan grafik jumlah titik 7 hari terakhir.

### Alur pengguna

1. Buka dashboard, langsung lihat peta prioritas gabungan dan daftar merah teratas
2. Filter ke provinsi yang jadi tanggung jawabnya
3. Klik sel merah teratas, baca kenapa skornya tinggi
4. Ganti ke layer angin atau gambut untuk konfirmasi
5. Ekspor daftar ke CSV untuk regu lapangan

### Halaman tambahan

- `/about` berisi metodologi, sumber data, dan disclaimer
- `/model` berisi metrik model, feature importance global, dan tanggal training terakhir

## 7. Arsitektur dan tech stack

Pipeline Python jalan tiap 3 jam, menulis hasil ke PostGIS, lalu FastAPI melayani dashboard Next.js. Model dilatih sekali di lokal atau Colab, lalu pipeline cuma menjalankan prediksi.

```
 NASA FIRMS        Open-Meteo        Layer statis
 (titik api)       (cuaca)           (gambut, WorldPop, OSM)
      |                 |                  |
      v                 v                  v
 +-----------------------------------------------------------+
 | Pipeline Python (cron tiap 3 jam)                         |
 | Ingest -> Fitur per sel H3 -> LightGBM + SHAP -> Skor     |
 +-----------------------------------------------------------+
                          |
                          v
 PostgreSQL + PostGIS + h3-pg  ->  FastAPI  ->  Dashboard Next.js
```

| Bagian | Pilihan | Alasan |
| --- | --- | --- |
| Pipeline dan ML | Python 3.11, pandas, geopandas, rasterio, h3-py, LightGBM, SHAP, scikit-learn | Standar untuk geospasial dan tabular ML |
| Database | PostgreSQL 16, PostGIS, h3-pg | Query spasial dan agregasi H3 langsung di SQL |
| API | FastAPI, SQLAlchemy, Pydantic | Ringan dan satu bahasa dengan pipeline |
| Web | Next.js, TypeScript, Tailwind, MapLibre GL, deck.gl H3HexagonLayer, Recharts | Cepat untuk ribuan heksagon, tanpa token Mapbox |
| Basemap | OpenFreeMap atau CARTO | Tanpa API key |
| Scheduler | GitHub Actions cron | Gratis, log tersimpan |
| Deploy | Vercel (web), Railway atau Render (API), Supabase (Postgres) | Ada free tier |

## 8. Skema data dan API

| Tabel | Kolom utama | Isi |
| --- | --- | --- |
| `hotspots` | id, satellite, instrument, lat, lon, geom, acq_datetime, frp, confidence, h3_index | Titik api mentah, unik per satellite, lat, lon, acq_datetime |
| `cell_static` | h3_index, peat_pct, peat_depth_cm, landcover_class, pop_density, dist_road_km, dist_plantation_km, province, regency | Faktor statis, dihitung sekali |
| `cell_daily` | h3_index, date, n_hotspots, frp_sum, frp_max, conf_mean, persistence_days, growth_24h, wind_speed, wind_dir, rain_1d, rain_7d, rain_30d, dry_days, temp_max, rh_min, soil_moisture, ffmc, dmc, dc, fwi | Fitur harian per sel aktif |
| `predictions` | h3_index, date, model_version, p_spread, impact_score, fire_score, priority_score, priority_class, confidence_level, shap_top (jsonb) | Hasil skoring per sel per hari |
| `ingest_runs` | id, source, started_at, finished_at, rows, status, error | Log tiap job ingest |

| Method | Path | Fungsi |
| --- | --- | --- |
| GET | `/api/cells?date=&layer=&province=` | GeoJSON sel H3 dengan nilai layer yang diminta |
| GET | `/api/priorities?date=&province=&limit=50` | Daftar sel terurut berdasarkan priority_score |
| GET | `/api/cells/{h3_index}?date=` | Detail satu sel, termasuk SHAP dan riwayat 7 hari |
| GET | `/api/hotspots?bbox=&date=` | Titik api mentah untuk zoom dekat |
| GET | `/api/wind?date=&bbox=` | Vektor angin untuk layer panah |
| GET | `/api/layers` | Daftar layer, satuan, dan skema warna |
| GET | `/api/model` | Versi model, metrik, tanggal training |
| GET | `/api/export.csv?date=&province=` | Ekspor daftar prioritas |
| GET | `/api/health` | Status ingest terakhir per sumber |

Response peta pakai GeoJSON dulu. Kalau sel lebih dari 20.000 dan peta lambat, ganti ke vector tile pakai `ST_AsMVT`.

## 9. Struktur repo

```
padamfirst/
  CLAUDE.md
  PRD.md
  docker-compose.yml
  .env.example              # FIRMS_MAP_KEY, DATABASE_URL, NEXT_PUBLIC_API_URL
  pipeline/
    pyproject.toml
    padamfirst/
      config.py             # bbox, resolusi H3, bobot skor, threshold kelas
      db.py
      ingest/
        firms.py
        weather.py
        static_layers.py
      features/
        cells.py
        fwi.py
        build_daily.py
      model/
        dataset.py
        train.py
        evaluate.py
        predict.py
        explain.py
      scoring.py
      jobs/
        run_update.py
    migrations/
    tests/
    notebooks/
  api/
    pyproject.toml
    app/
      main.py
      routes/
      schemas.py
    tests/
  web/
    package.json
    app/
      page.tsx
      about/
      model/
    components/
      MapView.tsx
      LayerPanel.tsx
      PriorityList.tsx
      CellDetail.tsx
      Legend.tsx
      TimeSlider.tsx
    lib/
      api.ts
      layers.ts
  data/
    raw/                    # tidak di-commit
    processed/
  models/                   # tidak di-commit
  .github/workflows/
    ci.yml
    update.yml
```

## 10. Fase pengembangan

Ada 15 fase dalam 5 tahap. Kerjakan satu fase per sesi Claude Code, cek hasilnya, commit, baru lanjut.

| Tahap | Fase | Hasil yang bisa dilihat |
| --- | --- | --- |
| A. Fondasi | 0 sampai 2 | Repo jalan, database siap |
| B. Data | 3 sampai 6 | Semua faktor terisi per sel |
| C. MVP | 7 sampai 9 | Dashboard jalan dengan skor baseline |
| D. Machine learning | 10 sampai 12 | Skor dari model, ada penjelasan SHAP |
| E. Rilis | 13 sampai 14 | Online, update otomatis, siap demo |

### Aturan umum tiap fase

- Baca `PRD.md` dan `CLAUDE.md` dulu
- Kerjakan fase yang diminta saja, jangan loncat
- Tiap fungsi pemrosesan data punya unit test
- Commit kecil dengan pesan singkat, tanpa Co-Authored-By atau atribusi AI
- Akhiri dengan cara manual untuk mengecek hasil fase

### Tahap A. Fondasi

#### Fase 0. Persiapan akun dan data mentah

Dikerjakan manual, bukan oleh Claude Code.

- Daftar MAP_KEY FIRMS di `https://firms.modaps.eosdis.nasa.gov/api/map_key/`
- Unduh peta gambut BBSDLP (atau Wetlands International sebagai cadangan) ke `data/raw/peat/`
- Unduh WorldPop Indonesia ke `data/raw/worldpop/`
- Unduh tile ESA WorldCover yang mencakup Sumatera, Kalimantan, dan Papua ke `data/raw/worldcover/`
- Unduh OSM Indonesia dari Geofabrik ke `data/raw/osm/`
- Unduh batas administrasi dari HDX ke `data/raw/admin/`

Selesai kalau semua file ada dan MAP_KEY sudah dicoba di browser.

#### Fase 1. Setup repo

- Inisialisasi monorepo sesuai struktur repo
- `pipeline/` dan `api/` pakai uv atau poetry, Python 3.11
- `web/` pakai Next.js App Router, TypeScript, Tailwind
- `docker-compose.yml` berisi Postgres 16 dengan PostGIS dan h3-pg, service api, service web
- Ruff untuk Python, ESLint dan Prettier untuk web
- `ci.yml` menjalankan lint dan test tiap push
- `CLAUDE.md` berisi ringkasan proyek, stack, perintah penting, dan aturan umum

Selesai kalau `docker compose up` jalan, `GET /api/health` mengembalikan 200, dan halaman web kosong terbuka di localhost.

Prompt: `Baca PRD.md. Kerjakan Fase 1 saja. Buat juga CLAUDE.md. Selesai kalau kriteria Fase 1 terpenuhi. Kasih tahu cara aku ngecek.`

#### Fase 2. Skema database

- Migrasi Alembic untuk 5 tabel di bagian 8
- Index pada `h3_index`, `date`, dan `geom` (GIST)
- Unique constraint `hotspots (satellite, lat, lon, acq_datetime)` dan `cell_daily (h3_index, date)`
- `db.py` dengan helper koneksi dan upsert batch

Selesai kalau `alembic upgrade head` sukses di database kosong dan test insert dan upsert lulus.

### Tahap B. Data

#### Fase 3. Ingest titik api

- `ingest/firms.py` menarik VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT untuk bbox Indonesia, day_range 1 sampai 5
- Parse CSV, normalisasi confidence ke low, nominal, high
- Hitung `h3_index` resolusi 7, simpan dengan upsert
- Buang titik di luar daratan Indonesia pakai batas admin
- Catat tiap run ke `ingest_runs`
- CLI `python -m padamfirst.ingest.firms --days 2`

Selesai kalau titik 2 hari terakhir masuk database, jumlahnya mendekati peta FIRMS, dan run kedua tidak bikin duplikat.

#### Fase 4. Layer statis

- `ingest/static_layers.py` memproses tiap sumber ke nilai per sel H3
- Gambut jadi `peat_pct` (persen luas sel) dan `peat_depth_cm`
- WorldPop jadi `pop_density` (jumlah orang dibagi luas sel)
- WorldCover jadi `landcover_class` dominan
- OSM jadi `dist_road_km` dan `dist_plantation_km` dari centroid
- Batas admin jadi `province` dan `regency`
- Sel yang diproses adalah semua sel yang pernah punya titik api sejak 2015 plus ring 2 di sekitarnya
- Hasil juga disimpan ke `data/processed/cell_static.parquet`

Selesai kalau `cell_static` terisi dan satu sel di Ogan Komering Ilir, Sumatera Selatan, punya `peat_pct` dan `pop_density` yang masuk akal.

#### Fase 5. Cuaca dan Fire Weather Index

- `ingest/weather.py` mengambil cuaca harian dari Open-Meteo per centroid sel aktif, batch maksimal 100 koordinat per request, dengan retry dan cache harian
- Variabel: suhu maksimum, kelembapan minimum, hujan, kecepatan dan arah angin dominan, soil moisture
- `features/fwi.py` mengimplementasikan FFMC, DMC, DC, ISI, BUI, FWI dari rumus Canadian FWI
- Nilai awal FFMC 85, DMC 6, DC 15, lalu dihitung berantai per hari dengan spin-up 60 hari

Selesai kalau unit test FWI cocok dengan contoh perhitungan standar CFFWIS dan nilai DC di Riau saat kemarau terlihat naik.

#### Fase 6. Fitur harian per sel

- `features/cells.py` agregasi titik api per sel per hari
- `features/build_daily.py` menghitung persistence_days (toleransi 1 hari bolong karena awan), growth_24h, jumlah sel tetangga terbakar, rain_7d, rain_30d, dry_days
- Gabungkan cuaca dan FWI ke `cell_daily`

Selesai kalau `cell_daily` untuk hari ini terisi lengkap tanpa kolom kosong di sel aktif, dan ada test untuk logika persistensi.

### Tahap C. MVP dashboard

#### Fase 7. Skor baseline dan API

- `scoring.py` dengan rumus bagian 5, `P_spread` sementara diganti skor rule-based dari DC, persistensi, angin, dan gambut
- Normalisasi tiap komponen ke 0 sampai 1 pakai persentil historis
- Simpan ke `predictions` dengan `model_version = baseline-v1`
- Semua endpoint di bagian 8 kecuali `/api/model`

Selesai kalau `curl /api/priorities?limit=50` mengembalikan daftar terurut dan `/api/cells` mengembalikan GeoJSON valid.

#### Fase 8. Dashboard peta dasar

- `MapView` dengan MapLibre dan deck.gl H3HexagonLayer
- `LayerPanel` dengan 14 layer, definisi warna dan satuan di `lib/layers.ts`
- `Legend` yang berubah mengikuti layer
- Layer angin sebagai panah
- Titik api mentah muncul saat zoom di atas 9

Selesai kalau semua layer bisa dipilih, warnanya berubah, dan peta tetap lancar saat digeser.

#### Fase 9. Dashboard lengkap

- `PriorityList` dengan ringkasan per kelas dan klik untuk zoom
- `CellDetail` dengan nilai faktor dan grafik 7 hari
- Filter provinsi dan kabupaten
- `TimeSlider` 7 hari terakhir
- Tombol ekspor CSV
- Tampilan tetap bisa dipakai di layar laptop 1366 px

Selesai kalau alur pengguna di bagian 6 bisa dijalankan dari awal sampai akhir.

### Tahap D. Machine learning

#### Fase 10. Dataset historis

- Tarik arsip FIRMS VIIRS SP untuk Juni sampai November 2015 sampai 2025, simpan sebagai parquet per tahun
- Tarik cuaca ERA5 dari Open-Meteo Archive untuk semua sel yang pernah aktif
- Jalankan ulang Fase 6 secara historis
- `model/dataset.py` membuat label 48 jam sesuai bagian 5
- Notebook EDA berisi proporsi label, sebaran fitur, dan korelasi

Selesai kalau ada `data/processed/train.parquet` dengan kolom fitur dan label, plus ringkasan jumlah baris per tahun.

#### Fase 11. Training dan evaluasi

- `model/train.py` melatih LightGBM dengan split waktu bagian 5
- Tuning ringan pakai Optuna, maksimal 50 trial, dioptimasi untuk PR-AUC di 2023
- Kalibrasi isotonic di data validasi
- `model/evaluate.py` menghitung PR-AUC, ROC-AUC, recall di 50 teratas per hari, dan reliability plot, dibandingkan dengan baseline
- Simpan model ke `models/lgbm-v1.txt` dan metrik ke `models/lgbm-v1.json`

Selesai kalau model mengalahkan baseline di PR-AUC pada data uji dan laporan metrik ada di notebook.

#### Fase 12. Integrasi ML dan SHAP

- `model/predict.py` menghasilkan `p_spread` harian
- `model/explain.py` menyimpan 5 kontribusi SHAP teratas per sel ke `shap_top`
- Hitung `confidence_level` dari probabilitas dan jarak fitur ke data latih
- `jobs/run_update.py` menjalankan ingest, fitur, prediksi, dan skoring berurutan
- `CellDetail` menampilkan bar chart SHAP dan keyakinan prediksi
- Halaman `/model` dan endpoint `/api/model`

Selesai kalau `predictions` hari ini punya `model_version = lgbm-v1` dan panel detail menjelaskan kenapa sel merah.

### Tahap E. Rilis

#### Fase 13. Otomasi dan deploy

- `update.yml` menjalankan `run_update.py` tiap 3 jam lewat GitHub Actions
- Database di Supabase, API di Railway atau Render, web di Vercel
- Secret disimpan di GitHub dan platform deploy, tidak di repo
- `/api/health` menampilkan umur data terakhir
- Banner di web kalau data lebih tua dari 6 jam

Selesai kalau dalam 24 jam data terbaru muncul sendiri tanpa dijalankan manual.

#### Fase 14. Testing, polish, dan demo

- Test end-to-end alur utama pakai Playwright
- Cek performa, peta prioritas terbuka di bawah 3 detik
- Halaman `/about` berisi metodologi, sumber data, batasan, dan disclaimer
- README berisi screenshot, cara menjalankan lokal, dan arsitektur
- Siapkan skenario demo berdasarkan data musim kebakaran 2023 kalau saat demo sedang musim hujan

Selesai kalau semua kriteria di bagian 11 tercentang.

## 11. Kriteria selesai

- [ ] Dashboard online dan bisa dibuka tanpa login
- [ ] Data titik api terbaru tidak lebih tua dari 6 jam
- [ ] 14 layer bisa dipilih, legenda sesuai
- [ ] Daftar prioritas bisa difilter per provinsi dan diekspor CSV
- [ ] Panel detail menampilkan SHAP dan keyakinan prediksi
- [ ] Model LightGBM mengalahkan baseline di PR-AUC pada data uji 2024 sampai 2025
- [ ] Halaman `/about` menjelaskan metodologi dan sumber data
- [ ] Peta prioritas terbuka di bawah 3 detik di laptop biasa

## 12. Risiko dan batasan

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Awan dan asap tebal menutupi api dari satelit | Persistensi terlihat putus | Toleransi 1 hari bolong |
| False positive dari sumber panas lain (pabrik, flare) | Titik merah palsu | Filter confidence low, masker lokasi industri dari OSM |
| Label ML berasal dari deteksi satelit, bukan data lapangan | Model belajar pola deteksi | Disebut di `/about`, validasi silang dengan rekap luas terbakar SiPongi per provinsi |
| Peta gambut resolusinya kasar | Skor gambut kurang akurat di tepi lahan | Pakai persen area per sel |
| Data latih didominasi tahun kering | Model jelek saat musim normal | Sertakan tahun basah 2016 sampai 2018 dan 2020 sampai 2022 |
| Batas penggunaan Open-Meteo | Request ditolak | Batch koordinat, cache per hari |
| File raster besar (WorldPop sekitar 1,8 GB) | Lambat diproses | Proses sekali di lokal, simpan hasil per sel |
| Saat demo tidak sedang musim kebakaran | Peta hampir kosong | Mode demo dengan tanggal historis |

PadamFirst adalah alat bantu keputusan untuk riset dan lomba, bukan sistem resmi. Keputusan pemadaman tetap di tangan BPBD, Manggala Agni, dan KLHK.

Pertanyaan terbuka: apakah perlu menambah data kawasan hutan lindung sebagai faktor dampak.

## 13. Sumber

- NASA FIRMS, https://firms.modaps.eosdis.nasa.gov/
- Format area API FIRMS, https://mintlify.wiki/danizd/GeoSentinel/data-sources/firms
- Batas request FIRMS, https://github.com/api-evangelist/nasa-firms
- Open-Meteo, https://open-meteo.com/en/docs
- Open-Meteo Historical Weather API, https://open-meteo.com/en/docs/historical-weather-api
- WorldPop Indonesia 100 m, https://hub.worldpop.org/doi/10.5258/SOTON/WP00114
- Metadata lahan gambut BBSDLP di datagambut Sumsel, https://datagambut.sumselprov.go.id/layers/geonode:lahan_gambut/metadata_detail
- Peta sebaran gambut BBSDLP dan Wetlands International, https://www2.cifor.org/ipn-toolbox/wp-content/uploads/pdf/A1.pdf
- FDRS BMKG berbasis Canadian FWI, https://jmg.bmkg.go.id/jmg/index.php/jmg/article/view/37/32
- Faktor antropogenik dalam FDRS gambut Sumatera Selatan, https://syartinilia-staff.ipb.ac.id/?p=3486
- Faktor penyebab kebakaran lahan gambut di OKI, Jurnal Sylva 2026, https://jurnal.um-palembang.ac.id/sylva/article/download/11515/4857
- Penyebab karhutla dan El Nino 2026, Katadata, https://katadata.co.id/lifestyle/varia/6a8e69f2b2e38/7-penyebab-kebakaran-hutan-yang-sering-terjadi-di-indonesia-bisa-karena-el-nino
- Batas administrasi Indonesia, HDX, https://data.humdata.org/dataset/indonesia-administrative-boundary-polygons-lines-and-places-levels-0-4b
