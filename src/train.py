"""
train.py — Hochwasser-Scoring MLOps
Wird von Azure ML als Command Job ausgeführt.
Liest Hyperparameter als CLI-Args, loggt alles via MLflow.
"""
import argparse, json, pickle
import numpy as np
import pandas as pd
import mlflow
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def generate_data(n: int, seed: int) -> pd.DataFrame:
    np.random.seed(seed)
    df = pd.DataFrame({
        "PLZ":                            np.random.randint(10000, 99999, n),
        "Region":                         np.random.choice(["Nord", "Mitte", "Süd"], n),
        "Hochwasserereignisse_pro_Jahr":  np.random.beta(2, 5, n) * 5,
        "Durchschnittlicher_Schaden_EUR": np.random.lognormal(10, 1.5, n),
        "Anzahl_Versicherte":             np.random.randint(10, 500, n),
        "Geographische_Hoehe_m":          np.random.uniform(0, 1500, n),
        "Naehe_zu_Fluss":                np.random.choice([0, 1], n, p=[0.6, 0.4]),
    })
    df["Schadensumme_pro_Jahr_EUR"] = (
        df["Hochwasserereignisse_pro_Jahr"] * df["Durchschnittlicher_Schaden_EUR"]
        * df["Anzahl_Versicherte"] / 100
        + df["Naehe_zu_Fluss"] * 50000
        + (1500 - df["Geographische_Hoehe_m"]) * 10
        + np.random.normal(0, 20000, n)
    ).clip(lower=0)
    return df


def main(args):
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = generate_data(args.n_plzs, args.seed)
    le = LabelEncoder()
    df["Region_encoded"] = le.fit_transform(df["Region"])

    features = [
        "Hochwasserereignisse_pro_Jahr", "Durchschnittlicher_Schaden_EUR",
        "Anzahl_Versicherte", "Geographische_Hoehe_m",
        "Naehe_zu_Fluss", "Region_encoded",
    ]
    X, y = df[features], df["Schadensumme_pro_Jahr_EUR"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=args.seed
    )

    # MLflow: Parameter
    mlflow.log_params({
        "n_plzs":             args.n_plzs,
        "n_estimators":       args.n_estimators,
        "max_depth":          args.max_depth,
        "min_samples_split":  args.min_samples_split,
        "min_samples_leaf":   args.min_samples_leaf,
        "seed":               args.seed,
    })

    # Training
    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_split=args.min_samples_split,
        min_samples_leaf=args.min_samples_leaf,
        random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    y_pred       = model.predict(X_test)
    y_pred_train = model.predict(X_train)   # für Overfitting-Detektion

    # MLflow: Metriken
    metrics = {
        "train_r2":  round(r2_score(y_train, y_pred_train), 4),   # Overfitting-Indikator
        "test_r2":   round(r2_score(y_test, y_pred), 4),
        "test_rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 2),
        "test_mae":  round(float(mean_absolute_error(y_test, y_pred)), 2),
        "overfit_gap": round(
            r2_score(y_train, y_pred_train) - r2_score(y_test, y_pred), 4
        ),
    }
    mlflow.log_metrics(metrics)
    for feat, imp in zip(features, model.feature_importances_):
        mlflow.log_metric(f"importance_{feat}", round(float(imp), 4))

    print(f"train_r2={metrics['train_r2']}  test_r2={metrics['test_r2']}  "
          f"overfit_gap={metrics['overfit_gap']}  RMSE={metrics['test_rmse']:,.0f}€")

    # Outputs in output_dir (Azure ML erfasst automatisch)
    with open(out / "flood_model.pkl", "wb") as f:
        pickle.dump(model, f)
    (out / "model_metadata.json").write_text(
        json.dumps({**metrics, "features": features, "basis_praemie_eur": 150}, indent=2)
    )
    print(f"✅ Outputs gespeichert → {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n_plzs",            type=int, default=500)
    p.add_argument("--n_estimators",     type=int, default=100)
    p.add_argument("--max_depth",        type=int, default=15)
    p.add_argument("--min_samples_split",type=int, default=2)
    p.add_argument("--min_samples_leaf", type=int, default=1)
    p.add_argument("--seed",             type=int, default=42)
    p.add_argument("--output_dir",       type=str, default="outputs")
    with mlflow.start_run():
        main(p.parse_args())
