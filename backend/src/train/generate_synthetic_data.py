import random

import pandas as pd

from src.model.environment.features import get_directional_features, transform_environment

BOATS = ["1x", "2x", "4x", "8+"]
SEXES = ["men", "women"]
WEIGHTS = ["openweight", "lightweight"]
DIRECTIONS = ["upstream", "downstream"]

BOAT_FACTOR = {"1x": 1.0, "2x": 0.9, "4x": 0.75, "8+": 0.6}
SEX_FACTOR = {"men": 1.0, "women": 1.08}
WEIGHT_FACTOR = {"openweight": 1.0, "lightweight": 1.12}

# Sensible defaults; tune with observed data later.
K1 = 0.015
K2 = 0.0008
K3 = 0.06
K4 = 0.08


def generate_synthetic_data(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    rows = []

    for _ in range(n_samples):
        wind_speed = random.uniform(0, 20)
        wind_dir = random.uniform(0, 360)
        flow_rate = random.uniform(0, 5000)
        water_temp = random.uniform(40, 75)
        boat_class = random.choice(BOATS)
        sex = random.choice(SEXES)
        weight_class = random.choice(WEIGHTS)
        direction = random.choice(DIRECTIONS)
        hour_of_day = random.randint(0, 23)

        directional = get_directional_features(
            wind_speed=wind_speed,
            wind_dir=wind_dir,
            flow_rate=flow_rate,
            water_temp=water_temp,
            direction=direction,
        )
        transformed = transform_environment(directional)

        delta = (
            K1 * transformed["headwind_sq"]
            + K2 * transformed["flow_rate"]
            + K3 * transformed["crosswind"]
            - K4 * transformed["tailwind"]
        )
        delta *= BOAT_FACTOR[boat_class]
        delta *= SEX_FACTOR[sex]
        delta *= WEIGHT_FACTOR[weight_class]

        rows.append(
            {
                **transformed,
                "boat_class": boat_class,
                "sex": sex,
                "weight_class": weight_class,
                "direction": direction,
                "hour_of_day": hour_of_day,
                "delta_split": delta,
            }
        )

    return pd.DataFrame(rows)

