# Backend (FastAPI)

## Setup

From the `backend/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### macOS: XGBoost / OpenMP

If you see `Library not loaded: libomp.dylib`:

```bash
brew install libomp
```

## Train the XGBoost residual model

Writes `models/xgb_delta.json` and `models/xgb_delta.features.csv` next to this folder (paths are package-relative):

```bash
cd backend
source .venv/bin/activate
python -m src.train.train_xgb_delta
```

If those files are missing (e.g. after a fresh `git clone`), **the API will train them automatically on first startup** (can take ~30–60 seconds). You can still pre-train with the command above to avoid that delay.

## Run the API

```bash
cd backend
source .venv/bin/activate
uvicorn app:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/`
- Predictions: `GET http://127.0.0.1:8000/predictions?boat_class=1x&sex=men&weight_class=openweight&direction=upstream&map_rate=24`

### River geometry

Segment headings and map polylines come from [`data/charles_river_rowing.geojson`](data/charles_river_rowing.geojson). The **canonical** vertices run **upstream (Watertown Dam) → downstream (Longfellow Bridge)** along the `LineString` order (`[lng, lat]`).

- **`RIVER_DENSIFY_STEPS`** — subdivide each leg with linear interpolation (default **`5`**). **`0`** or **`1`** means no extra subdivision (use the sparse GeoJSON vertices only). More steps → more segments and smoother headings on bends.
- **`RIVER_HEADING_SMOOTH_WINDOW`** — when building each segment’s downstream axis for wind/physics, use a chord from vertex `i−W` to `i+W` (default **`4`**; **`0`** = per-leg geographic heading only). Headings use **longitude scaled by cos(latitude)** so east–west legs are not skewed.
- The server caches loaded segments by **GeoJSON file mtime/size** and this step count; editing the file or changing the env var requires an **API restart** to pick up changes in typical deployments.

Optional: from `backend/`, run `python -m src.model.geometry.export_densified_geojson` to write a densified GeoJSON next to the canonical file for QGIS / geojson.io QA.

### Query params

- `map_rate` — stroke rate (spm) used for per-segment payloads in each hour (`18`–`36`, same set as the table). Default `24`.

Daily responses are cached under `cache_data/` (gitignored).

## CORS

`app.py` allows `http://localhost:3000` and `http://127.0.0.1:3000` by default.

For a deployed frontend (e.g. Vercel), set a comma-separated list (no spaces required):

```bash
export CORS_ORIGINS=https://your-app.vercel.app,https://yourdomain.com
```

Restart uvicorn after changing this.
