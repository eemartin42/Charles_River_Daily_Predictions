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

**Editing / regenerating**

1. **Manual satellite trace (recommended for fine control):** In [geojson.io](https://geojson.io) (satellite basemap), digitize a dense centerline, export GeoJSON, and replace `data/charles_river_rowing.geojson` with a `Feature` whose `geometry.type` is `LineString` and `coordinates` are `[lng, lat]` in upstream→downstream order. Update `properties.landmarks` `coord_index` values if you keep them.
2. **Rebuild from OpenStreetMap:** Download Overpass JSON, then run the merge script:

   ```bash
   cd backend
   curl -sS -X POST https://overpass-api.de/api/interpreter \
     --data-binary @scripts/overpass_charles_river.txt \
     -o data/osm_charles_overpass.json
   python scripts/build_charles_river_geojson_from_osm.py
   ```

3. After shipping new geometry, bump the **`v7`** (or current) cache prefix in [`app.py`](app.py) so `cache_data/` does not return stale segment payloads.

**Environment**

- **`RIVER_DENSIFY_STEPS`** — default **`1`** (dense OSM line: no extra subdivision). **`0`** or **`1`** = canonical vertices only. Use **`3`–`5`** for a sparse hand-drawn line. More steps → more segments.
- **`RIVER_HEADING_SMOOTH_WINDOW`** — chord from vertex `i−W` to `i+W` (default **`4`**; **`0`** = per-leg heading only). Headings use **longitude scaled by cos(latitude)**.
- The server caches segments by **GeoJSON mtime/size** and env knobs; **restart** the API after edits.

Optional: `python -m src.model.geometry.export_densified_geojson` writes a QA GeoJSON (gitignored `*_densified.geojson`).

### Query params

- `map_rate` — stroke rate (spm) used for per-segment payloads in each hour (`18`–`36`, same set as the table). Default `24`.

- **`GET /predictions/segment-rates`** — same query params as `/predictions` (`date`, `boat_class`, `sex`, `weight_class`, `direction`) plus **`hour_timestamp`** (ISO string matching an hour from the forecast) and **`segment_index`** (integer, river segment index). Returns all stroke-rate rows for that segment with **segment-local** wind decomposition and XGBoost residual (not cached; used when the map UI focuses on one segment).

Daily responses are cached under `cache_data/` (gitignored).

**USGS water temperature:** Flow remains **01104500** (Charles at Waltham). Default water-temp gauge is **422302071083801** (Fresh Pond, Cambridge) because the Waltham site does not serve parameter `00010` in IV. Set **`USGS_WATER_TEMP_SITE`** to another NWIS site id if needed.

## CORS

`app.py` allows `http://localhost:3000` and `http://127.0.0.1:3000` by default.

For a deployed frontend (e.g. Vercel), set a comma-separated list (no spaces required):

```bash
export CORS_ORIGINS=https://your-app.vercel.app,https://yourdomain.com
```

Restart uvicorn after changing this.
