import math
import os

from src.model.environment.wind import compute_wind_components

# Legacy fixed headings (optional reference only; segment-based headings preferred)
UPSTREAM_HEADING = 290.0
DOWNSTREAM_HEADING = 110.0

MPH_TO_MPS = 0.44704

def _flow_spatial_weight_min_from_env() -> float | None:
    """
    Basin (Longfellow) end: river-current effect from discharge scales to this fraction of the
    Watertown-dam end. Empty / unset = uniform current (legacy). Default ~0.28 if unset.
    """
    raw = os.environ.get("FLOW_SPATIAL_WEIGHT_MIN", "0.28").strip()
    if raw == "":
        return None
    try:
        v = float(raw)
        return max(0.0, min(1.0, v))
    except ValueError:
        return 0.28


def flow_spatial_scale_for_segment(segment_index: int, num_segments: int) -> float:
    """
    USGS gives one cfs for the reach; we approximate stronger current near the dam and weaker
    toward the tidal basin by scaling the derived current speed. Polyline order is
    Watertown → Longfellow (see GeoJSON / README): index 0 = dam side, last = basin.
    """
    w_min = _flow_spatial_weight_min_from_env()
    if w_min is None or num_segments <= 1:
        return 1.0
    t = segment_index / (num_segments - 1)
    return 1.0 - (1.0 - w_min) * t


PHYSICS_CONFIG = {
    "flow_k": 0.003,
    "flow_cap_mps": 0.3,
    "flow_downstream_asymmetry": 0.7,
    "temp_neutral_f": 70.0,
    "temp_c1": 0.1,
    "temp_c2": 0.04,
    "min_velocity": 0.1,
}

BOAT_FLOW_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.75, "8+": 0.6}
BOAT_TEMP_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.8, "8+": 0.7}
# Wind: fraction of wind-induced delta (vs pre-wind v) that is applied. Larger shells feel less
# proportional aero effect; must NOT scale absolute velocity (that inverted 8+ vs 1x ordering).
BOAT_WIND_PHYSICS_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.75, "8+": 0.6}


def split_to_velocity(split_seconds: float) -> float:
    return 500.0 / max(split_seconds, 1e-6)


def velocity_to_split(velocity: float) -> float:
    return 500.0 / max(velocity, PHYSICS_CONFIG["min_velocity"])


def flow_to_velocity(
    flow_cfs: float,
    k: float = PHYSICS_CONFIG["flow_k"],
    cap_mps: float = PHYSICS_CONFIG["flow_cap_mps"],
) -> float:
    v = k * (max(flow_cfs, 0.0) ** 0.5)
    return min(v, cap_mps)


def apply_temperature(v: float, temp_f: float, boat_class: str) -> float:
    t_n = PHYSICS_CONFIG["temp_neutral_f"]
    if temp_f < t_n:
        factor = 1.0 + PHYSICS_CONFIG["temp_c1"] * ((t_n - temp_f) / 20.0) ** 1.3
    else:
        factor = 1.0 - PHYSICS_CONFIG["temp_c2"] * ((temp_f - t_n) / 20.0)
    scaled = 1.0 + (factor - 1.0) * BOAT_TEMP_FACTOR[boat_class]
    return v / max(scaled, 0.01)


def apply_wind(
    v: float,
    headwind_mps: float,
    crosswind_mps: float,
    boat_class: str,
) -> float:
    """headwind_mps signed along boat axis; crosswind_mps magnitude for penalty."""
    v_safe = max(v, 1e-6)
    v_rel = v_safe + max(0.0, headwind_mps)
    drag_multiplier = 1.0 + 0.03 * (v_rel / v_safe) ** 2
    tailwind = max(0.0, -headwind_mps)
    tail_boost = 0.01 * tailwind
    cross_mag = abs(crosswind_mps)
    cross_penalty = 0.02 * (cross_mag**1.3)
    v_after_drag = v / drag_multiplier
    v_adjusted = v_after_drag + tail_boost - cross_penalty
    sensitivity = BOAT_WIND_PHYSICS_FACTOR[boat_class]
    # Blend toward wind-adjusted v so hull ordering from baseline is preserved (see module doc).
    return v + sensitivity * (v_adjusted - v)


def apply_flow(
    v: float,
    flow_cfs: float,
    direction: str,
    boat_class: str,
    *,
    flow_spatial_scale: float = 1.0,
) -> float:
    """flow_spatial_scale tapers apparent current from dam toward basin (see flow_spatial_scale_for_segment)."""
    scale = max(0.0, min(1.0, flow_spatial_scale))
    v_current = flow_to_velocity(flow_cfs) * scale
    if direction == "upstream":
        v_flow = v_current
    else:
        v_flow = -PHYSICS_CONFIG["flow_downstream_asymmetry"] * v_current
    return v - (v_flow * BOAT_FLOW_FACTOR[boat_class])


def compute_effective_velocity(
    baseline_split: float,
    temp_f: float,
    flow_cfs: float,
    headwind_mps: float,
    crosswind_mps: float,
    direction: str,
    boat_class: str,
    *,
    flow_spatial_scale: float = 1.0,
) -> float:
    """Unified pipeline: temperature -> wind -> flow. Wind in m/s."""
    v = split_to_velocity(baseline_split)
    v = apply_temperature(v, temp_f, boat_class)
    v = apply_wind(v, headwind_mps, crosswind_mps, boat_class)
    v = apply_flow(v, flow_cfs, direction, boat_class, flow_spatial_scale=flow_spatial_scale)
    return max(v, PHYSICS_CONFIG["min_velocity"])


def wind_features_for_river_axis_mps(
    wind_speed_mph: float,
    wind_dir_deg: float,
    river_axis_heading_deg: float,
) -> dict:
    """Wind components in m/s along river axis (signed headwind)."""
    wind_mps = max(0.0, wind_speed_mph) * MPH_TO_MPS
    return compute_wind_components(wind_mps, wind_dir_deg, river_axis_heading_deg)


def get_directional_features(
    wind_speed: float,
    wind_dir: float,
    flow_rate: float,
    water_temp: float,
    direction: str,
) -> dict:
    """Legacy aggregate using fixed headings (mph wind). Prefer segment-based pipeline."""
    if direction == "upstream":
        river_heading = UPSTREAM_HEADING
    else:
        river_heading = DOWNSTREAM_HEADING
    wind = compute_wind_components(wind_speed * MPH_TO_MPS, wind_dir, river_heading)
    return {
        **wind,
        "flow_rate": flow_rate,
        "water_temp": water_temp,
    }


def transform_environment(features: dict) -> dict:
    headwind = max(0.0, features["headwind"])
    return {
        "headwind_sq": headwind**2,
        "tailwind": features["tailwind"],
        "crosswind": features["crosswind"],
        "flow_rate": features["flow_rate"],
        "water_temp": features["water_temp"],
    }


def mean_feature_dict(feature_dicts: list[dict]) -> dict:
    """Average segment wind/flow/temp fields for XGB input."""
    if not feature_dicts:
        return {
            "headwind": 0.0,
            "tailwind": 0.0,
            "crosswind": 0.0,
            "flow_rate": 0.0,
            "water_temp": 60.0,
        }
    keys = ["headwind", "tailwind", "crosswind", "flow_rate", "water_temp"]
    out = {}
    for k in keys:
        out[k] = sum(d[k] for d in feature_dicts) / len(feature_dicts)
    return out
