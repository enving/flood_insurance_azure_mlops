# Flood Insurance Azure MLOps — Claude Kontext

## Wer arbeitet hier
Tristan — MLOps-Anfänger, wird bald verantwortlich für ML & KI-Platform in einem Versicherungsunternehmen.
Lernt am besten hands-on. Erkläre das Warum, nicht nur das Was. Fachbegriffe kurz erklären wenn neu.

## Was dieses Projekt ist
KI-gestütztes Hochwasserrisiko-Scoring für eine deutsche Versicherung.
Modell berechnet Prämien pro PLZ basierend auf Schadensdaten (RandomForest Regressor).
EU AI Act Klassifikation: **High-Risk KI** (finanzielle Entscheidungen, Artikel 6/7).

## Stack

### Azure (Lernumgebung)
- **Workspace:** `flood-insurance-workspace`
- **Resource Group:** `rg-flood-insurance-mvp`
- **Compute Cluster:** `flood-compute` (Standard_D2s_v3) — für Training Jobs
- **Compute Instance:** `flood-instance` (Standard_DS3_v2) — für Notebooks
- **Storage:** `floodinsstorage340058cf8`
- **Model Registry Name:** `hochwasser-scoring-model`

### Tools
- **MLflow** — Experiment Tracking, Model Registry (sklearn flavor, kein pickle!)
- **scikit-learn** — RandomForest Regressor
- **GitHub Actions** — CI/CD (`.github/workflows/train.yml`)
- **Azure ML Job** — Training via `src/job.yaml`

## Repo-Struktur
```
src/
├── train.py          # Training Script — RandomForest + MLflow Logging
├── job.yaml          # Azure ML Command Job Definition
├── quality_gate.py   # R² > 0.7 Gate (läuft nach Training)
└── sweep.yaml        # Hyperparameter Sweep Definition
.github/
└── workflows/
    └── train.yml     # CI/CD: Push → Azure ML Job → Model Registry
```

## Modell & Features
- `Hochwasserereignisse_pro_Jahr`, `Durchschnittlicher_Schaden_EUR`, `Anzahl_Versicherte`
- `Geographische_Hoehe_m`, `Naehe_zu_Fluss`, `Region_encoded`
- Target: `Schadensumme_pro_Jahr_EUR`
- Prämienkalkulation: `150 * (0.5 + risk_score / 100 * 2.0)`
- `high_risk = risk_score > 66` — EU AI Act Flag

## Konventionen
- Immer `mlflow.sklearn.log_model()` — niemals pickle (RAI Dashboard + Registry brauchen sklearn flavor)
- Signatur immer mit `mlflow.models.infer_signature()` setzen
- Pflicht-Metriken: `train_r2`, `test_r2`, `test_rmse`, `test_mae`, `overfit_gap`
- RAI Output: `outputs/test_data_for_rai.csv` mit Spalten `y_true`, `y_pred`, `risk_score`, `praemie_eur`, `high_risk`
- Quality Gate: R² > 0.7, Overfitting Gap < 0.15

## Git
- Branch: `enving/flood_insurance_azure_mlops`
- Remote: GitHub (Anthropic-internes Lernrepo)

## Nächste Lernschritte (Backlog)
1. FastAPI Inference Endpoint — Prämie per REST-Call ausgeben
2. Evidently Data Drift — wöchentlicher Drift-Report
3. Champion-Challenger — neues vs. aktuelles Modell vergleichen
4. Managed Online Endpoint in Azure ML
5. Responsible AI Dashboard einrichten (nach erstem echten Training-Run)
6. Model Card schreiben

## Hinweise für Claude
- Anfänger-kontext beachten: immer erklären was ein Befehl tut bevor er ausgeführt wird
- Self-Hosted First Prinzip: erst einfach, dann skalieren — kein Overkill
- Bei Fehlern: Ursache erklären, nicht nur fixen
- Nächsten konkreten Schritt immer nennen
