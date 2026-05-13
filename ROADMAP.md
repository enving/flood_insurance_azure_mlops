# Flood Insurance MLOps — Roadmap & PRD

> Dieses Dokument beschreibt den aktuellen Stand der MLOps-Infrastruktur,
> die Zielbild-Architektur und den priorisierten Backlog.
> Basis: KI-gestütztes Hochwasserrisiko-Scoring pro PLZ für eine Versicherung.

---

## Aktueller Stand ✅

### Was live ist (Azure, Stand Mai 2026)

| Ressource | Name | Details |
|---|---|---|
| Resource Group | `rg-flood-insurance-mvp` | westeurope |
| ML Workspace | `flood-insurance-workspace` | |
| Compute Cluster | `flood-compute` | Standard_D2s_v3, 0–4 Nodes, für Jobs |
| Compute Instance | `flood-instance` | Standard_DS3_v2, für interaktives Arbeiten |
| Model Registry | `hochwasser-scoring-model` | v1 (manuell), v2+ (via CI/CD) |

### Was die Pipeline heute kann

```
git push (src/train.py oder src/sweep.yaml geändert)
         ↓
GitHub Actions (.github/workflows/train.yml)
         ↓
HyperDrive Sweep (src/sweep.yaml)
  • Bayesian Search: n_estimators, max_depth, min_samples_split, min_samples_leaf
  • Bandit Early Termination (slack_factor=0.15, delay=3)
  • Max 20 Trials, 4 parallel, 90min Timeout
         ↓
Quality Gate (src/quality_gate.py)
  • test_r2 >= 0.80
  • overfit_gap <= 0.10
         ↓
Model Registry (stage=staging, tags: git_sha, test_r2, sweep_job)
```

### Was geloggt wird (MLflow, pro Run)

- **Parameter:** n_plzs, n_estimators, max_depth, min_samples_split, min_samples_leaf, seed
- **Metriken:** train_r2, test_r2, test_rmse, test_mae, overfit_gap, feature importances
- **Artefakte:** flood_model.pkl, model_metadata.json (im Job Output `model_dir`)

### Aktuell nicht vorhanden

- Echte Daten (synthetische Datengenerierung in train.py)
- Data Asset als deklarierter Job-Input (kein Lineage-Tracking)
- Azure ML Pipeline (nur Einzeljob + GitHub Actions als äußerer Loop)
- Deployment (kein Endpoint, kein Scoring-API)
- Monitoring (kein Drift-Check, kein Alert)

---

## Zielbild-Architektur

```
┌──────────────────────────────────────────────────────────────────┐
│ OUTER LOOP — GitHub Actions                                      │
│  Trigger: git push / cron / drift-webhook                        │
│  Aufgabe: Auth, Reporting, Deployment-Gate (manual approve)      │
│                                                                  │
│  └── az ml job create --file src/pipeline.yaml                   │
│                   ↓                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ INNER LOOP — Azure ML Pipeline (4 Steps)                   │  │
│  │                                                            │  │
│  │  Step 1: data_prep    Schema-Check, Feature Validation     │  │
│  │          Input:  azureml:flood-raw-data:latest             │  │
│  │          Output: clean_data (uri_folder)                   │  │
│  │                                                            │  │
│  │  Step 2: train/sweep  HyperDrive (wie heute)               │  │
│  │          Input:  clean_data                                │  │
│  │          Output: model_dir                                 │  │
│  │                                                            │  │
│  │  Step 3: evaluate     Champion-Challenger                  │  │
│  │          Input:  model_dir + champion (Registry latest)    │  │
│  │          Output: decision (go / no-go JSON)                │  │
│  │                                                            │  │
│  │  Step 4: register     Nur wenn decision=go                 │  │
│  │          Tags: stage=staging, git_sha, test_r2             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                   ↓                                              │
│  stage=staging → manueller Approve → stage=production            │
└──────────────────────────────────────────────────────────────────┘
          ↑
          │ Retraining-Trigger
          │
┌─────────────────────────────┐
│ Azure ML Monitor Job        │
│  (täglich, scheduled)       │
│  Jensen-Shannon Drift > 0.1 │
│  → Azure Monitor Alert      │
│  → Webhook → GH Actions     │
└─────────────────────────────┘
          ↑
          │ scored von
          │
┌─────────────────────────────┐
│ Managed Online Endpoint     │
│  REST API: PLZ → Prämie     │
│  Blue/Green Deployment      │
│  Application Insights       │
└─────────────────────────────┘
```

---

## Backlog (priorisiert)

### P1 — Nächste sinnvolle Schritte

| # | Feature | Warum wichtig | Aufwand |
|---|---|---|---|
| 1 | **Champion-Challenger** in `quality_gate.py` | Verhindert Regression: neues Modell muss besser sein als aktuell registered | ~1h |
| 2 | **Azure ML Pipeline** (`src/pipeline.yaml` + 4 Components) | Compliance/Lineage, Step-Caching, Wiederverwendbarkeit | ~3h |
| 3 | **Staging → Production Gate** (GitHub Environments + manual approve) | Kein automatischer Prod-Rollout ohne Vier-Augen-Prinzip | ~30min |

### P2 — Wenn echte Daten da sind

| # | Feature | Warum wichtig | Aufwand |
|---|---|---|---|
| 4 | **Data Asset registrieren** (`az ml data create`) + als Job-Input deklarieren | Datensatz-Lineage: welche Daten → welches Modell | ~1h |
| 5 | **Data Validation Step** (Great Expectations oder einfaches Schema-Check-Script) | Kein Training auf korrupten Daten | ~1h |
| 6 | **Model Card** (Markdown, auto-generiert nach Training) | EU AI Act Dokumentationspflicht für High-Risk-AI | ~30min |

### P3 — Wenn Endpoint deployed

| # | Feature | Aufwand |
|---|---|---|
| 7 | **Managed Online Endpoint** (`src/endpoint.yaml` + `src/deployment.yaml`) | ~1h |
| 8 | **Azure ML Monitor Job** (Drift-Check, scheduled) | ~2h |
| 9 | **Drift → Webhook → Retraining** (automatischer Trigger) | ~1h |
| 10 | **Rollback-Logik** (auto-rollback bei Endpoint-Degradation) | ~2h |

---

## Datei-Übersicht (aktuell)

```
flood_insurance_azure_mlops/
├── src/
│   ├── train.py           Trainings-Script (RandomForest, MLflow Logging)
│   ├── job.yaml           Einzeljob-Definition (Legacy, wird durch pipeline.yaml ersetzt)
│   ├── sweep.yaml         HyperDrive Sweep (Bayesian, Bandit Early Termination)
│   └── quality_gate.py    Quality Gate: R²-Check + Overfitting-Check
├── .github/
│   └── workflows/
│       └── train.yml      CI/CD: Sweep → Quality Gate → Register
└── ROADMAP.md             dieses Dokument
```

---

## Offene Designentscheidungen

1. **Echte Daten**: Kommen die aus Azure Blob Storage, einer Datenbank, oder einem Data Lakehouse (Fabric/ADLS)?
   Antwort bestimmt: Data Asset Type, Datastore-Konfiguration, ggf. Arc für lokale Daten.

2. **Endpoint-Strategie**: Echtzeit (Managed Online Endpoint, ~0.10€/h) oder Batch (Batch Endpoint, nur Compute-Kosten)?
   Für Versicherungs-Scoring: wahrscheinlich Batch (nächtlicher Scoring-Job über alle PLZs).

3. **Arc / Hybrid**: Wenn Rohdaten DSGVO-kritisch sind und lokal bleiben müssen →
   Arc-enabled Kubernetes als Compute Target statt Azure Cloud Compute.

4. **Azure ML Pipeline vs. Databricks**: Bei sehr großen Datenmengen (>100GB Feature Store) ist
   Databricks + MLflow auf Azure manchmal pragmatischer als native Azure ML Pipelines.
