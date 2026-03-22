from dateutil import parser as date_parser

from src.model.baseline.baseline_split import baseline_split
from src.model.environment.features import (
    compute_effective_velocity,
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
                v_eff = compute_effective_velocity(
                    baseline_split=base,
                    temp_f=row["water_temp"],
                    flow_cfs=row["flow_rate"],
                    headwind_mps=w["headwind"],
                    crosswind_mps=w["crosswind"],
                    direction=direction,
                    boat_class=boat_class,
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
                v_eff = compute_effective_velocity(
                    baseline_split=base_map,
                    temp_f=row["water_temp"],
                    flow_cfs=row["flow_rate"],
                    headwind_mps=w["headwind"],
                    crosswind_mps=w["crosswind"],
                    direction=direction,
                    boat_class=boat_class,
                )
                split_seg = velocity_to_split(v_eff)
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
                        "adjusted_split": round(split_seg, 2),
                        "delta": round(split_seg - base_map, 2),
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
