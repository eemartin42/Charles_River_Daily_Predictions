from src.model.environment.wind import compute_wind_components

UPSTREAM_HEADING = 290.0
DOWNSTREAM_HEADING = 110.0

PHYSICS_CONFIG = {
    "flow_k": 0.003,
    "flow_downstream_asymmetry": 0.7,
    "temp_neutral_f": 70.0,
    "temp_c1": 0.08,
    "temp_c2": 0.04,
    "wind_head_coeff": 0.02,   # m/s per mph-equivalent component
    "wind_tail_coeff": 0.015,  # m/s per mph-equivalent component
    "wind_cross_coeff": 0.006, # m/s per mph-equivalent component
    "interaction_d": 0.2,
    "min_velocity": 0.1,
}

BOAT_FLOW_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.75, "8+": 0.6}
BOAT_TEMP_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.8, "8+": 0.7}
BOAT_WIND_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.75, "8+": 0.6}


def split_to_velocity(split_seconds: float) -> float:
    return 500.0 / max(split_seconds, 1e-6)


def velocity_to_split(velocity: float) -> float:
    return 500.0 / max(velocity, PHYSICS_CONFIG["min_velocity"])


def flow_to_velocity(flow_cfs: float, k: float = PHYSICS_CONFIG["flow_k"]) -> float:
    return k * (max(flow_cfs, 0.0) ** 0.5)


def compute_flow_velocity_effect(
    flow_cfs: float,
    direction: str,
    boat_class: str,
    asymmetry: float = PHYSICS_CONFIG["flow_downstream_asymmetry"],
) -> float:
    v_current = flow_to_velocity(flow_cfs)
    if direction == "upstream":
        v_flow = v_current
    else:
        v_flow = -v_current * asymmetry
    return v_flow * BOAT_FLOW_FACTOR[boat_class]


def temperature_drag_factor(
    temp_f: float,
    neutral_f: float = PHYSICS_CONFIG["temp_neutral_f"],
    c1: float = PHYSICS_CONFIG["temp_c1"],
    c2: float = PHYSICS_CONFIG["temp_c2"],
) -> float:
    if temp_f < neutral_f:
        return 1.0 + c1 * ((neutral_f - temp_f) / 20.0) ** 1.3
    return 1.0 - c2 * ((temp_f - neutral_f) / 20.0)


def apply_temperature_effect(v_baseline: float, temp_f: float, boat_class: str) -> float:
    factor = temperature_drag_factor(temp_f)
    scaled_factor = 1.0 + (factor - 1.0) * BOAT_TEMP_FACTOR[boat_class]
    return v_baseline / max(scaled_factor, 0.1)


def compute_wind_velocity_effect(
    headwind: float,
    tailwind: float,
    crosswind: float,
    boat_class: str,
    head_coeff: float = PHYSICS_CONFIG["wind_head_coeff"],
    tail_coeff: float = PHYSICS_CONFIG["wind_tail_coeff"],
    cross_coeff: float = PHYSICS_CONFIG["wind_cross_coeff"],
) -> float:
    scale = BOAT_WIND_FACTOR[boat_class]
    # Positive return means velocity penalty; negative means velocity boost.
    return scale * ((head_coeff * headwind) + (cross_coeff * crosswind) - (tail_coeff * tailwind))


def compute_effective_velocity(
    split_baseline: float,
    flow_cfs: float,
    temp_f: float,
    direction: str,
    boat_class: str,
    headwind: float,
    tailwind: float,
    crosswind: float,
    interaction_d: float = PHYSICS_CONFIG["interaction_d"],
) -> float:
    v_baseline = split_to_velocity(split_baseline)
    v_flow = compute_flow_velocity_effect(flow_cfs, direction, boat_class)
    v_temp_adjusted = apply_temperature_effect(v_baseline, temp_f, boat_class)
    v_wind = compute_wind_velocity_effect(headwind, tailwind, crosswind, boat_class)

    v_effective = v_temp_adjusted - v_flow - v_wind

    if interaction_d > 0.0:
        v_current = flow_to_velocity(flow_cfs)
        interaction = interaction_d * v_current * (1.0 / max(v_baseline, 0.1))
        v_effective -= interaction

    return max(v_effective, PHYSICS_CONFIG["min_velocity"])


def get_directional_features(
    wind_speed: float,
    wind_dir: float,
    flow_rate: float,
    water_temp: float,
    direction: str,
) -> dict:
    if direction == "upstream":
        river_heading = UPSTREAM_HEADING
        effective_flow = flow_rate
    else:
        river_heading = DOWNSTREAM_HEADING
        effective_flow = -flow_rate

    wind = compute_wind_components(wind_speed, wind_dir, river_heading)
    return {
        **wind,
        "flow_rate": effective_flow,
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

