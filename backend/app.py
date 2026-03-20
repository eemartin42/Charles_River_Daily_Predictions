from datetime import date
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from src.cache.daily_cache import DailyCache
from src.data.external.external_data_client import ExternalDataClient
from src.model.environment.load_model import load_delta_model
from src.predictions.compute_hourly_predictions import compute_hourly_predictions

app = FastAPI(title="Charles River Daily Split Predictor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

external_client = ExternalDataClient()
daily_cache = DailyCache()
delta_model = None


@app.on_event("startup")
async def startup_event():
    global delta_model
    delta_model = load_delta_model()


@app.get("/predictions")
async def get_predictions(
    boat_class: Literal["1x", "2x", "4x", "8+"],
    sex: Literal["men", "women"],
    weight_class: Literal["openweight", "lightweight"],
    direction: Literal["upstream", "downstream"],
    query_date: str = Query(default_factory=lambda: date.today().isoformat(), alias="date"),
):
    # Bump when hourly inputs (e.g. flow projection) change so disk cache does not
    # serve stale per-hour flow.
    cache_key = f"v2:{query_date}:{boat_class}:{sex}:{weight_class}:{direction}"
    cached = daily_cache.get(cache_key)
    if cached is not None:
        return cached

    hourly = await compute_hourly_predictions(
        date_str=query_date,
        boat_class=boat_class,
        sex=sex,
        weight_class=weight_class,
        direction=direction,
        external_client=external_client,
        delta_model=delta_model,
    )

    all_deltas = [r["delta"] for hour in hourly for r in hour["rows"]]
    charles_speed_index = round(sum(all_deltas) / max(1, len(all_deltas)), 2)

    payload = {
        "meta": {
            "date": query_date,
            "boat_class": boat_class,
            "sex": sex,
            "weight_class": weight_class,
            "direction": direction,
            "charles_speed_index": charles_speed_index,
        },
        "hourly": hourly,
    }
    daily_cache.set(cache_key, payload)
    return payload


@app.get("/")
async def root():
    return {"status": "ok", "message": "Use GET /predictions with query parameters."}

