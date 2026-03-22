import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.cache.daily_cache import DailyCache
from src.data.external.external_data_client import ExternalDataClient
from src.model.environment.load_model import load_delta_model
from src.model.geometry.river_path import load_river_segments
from src.predictions.compute_hourly_predictions import (
    RATES,
    compute_hourly_predictions,
    compute_rate_rows_for_segment,
)
from src.train.train_xgb_delta import ensure_residual_model_files


def _cors_allow_origins() -> list[str]:
    """Local dev defaults plus optional comma-separated CORS_ORIGINS (e.g. https://your-app.vercel.app)."""
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    extra = os.environ.get("CORS_ORIGINS", "").strip()
    if not extra:
        return defaults
    more = [o.strip().rstrip("/") for o in extra.split(",") if o.strip()]
    # Dedupe while preserving order (defaults first)
    seen: set[str] = set()
    out: list[str] = []
    for o in defaults + more:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


app = FastAPI(title="Charles River Daily Split Predictor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
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
    ensure_residual_model_files()
    delta_model = load_delta_model()
    load_river_segments()


@app.get("/predictions")
async def get_predictions(
    boat_class: Literal["1x", "2x", "4x", "8+"],
    sex: Literal["men", "women"],
    weight_class: Literal["openweight", "lightweight"],
    direction: Literal["upstream", "downstream"],
    query_date: str = Query(default_factory=lambda: date.today().isoformat(), alias="date"),
    map_rate: int = Query(24, description="Stroke rate used for per-segment map payload"),
):
    if map_rate not in RATES:
        raise HTTPException(
            status_code=400,
            detail=f"map_rate must be one of {RATES}",
        )

    cache_key = f"v12:{map_rate}:{query_date}:{boat_class}:{sex}:{weight_class}:{direction}"
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
        map_rate=map_rate,
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
            "map_rate": map_rate,
            "charles_speed_index": charles_speed_index,
        },
        "hourly": hourly,
    }
    daily_cache.set(cache_key, payload)
    return payload


def _find_hour_row(hourly_conditions: list[dict], hour_timestamp: str) -> dict | None:
    """Match API hour timestamp to a conditions row (flexible ISO equality)."""
    from dateutil import parser as date_parser

    target = None
    try:
        target = date_parser.isoparse(hour_timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    for row in hourly_conditions:
        ts = row.get("timestamp")
        if ts == hour_timestamp:
            return row
        if target is not None and ts is not None:
            try:
                r = date_parser.isoparse(str(ts).replace("Z", "+00:00"))
                if r == target:
                    return row
            except (ValueError, TypeError):
                continue
    return None


@app.get("/predictions/segment-rates")
async def get_segment_rates(
    boat_class: Literal["1x", "2x", "4x", "8+"],
    sex: Literal["men", "women"],
    weight_class: Literal["openweight", "lightweight"],
    direction: Literal["upstream", "downstream"],
    query_date: str = Query(..., alias="date"),
    hour_timestamp: str = Query(..., description="ISO timestamp matching hourly[].timestamp"),
    segment_index: int = Query(..., ge=0),
):
    """Per-segment stroke-rate table with segment-local wind decomposition and residual."""
    hourly_conditions = await external_client.fetch_hourly_conditions(query_date)
    row = _find_hour_row(hourly_conditions, hour_timestamp)
    if row is None:
        raise HTTPException(status_code=404, detail="Hour not found for date/timestamp")

    try:
        payload = compute_rate_rows_for_segment(
            hour_row=row,
            segment_index=segment_index,
            boat_class=boat_class,
            sex=sex,
            weight_class=weight_class,
            direction=direction,
            delta_model=delta_model,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return payload


@app.get("/")
async def root():
    return {"status": "ok", "message": "Use GET /predictions with query parameters."}

