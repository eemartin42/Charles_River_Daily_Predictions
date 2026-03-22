# Charles River Daily Rowing Split Predictor

Full-stack app that predicts **500m split times** for the Charles River by combining:

- **Baseline curves** per boat class and category (men/women × openweight/lightweight), fit from ideal-condition tables in [`CST_tables/`](CST_tables/)
- **Environmental effects** via a **unified velocity pipeline** (water temperature drag scaling → aerodynamic wind → capped river current), then a small **XGBoost residual** on **segment-averaged** conditions
- **Segment-wise wind** using headings from a curated river polyline ([`backend/data/charles_river_rowing.geojson`](backend/data/charles_river_rowing.geojson)), with **length-weighted** aggregation for hourly table splits
- **Hourly tables** from [weather.gov](https://www.weather.gov/) (wind) and [USGS NWIS](https://waterservices.usgs.gov/) (discharge; water temperature when available)
- **Map view** (Next.js + Google Maps): colored river segments, wind arrows, click segments for details — requires `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`

Outputs are **seconds per 500m**; the web UI also shows splits as `m:ss.xx`.

## Repository layout

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI API, physics + model code |
| `backend/data/` | River `LineString` GeoJSON for segment headings + map path |
| `frontend/` | Next.js UI + map |
| `CST_tables/` | CSV baselines used to derive category split curves |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for Next.js)
- **macOS (Apple Silicon)**: XGBoost needs OpenMP — `brew install libomp` if import fails

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.train.train_xgb_delta
uvicorn app:app --reload --port 8000
```

If you skip the training step, the first API startup will **generate** `models/xgb_delta.json` automatically (short wait).

API: `http://127.0.0.1:8000` — use `GET /predictions` with query params (see below).

Paths to the trained model and daily cache are resolved from the `backend/` package directory, so this works regardless of your shell working directory.

**River geometry:** [`backend/data/charles_river_rowing.geojson`](backend/data/charles_river_rowing.geojson) is ordered **upstream (Watertown Dam) → downstream (Longfellow Bridge)** along the polyline (`[lng, lat]`). The committed centerline is built from **OpenStreetMap** (waterway, ODbL) for a water-following path; regenerate or refine with [`backend/scripts/build_charles_river_geojson_from_osm.py`](backend/scripts/build_charles_river_geojson_from_osm.py) or by **manual satellite trace** in [geojson.io](https://geojson.io) (draw on satellite, export GeoJSON, keep the same `Feature` + `LineString` shape). After changing geometry, **bump the prediction cache prefix** in `backend/app.py` and restart the API.

**Densification:** `RIVER_DENSIFY_STEPS` defaults to **`1`** (no extra subdivision) because the OSM line is already dense. Use **`3`–`5`** if you switch to a sparse polyline. **`0`** or **`1`** = use canonical vertices only. Segment headings use a **latitude-corrected** bearing plus **`RIVER_HEADING_SMOOTH_WINDOW`** (default `4`).

### 2. Frontend

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
export NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_key_here
npm run dev
```

Open `http://localhost:3000`. Enable **Maps JavaScript API** for that key and restrict it to your domains + `localhost`.

**Map stroke rate:** the UI sends `map_rate` (spm) to the API; per-segment splits in the JSON (and map colors) use that rate. The table still lists all stroke rates.

### “Failed to fetch” after pushing to GitHub

That message almost always means the **browser cannot reach your API** or **CORS** blocks the request. Pushing the repo does not host the backend.

1. **Host the API somewhere public** (Railway, Render, Fly.io, your VPS, etc.) and note its HTTPS URL, e.g. `https://your-api.onrender.com`.

2. **Tell the frontend where the API is** at **build time** (Next.js bakes in `NEXT_PUBLIC_*`):

   - Vercel / Netlify / similar: set env var  
     `NEXT_PUBLIC_API_BASE_URL=https://your-api.onrender.com`  
     then **redeploy** the frontend.

3. **Allow your frontend origin on the API** (CORS). On the backend host, set:

   ```bash
   export CORS_ORIGINS=https://your-app.vercel.app,https://www.yourdomain.com
   ```

   Then restart the API. Local `localhost` origins stay allowed by default.

4. **HTTPS page cannot call `http://localhost:8000`** — users’ browsers are not your laptop. Use the deployed API URL and `https`.

5. In the browser, open **DevTools → Network** (or Console): if you see a CORS error, fix `CORS_ORIGINS`; if **connection refused** / **Name not resolved**, fix `NEXT_PUBLIC_API_BASE_URL` and ensure the API is running.

### Example API request

```http
GET /predictions?boat_class=1x&sex=men&weight_class=openweight&direction=upstream&date=2026-03-20&map_rate=24
```

## Data sources (configured in code)

- Wind: `GET https://api.weather.gov/points/42.37,-71.06` → hourly forecast
- Flow: USGS **Charles River at Waltham** `01104500`, parameter `00060` (cfs)
- Water temp: USGS **Fresh Pond gate house, Cambridge** `422302071083801`, parameter `00010` (°C), converted to **°F** — the Waltham Charles discharge site does not publish instantaneous water temperature in NWIS IV; Fresh Pond is a nearby active gauge in the same basin. Override with env **`USGS_WATER_TEMP_SITE`** (NWIS site id) if you prefer another MA station (e.g. Stony Brook at Waltham `01104460`). Each forecast hour uses the **nearest observation in time** (or latest reading).

**Flow:** There is no forecast; the API uses the **latest observed discharge** for **every** hour in the selected forecast day so physics stays consistent.

**Flow along the course:** Public APIs (USGS NWIS, etc.) give **one discharge number** at the Waltham gage—not a velocity field along the river. Hydrodynamic models (HEC-RAS, estuary models) could estimate spatial variation but need calibration and aren’t wired here. Instead, physics applies a **simple linear taper** along the curated polyline (**Watertown Dam → Longfellow**): the derived current speed from cfs is **full strength near the dam** (segment index 0) and scales down toward the **basin end** (last segment). The basin end weight defaults to **28%** of the dam end (`FLOW_SPATIAL_WEIGHT_MIN=0.28`). Set **`FLOW_SPATIAL_WEIGHT_MIN=`** (empty) on the API process to disable the taper and use uniform current everywhere (legacy behavior).

## Model overview

1. `baseline_split(rate, …)` from parametric curves (α + β/rate + γ×rate) with parameters per category/boat.
2. For each river segment, wind vs **local segment heading** (downstream polyline order; upstream flips axis by 180°). Per segment: `split → velocity` → **temperature** → **wind** → **capped flow** (tapered along the reach from dam to basin; see **Flow along the course** above) → effective velocity → segment split. **Table** uses length-weighted mean velocity across segments, then `500/v̄`. Wind uses **hull-size sensitivity** on the wind-induced speed change (not a multiplier on absolute speed) so **8+ stays faster than 1x** under the same conditions.
3. XGBoost adds a small **residual** in seconds (trained on synthetic data) using **mean** head/tail/cross wind features across segments.

Tunable physics constants live in [`backend/src/model/environment/features.py`](backend/src/model/environment/features.py).


## License

Add a `LICENSE` file in the repo if you want to open-source formally.

## Further reading

- Backend details: [`backend/README.md`](backend/README.md)
- Frontend env: [`frontend/README.md`](frontend/README.md)
