from src.model.baseline.baseline_split import baseline_split
from src.model.environment.features import (
    compute_effective_velocity,
    get_directional_features,
    transform_environment,
    velocity_to_split,
)

RATES = [18, 20, 22, 24, 26, 28, 30, 32, 34, 36]


async def compute_hourly_predictions(
    date_str: str,
    boat_class: str,
    sex: str,
    weight_class: str,
    direction: str,
    external_client,
    delta_model,
) -> list[dict]:
    hourly_conditions = await external_client.fetch_hourly_conditions(date_str)
    output = []

    for row in hourly_conditions:
        directional = get_directional_features(
            wind_speed=row["wind_speed"],
            wind_dir=row["wind_dir"],
            flow_rate=row["flow_rate"],
            water_temp=row["water_temp"],
            direction=direction,
        )
        transformed = transform_environment(directional)

        rate_rows = []
        for rate in RATES:
            base = baseline_split(rate, boat_class, sex, weight_class)
            v_effective = compute_effective_velocity(
                split_baseline=base,
                flow_cfs=row["flow_rate"],
                temp_f=row["water_temp"],
                direction=direction,
                boat_class=boat_class,
                headwind=directional["headwind"],
                tailwind=directional["tailwind"],
                crosswind=directional["crosswind"],
            )
            split_physics = velocity_to_split(v_effective)

            model_input = {
                **transformed,
                "boat_class": boat_class,
                "sex": sex,
                "weight_class": weight_class,
                "direction": direction,
                "hour_of_day": int(row["timestamp"][11:13]),
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

        output.append(
            {
                "timestamp": row["timestamp"],
                "wind_speed": row["wind_speed"],
                "wind_dir": row["wind_dir"],
                "flow_rate": row["flow_rate"],
                "water_temp": row["water_temp"],
                "rows": rate_rows,
            }
        )

    return output

