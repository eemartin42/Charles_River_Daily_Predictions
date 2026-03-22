from dateutil import parser as date_parser

from src.model.baseline.baseline_split import baseline_split
from src.model.environment.features import (
    compute_effective_velocity,
    flow_spatial_scale_for_segment,
    mean_feature_dict,
    transform_environment,
    velocity_to_split,
    wind_features_for_river_axis_mps,
)
from src.model.geometry.river_path import boat_axis_heading_for_segment, load_river_segments

RATES = [18, 20, 22, 24, 26, 28, 30, 32, 34, 36]


def _hour_of_day_from_timestamp(timestamp: str) -> int:
    try:
        return date_parser.isoparse(timestamp).hour
    except (ValueError, TypeError):
        return 12


async def compute_hourly_predictions(
    date_str: str,
    boat_class: str,
    sex: str,
    weight_class: str,
    direction: str,
    external_client,
    delta_model,
    map_rate: int = 24,
) -> list[dict]:
    hourly_conditions = await external_client.fetch_hourly_conditions(date_str)
    segments = load_river_segments()
    n_seg = len(segments)
    output = []

    for row in hourly_conditions:
        segment_env_rows: list[dict] = []
        for seg in segments:
            axis_deg = boat_axis_heading_for_segment(seg, direction)
            w = wind_features_for_river_axis_mps(
                row["wind_speed"],
                row["wind_dir"],
                axis_deg,
            )
            segment_env_rows.append(
                {
                    "headwind": w["headwind"],
                    "tailwind": w["tailwind"],
                    "crosswind": w["crosswind"],
                    "flow_rate": row["flow_rate"],
                    "water_temp": row["water_temp"],
                }
            )

        mean_feats = mean_feature_dict(segment_env_rows)
        transformed = transform_environment(mean_feats)
        hour_key = _hour_of_day_from_timestamp(row["timestamp"])

        rate_rows = []
        for rate in RATES:
            base = baseline_split(rate, boat_class, sex, weight_class)
            num_v = 0.0
            den_l = 0.0
            for seg in segments:
                axis_deg = boat_axis_heading_for_segment(seg, direction)
                w = wind_features_for_river_axis_mps(
                    row["wind_speed"],
                    row["wind_dir"],
                    axis_deg,
                )
                fs = flow_spatial_scale_for_segment(seg.index, n_seg)
                v_eff = compute_effective_velocity(
                    baseline_split=base,
                    temp_f=row["water_temp"],
                    flow_cfs=row["flow_rate"],
                    headwind_mps=w["headwind"],
                    crosswind_mps=w["crosswind"],
                    direction=direction,
                    boat_class=boat_class,
                    flow_spatial_scale=fs,
                )
                num_v += v_eff * seg.length_m
                den_l += seg.length_m
            v_bar = num_v / den_l if den_l > 0 else compute_effective_velocity(
                base,
                row["water_temp"],
                row["flow_rate"],
                0.0,
                0.0,
                direction,
                boat_class,
                flow_spatial_scale=1.0,
            )
            split_physics = velocity_to_split(v_bar)

            model_input = {
                **transformed,
                "boat_class": boat_class,
                "sex": sex,
                "weight_class": weight_class,
                "direction": direction,
                "hour_of_day": hour_key,
            }
            residual_delta = delta_model.predict_one(model_input)
            adjusted = split_physics + residual_delta
            delta = adjusted - base
            rate_rows.append(
                {
                    "rate": rate,
                    "baseline": round(base, 2),
                    "adjusted": round(adjusted, 2),
                    "delta": round(delta, 2),
                }
            )

        segments_payload: list[dict] = []
        if map_rate in RATES:
            base_map = baseline_split(map_rate, boat_class, sex, weight_class)
            for seg in segments:
                axis_deg = boat_axis_heading_for_segment(seg, direction)
                w = wind_features_for_river_axis_mps(
                    row["wind_speed"],
                    row["wind_dir"],
                    axis_deg,
                )
                fs = flow_spatial_scale_for_segment(seg.index, n_seg)
                v_eff = compute_effective_velocity(
                    baseline_split=base_map,
                    temp_f=row["water_temp"],
                    flow_cfs=row["flow_rate"],
                    headwind_mps=w["headwind"],
                    crosswind_mps=w["crosswind"],
                    direction=direction,
                    boat_class=boat_class,
                    flow_spatial_scale=fs,
                )
                split_physics = velocity_to_split(v_eff)
                # Match GET /predictions/segment-rates: segment-local env + XGBoost residual
                env_row = {
                    "headwind": w["headwind"],
                    "tailwind": w["tailwind"],
                    "crosswind": w["crosswind"],
                    "flow_rate": row["flow_rate"],
                    "water_temp": row["water_temp"],
                }
                transformed_seg = transform_environment(mean_feature_dict([env_row]))
                model_input = {
                    **transformed_seg,
                    "boat_class": boat_class,
                    "sex": sex,
                    "weight_class": weight_class,
                    "direction": direction,
                    "hour_of_day": hour_key,
                }
                residual_delta = delta_model.predict_one(model_input)
                adjusted_split = split_physics + residual_delta
                segments_payload.append(
                    {
                        "segment_index": seg.index,
                        "mid_lat": round(seg.mid_lat, 6),
                        "mid_lng": round(seg.mid_lng, 6),
                        "path": [
                            {"lat": seg.start_lat, "lng": seg.start_lng},
                            {"lat": seg.end_lat, "lng": seg.end_lng},
                        ],
                        "heading_deg": round(axis_deg, 2),
                        "headwind_mps": round(w["headwind"], 4),
                        "crosswind_mps": round(w["crosswind"], 4),
                        "baseline_split": round(base_map, 2),
                        "adjusted_split": round(adjusted_split, 2),
                        "delta": round(adjusted_split - base_map, 2),
                    }
                )

        output.append(
            {
                "timestamp": row["timestamp"],
                "wind_speed": row["wind_speed"],
                "wind_dir": row["wind_dir"],
                "wind_compass": row["wind_compass"],
                "wind_gust_mph": row["wind_gust_mph"],
                "flow_rate": row["flow_rate"],
                "water_temp": row["water_temp"],
                "map_rate": map_rate,
                "segments": segments_payload,
                "rows": rate_rows,
            }
        )

    return output


def compute_rate_rows_for_segment(
    hour_row: dict,
    segment_index: int,
    boat_class: str,
    sex: str,
    weight_class: str,
    direction: str,
    delta_model,
) -> dict:
    """
    Full stroke-rate table for one segment: physics on that segment's wind axis plus
    XGBoost residual from segment-local (not river-mean) environment features.
    """
    segments = load_river_segments()
    if segment_index < 0 or segment_index >= len(segments):
        raise ValueError("segment_index out of range")

    seg = segments[segment_index]
    axis_deg = boat_axis_heading_for_segment(seg, direction)
    w = wind_features_for_river_axis_mps(
        hour_row["wind_speed"],
        hour_row["wind_dir"],
        axis_deg,
    )
    env_row = {
        "headwind": w["headwind"],
        "tailwind": w["tailwind"],
        "crosswind": w["crosswind"],
        "flow_rate": hour_row["flow_rate"],
        "water_temp": hour_row["water_temp"],
    }
    mean_feats = mean_feature_dict([env_row])
    transformed = transform_environment(mean_feats)
    hour_key = _hour_of_day_from_timestamp(hour_row["timestamp"])

    rate_rows: list[dict] = []
    fs = flow_spatial_scale_for_segment(segment_index, len(segments))
    for rate in RATES:
        base = baseline_split(rate, boat_class, sex, weight_class)
        v_eff = compute_effective_velocity(
            baseline_split=base,
            temp_f=hour_row["water_temp"],
            flow_cfs=hour_row["flow_rate"],
            headwind_mps=w["headwind"],
            crosswind_mps=w["crosswind"],
            direction=direction,
            boat_class=boat_class,
            flow_spatial_scale=fs,
        )
        split_physics = velocity_to_split(v_eff)
        model_input = {
            **transformed,
            "boat_class": boat_class,
            "sex": sex,
            "weight_class": weight_class,
            "direction": direction,
            "hour_of_day": hour_key,
        }
        residual_delta = delta_model.predict_one(model_input)
        adjusted = split_physics + residual_delta
        delta = adjusted - base
        rate_rows.append(
            {
                "rate": rate,
                "baseline": round(base, 2),
                "adjusted": round(adjusted, 2),
                "delta": round(delta, 2),
            }
        )

    return {
        "segment_index": segment_index,
        "headwind_mps": round(w["headwind"], 4),
        "crosswind_mps": round(w["crosswind"], 4),
        "tailwind_mps": round(w["tailwind"], 4),
        "rows": rate_rows,
        "wind_speed": hour_row["wind_speed"],
        "wind_dir": hour_row["wind_dir"],
        "wind_compass": hour_row.get("wind_compass"),
    }
