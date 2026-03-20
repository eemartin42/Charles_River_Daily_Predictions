from src.model.baseline.baseline_params import BASELINE_PARAMS, CurveParams


def _evaluate_curve(rate: int, params: CurveParams) -> float:
    return params.alpha + (params.beta / rate) + (params.gamma * rate)


def _fallback_params(boat_class: str, sex: str, weight_class: str) -> CurveParams:
    key = (boat_class, sex, weight_class)
    if key in BASELINE_PARAMS:
        return BASELINE_PARAMS[key]

    # Lightweight 8+ rows are not available in CST tables.
    # Use openweight curve with a conservative additive slowdown.
    if boat_class == "8+" and weight_class == "lightweight":
        return BASELINE_PARAMS[(boat_class, sex, "openweight")]

    raise ValueError(f"Unsupported category combination: {key}")


def baseline_split(rate: int, boat_class: str, sex: str, weight_class: str) -> float:
    params = _fallback_params(boat_class, sex, weight_class)
    split = _evaluate_curve(rate, params)

    if boat_class == "8+" and weight_class == "lightweight":
        split += 2.0

    return round(split, 2)

