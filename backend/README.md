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

## Run the API

```bash
cd backend
source .venv/bin/activate
uvicorn app:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/`
- Predictions: `GET http://127.0.0.1:8000/predictions?boat_class=1x&sex=men&weight_class=openweight&direction=upstream`

Daily responses are cached under `cache_data/` (gitignored).

## CORS

`app.py` allows browser calls from `http://localhost:3000` and `http://127.0.0.1:3000`. Add origins there if you deploy the frontend elsewhere.
