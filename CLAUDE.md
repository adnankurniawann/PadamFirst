# PadamFirst

Dashboard peta Indonesia yang mengurutkan titik api karhutla berdasarkan mana yang paling perlu dipadamkan duluan. Tiap sel H3 resolusi 7 diberi skor prioritas 0 sampai 100 dari prediksi ML (api bertahan atau menyebar dalam 48 jam), dampak, dan kondisi api. Spesifikasi lengkap dan fase pengembangan ada di `PRD.md`.

## Stack

- `pipeline/`: Python 3.11, uv, Ruff, pytest
- `api/`: FastAPI, uv, Ruff, pytest
- `web/`: Next.js App Router, TypeScript, Tailwind, ESLint, Prettier
- `db/`: Postgres 16, PostGIS, h3-pg

## Perintah penting

Semua service, dari root repo:

```bash
docker compose up --build
```

Service: web `localhost:3000`, API `localhost:8000`, Postgres `localhost:5433` (bukan 5432). Perubahan di `api/app` dan `web/` langsung reload, perubahan dependensi perlu `--build`. Hapus data lokal database dengan `docker compose down -v`.

Python, jalankan di `pipeline/` atau `api/`:

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pytest
```

Test `pipeline/` butuh Postgres compose, jalankan `docker compose up -d --wait db` dulu. Test memakai database `padamfirst_test` yang dibuat dan dihapus sendiri, data dev tidak tersentuh.

Migrasi, jalankan di `pipeline/` setelah `cp .env.example .env` di root repo:

```bash
uv run --env-file ../.env alembic upgrade head
```

Ingest titik api, butuh `FIRMS_MAP_KEY` di `.env` dan batas admin di `data/raw/admin/`:

```bash
uv run --env-file ../.env python -m padamfirst.ingest.firms --days 2
```

Layer statis per sel ke `cell_static` dan `data/processed/cell_static.parquet`. Butuh data mentah di `data/raw/` (admin, peat, worldpop, worldcover, osm, dan arsip tahunan `firms_archive/viirs-snpp_<tahun>_Indonesia.csv` dari `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<tahun>/`). Jalan sekitar 20 menit:

```bash
uv run --env-file ../.env python -m padamfirst.ingest.static_layers
```

Web, jalankan di `web/`:

```bash
npm ci
npm run lint
npm run format
npm run build
```

## Aturan umum

- Baca `PRD.md` dan `CLAUDE.md` dulu
- Kerjakan fase yang diminta saja, jangan loncat
- Tiap fungsi pemrosesan data punya unit test
- Commit kecil, pesan cuma satu baris judul tanpa body
- Jangan pernah pakai Co-Authored-By atau atribusi AI apa pun di commit dan PR
- Semua data dari sumber publik yang real, bukan dummy
- Akhiri tiap fase dengan cara manual untuk mengecek hasilnya
