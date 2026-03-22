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

**River geometry:** [`backend/data/charles_river_rowing.geojson`](backend/data/charles_river_rowing.geojson) is ordered **upstream (Watertown Dam) → downstream (Longfellow Bridge)** along the polyline. The API **densifies** that line (linear interpolation in lng/lat) for smoother headings and more map segments. Set `RIVER_DENSIFY_STEPS` (default `5`; use `0` or `1` to use the sparse file vertices only). Higher values produce more segments. Segment headings use a **latitude-corrected** bearing plus optional **`RIVER_HEADING_SMOOTH_WINDOW`** (default `4`) so wind decomposition matches the river on E–W sections.

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
- Flow: USGS site `01104500`, parameter `00060` (cfs)
- Water temp: same site, parameter `00010` (when published)

**Flow:** There is no forecast; the API uses the **latest observed discharge** for **every** hour in the selected forecast day so physics stays consistent.

## Model overview

1. `baseline_split(rate, …)` from parametric curves (α + β/rate + γ×rate) with parameters per category/boat.
2. For each river segment, wind vs **local segment heading** (downstream polyline order; upstream flips axis by 180°). Per segment: `split → velocity` → **temperature** → **wind** → **capped flow** → effective velocity → segment split. **Table** uses length-weighted mean velocity across segments, then `500/v̄`.
3. XGBoost adds a small **residual** in seconds (trained on synthetic data) using **mean** head/tail/cross wind features across segments.

Tunable physics constants live in [`backend/src/model/environment/features.py`](backend/src/model/environment/features.py).

## Publishing to GitHub

1. Create a new empty repository on GitHub (no README/license if you want a clean first push).

2. From the **project root** (this folder):

```bash
git init
git add .
git commit -m "Initial commit: Charles River split predictor"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

3. **Do not commit secrets** — this project uses public weather/USGS endpoints only.

A [`.gitignore`](.gitignore) is included for virtualenvs, `node_modules`, caches, and local artifacts.

## License

Add a `LICENSE` file in the repo if you want to open-source formally.

## Further reading

- Backend details: [`backend/README.md`](backend/README.md)
- Frontend env: [`frontend/README.md`](frontend/README.md)
