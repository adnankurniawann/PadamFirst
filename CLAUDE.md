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
