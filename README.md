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
