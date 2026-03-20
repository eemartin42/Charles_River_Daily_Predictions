import pandas as pd
from xgboost import XGBRegressor

from src.paths import MODELS_DIR
from src.train.generate_synthetic_data import generate_synthetic_data


def train_and_save_model(output_path: Path, n_samples: int = 8000) -> None:
    df = generate_synthetic_data(n_samples=n_samples)
    y = df["delta_split"].copy()
    X = pd.get_dummies(
        df.drop(columns=["delta_split"]),
        columns=["boat_class", "sex", "weight_class", "direction"],
        dtype=float,
    )

    model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        objective="reg:squarederror",
    )

    model.fit(X, y)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(output_path))

    feature_names = X.columns.tolist()
    metadata_path = output_path.with_suffix(".features.csv")
    pd.DataFrame({"feature_name": feature_names}).to_csv(metadata_path, index=False)


if __name__ == "__main__":
    target = MODELS_DIR / "xgb_delta.json"
    train_and_save_model(target)
    print(f"Saved model to {target}")

