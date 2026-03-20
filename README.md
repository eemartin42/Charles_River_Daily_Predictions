# Charles River Daily Rowing Split Predictor

Full-stack app that predicts **500m split times** for the Charles River by combining:

- **Baseline curves** per boat class and category (men/women × openweight/lightweight), fit from ideal-condition tables in [`CST_tables/`](CST_tables/)
- **Environmental effects** via a **velocity-based physics model** (flow, water temperature, wind), then a small **XGBoost residual** trained on synthetic data
- **Hourly tables** from [weather.gov](https://www.weather.gov/) (wind) and [USGS NWIS](https://waterservices.usgs.gov/) (discharge; water temperature when available)

Outputs are **seconds per 500m**; the web UI also shows splits as `m:ss.xx`.

## Repository layout

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI API, physics + model code |
| `frontend/` | Next.js UI |
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

API: `http://127.0.0.1:8000` — use `GET /predictions` with query params (see below).

Paths to the trained model and daily cache are resolved from the `backend/` package directory, so this works regardless of your shell working directory.

### 2. Frontend

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

Open `http://localhost:3000`.

### Example API request

```http
GET /predictions?boat_class=1x&sex=men&weight_class=openweight&direction=upstream&date=2026-03-20
```

## Data sources (configured in code)

- Wind: `GET https://api.weather.gov/points/42.37,-71.06` → hourly forecast
- Flow: USGS site `01104500`, parameter `00060` (cfs)
- Water temp: same site, parameter `00010` (when published)

**Flow:** There is no forecast; the API uses the **latest observed discharge** for **every** hour in the selected forecast day so physics stays consistent.

## Model overview

1. `baseline_split(rate, …)` from parametric curves (α + β/rate + γ×rate) with parameters per category/boat.
2. `split → velocity (m/s)` → apply flow / temperature / wind in velocity space → `velocity → split`.
3. XGBoost adds a small **residual** in seconds (trained offline from synthetic data).

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
