from dataclasses import dataclass


@dataclass(frozen=True)
class CurveParams:
    alpha: float
    beta: float
    gamma: float


# Fitted from CST tables at rates 18/24/30.
BASELINE_PARAMS = {
    ("1x", "men", "openweight"): CurveParams(101.56, 504.0, -0.495),
    ("2x", "men", "openweight"): CurveParams(93.13, 464.4, -0.451667),
    ("4x", "men", "openweight"): CurveParams(86.025, 426.6, -0.419167),
    ("8+", "men", "openweight"): CurveParams(82.105, 412.2, -0.395833),
    ("1x", "women", "openweight"): CurveParams(110.52, 550.8, -0.536667),
    ("2x", "women", "openweight"): CurveParams(103.015, 513.0, -0.500833),
    ("4x", "women", "openweight"): CurveParams(94.905, 469.8, -0.464167),
    ("8+", "women", "openweight"): CurveParams(90.945, 455.4, -0.439167),
    ("1x", "men", "lightweight"): CurveParams(104.295, 523.8, -0.5025),
    ("2x", "men", "lightweight"): CurveParams(94.905, 469.8, -0.464167),
    ("4x", "men", "lightweight"): CurveParams(78.825, 394.2, -0.380833),
    ("1x", "women", "lightweight"): CurveParams(114.91, 572.4, -0.558333),
    ("2x", "women", "lightweight"): CurveParams(104.295, 523.8, -0.5025),
    ("4x", "women", "lightweight"): CurveParams(97.365, 484.2, -0.474167),
}

