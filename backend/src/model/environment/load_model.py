import pandas as pd
from xgboost import XGBRegressor

from src.paths import MODELS_DIR


class DeltaModel:
    def __init__(self, model_path: str, features_path: str):
        self.model = XGBRegressor()
        self.model.load_model(model_path)
        features_df = pd.read_csv(features_path)
        self.feature_names = features_df["feature_name"].tolist()

    def predict_one(self, row: dict) -> float:
        x = pd.DataFrame([row])
        x = pd.get_dummies(
            x,
            columns=["boat_class", "sex", "weight_class", "direction"],
            dtype=float,
        )
        x = x.reindex(columns=self.feature_names, fill_value=0.0)
        prediction = self.model.predict(x)[0]
        return float(prediction)


def load_delta_model() -> DeltaModel:
    return DeltaModel(
        model_path=str(MODELS_DIR / "xgb_delta.json"),
        features_path=str(MODELS_DIR / "xgb_delta.features.csv"),
    )

