# 🌊 Flood Insurance Azure MLOps

KI-gestütztes Hochwasserrisiko-Scoring für Versicherungen — MLOps auf Azure ML.

## Struktur

```
src/
├── train.py      # Training Script (RandomForest, MLflow Logging)
└── job.yaml      # Azure ML Job Definition
.github/
└── workflows/
    └── train.yml # CI/CD: Push → Train → Register
```

## CI/CD Workflow

```
Push auf main (src/train.py geändert)
    → GitHub Actions startet
    → Azure ML Training Job auf flood-compute
    → MLflow loggt Metriken & Parameter
    → Modell landet in Azure ML Model Registry
```

## GitHub Secrets (einmalig einrichten)

In GitHub → Settings → Secrets → Actions:

| Secret | Wert |
|--------|------|
| `AZURE_CREDENTIALS` | Service Principal JSON (siehe unten) |
| `AZURE_RESOURCE_GROUP` | `rg-flood-insurance-mvp` |
| `AZURE_ML_WORKSPACE` | `flood-insurance-workspace` |

### Service Principal erstellen

```bash
az ad sp create-for-rbac \
  --name "flood-mlops-github" \
  --role contributor \
  --scopes /subscriptions/<SUB_ID>/resourceGroups/rg-flood-insurance-mvp \
  --sdk-auth
```

Output als `AZURE_CREDENTIALS` Secret speichern.

---

## ⚠️ Responsible AI (RAI) & EU AI Act — High Risk Template

### Warum ist dieses Modell "High Risk"?

Dieses Modell entscheidet über **Versicherungsprämien pro PLZ** — eine finanzielle Entscheidung die direkt Menschen betrifft. Gemäß EU AI Act Artikel 6/7 gilt:

> KI-Systeme, die über Zugang zu Versicherungsleistungen oder deren Preisgestaltung entscheiden → **Hochrisiko-KI**.

Das bedeutet: Dokumentationspflicht, Monitoring-Pflicht, menschliche Aufsicht, Auditfähigkeit.

### Was das Modell dazu bereitstellt

| Anforderung (EU AI Act) | Umsetzung hier |
|-------------------------|----------------|
| Technische Dokumentation | `model_metadata.json` + MLflow Run |
| Transparenz & Erklärbarkeit | Feature Importance via MLflow, RAI Dashboard |
| Daten-Governance | `test_data_for_rai.csv` mit `high_risk` Flag |
| Monitoring | Azure ML Model Monitoring (Data Drift) |
| Audit-Log | Jeder Training-Run in Azure ML Jobs geloggt |
| Menschliche Aufsicht | Quality Gate in `quality_gate.py` (R² > 0.7) |

### Responsible AI Dashboard einrichten (nach Training)

```bash
# Voraussetzung: Modell muss als MLflow sklearn flavor in Registry sein
# (passiert automatisch beim Training)

# 1. Dashboard per CLI erstellen
az ml responsible-ai-insight create \
  --resource-group rg-flood-insurance-mvp \
  --workspace-name flood-insurance-workspace \
  --model-name hochwasser-scoring-model \
  --model-version 1 \
  --train-dataset-path outputs/test_data_for_rai.csv \
  --target-column y_true \
  --task-type regression

# 2. Im Azure ML Studio sehen:
# Modelle → hochwasser-scoring-model → Verantwortungsvolle KI → Dashboard erstellen
```

### Was das RAI Dashboard zeigt

- **Error Analysis**: Wo macht das Modell die größten Fehler? (z.B. schlechter bei PLZs nahe Flüssen)
- **Feature Importance**: Welche Features treiben die Prämienentscheidung? (Transparenz)
- **Fairness**: Werden bestimmte Regionen (Nord/Mitte/Süd) systematisch anders behandelt?
- **Data Explorer**: Verteilung der `high_risk` PLZs

### High Risk Flag Logik

```python
# In train.py definiert:
high_risk = risk_score > 66   # Top-Drittel der riskantesten PLZs
# → Prämie > ~250€/Jahr
# → Diese Entscheidungen brauchen laut EU AI Act besondere Begründbarkeit
```

### Warum MLflow sklearn statt Pickle?

```
pickle.dump(model)          → rohe Bytes, Azure weiß nicht was drin ist
                               RAI Dashboard kann nicht auslesen
                               keine Input/Output-Signatur
                               Versionierung manuell

mlflow.sklearn.log_model()  → strukturiertes Format mit Schema
                               RAI Dashboard liest Feature Names automatisch
                               Input-Beispiele für Dokumentation eingebettet
                               Azure Model Registry versioniert automatisch
                               framework-unabhängiges Laden (mlflow.pyfunc)
```

---

## Lokaler Testlauf

```bash
cd src
pip install mlflow scikit-learn pandas numpy
python train.py --n_plzs 200 --n_estimators 100
# → outputs/test_data_for_rai.csv
# → outputs/model_metadata.json
# → MLflow Run in ./mlruns/ (lokal)
```
