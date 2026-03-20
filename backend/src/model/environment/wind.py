import math


def compute_wind_components(wind_speed: float, wind_dir: float, river_heading: float) -> dict:
    angle = math.radians(wind_dir - river_heading)
    headwind = wind_speed * math.cos(angle)
    crosswind = wind_speed * math.sin(angle)
    return {
        "headwind": headwind,
        "tailwind": max(0.0, -headwind),
        "crosswind": abs(crosswind),
    }

