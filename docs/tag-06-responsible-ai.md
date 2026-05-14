# Tag 6 — Responsible AI & Governance in Azure

> Ziel: RAI Dashboard, RBAC, Audit-Logging und EU AI Act-Kategorisierung im Azure-Kontext verstehen.

---

## RAI Dashboard: Was es kann (und was nicht)

Das Azure Responsible AI Dashboard ist ein **Analyse-Werkzeug**, kein Compliance-Zertifikat. Es zeigt wo dein Modell Probleme hat — es löst sie nicht.

**Wichtig:** Das RAI Dashboard funktioniert nur mit MLflow sklearn flavor. Das ist der Grund warum wir in `train.py` `mlflow.sklearn.log_model()` statt `pickle` nutzen.

### Die 6 Säulen (konkret für Hochwasser-Modell)

| Säule | Was Azure zeigt | Konkretes Beispiel |
|---|---|---|
| **Fairness** | Systematisch mehr Fehler bei bestimmten Gruppen? | Werden PLZs in "Süd" bei gleichem Risiko anders bepreist als "Nord"? |
| **Reliability** | Wo versagt das Modell am häufigsten? | Error Analysis: bei welchen Feature-Kombinationen ist RMSE besonders hoch? |
| **Privacy** | Sensible Attribute im Modell? | Nicht direkt messbar — muss manuell geprüft werden |
| **Inclusiveness** | Unterrepräsentierte Gruppen? | Haben wir genug PLZs aus allen Regionen im Training? |
| **Transparency** | Welche Features treiben die Entscheidung? | SHAP: dominieren `Naehe_zu_Fluss` und `Geographische_Hoehe_m`? |
| **Accountability** | Wer hat wann welche Entscheidung getroffen? | MLflow Run-History + Git-Commits als Audit-Trail |

### RAI Dashboard erstellen (nach Training)

```bash
az ml responsible-ai-insight create \
  --resource-group rg-flood-insurance-mvp \
  --workspace-name flood-insurance-workspace \
  --model-name hochwasser-scoring-model \
  --model-version 1 \
  --train-dataset-path outputs/test_data_for_rai.csv \
  --target-column y_true \
  --task-type regression
```

---

## RBAC: Rollen & Rechte in Azure ML

### Rollenmodell für eine Versicherung

```
Azure ML Workspace: flood-insurance-workspace
│
├── IT-Team          → Contributor          (alles: Compute, Deploy, löschen)
├── Fachbereich      → AzureML Data Scientist (Experimente starten, KEINE Cluster erstellen)
├── Externer Dev     → Custom Role           (deployen, KEINE Data Assets sehen)
└── Compliance       → Reader               (Read-Only auf alles, für Audits)
```

### Fachbereich-Analysten zuweisen

```bash
az role assignment create \
  --assignee "analyst@versicherung.de" \
  --role "AzureML Data Scientist" \
  --scope "/subscriptions/<SUB_ID>/resourceGroups/rg-flood-insurance-mvp/providers/Microsoft.MachineLearningServices/workspaces/flood-insurance-workspace"
```

### Custom Role für externen Dienstleister

```json
{
  "Name": "MLOps Deployer (Extern)",
  "Description": "Darf Modelle deployen, aber keine Daten-Assets sehen",
  "Actions": [
    "Microsoft.MachineLearningServices/workspaces/models/read",
    "Microsoft.MachineLearningServices/workspaces/models/write",
    "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/*"
  ],
  "NotActions": [
    "Microsoft.MachineLearningServices/workspaces/datasets/*",
    "Microsoft.MachineLearningServices/workspaces/datastores/*"
  ]
}
```

```bash
az role definition create --role-definition mlops-deployer-extern.json
```

---

## Auditfähigkeit

### Was automatisch geloggt wird

Azure ML loggt alle Control-Plane-Aktionen im Activity Log:
- Wer hat wann welches Modell registriert
- Wer hat einen Endpoint erstellt oder gelöscht
- Wer hat Compute gestartet/gestoppt

### Diagnostic Settings einrichten (90 Tage Aufbewahrung)

```bash
az monitor diagnostic-settings create \
  --name "ml-audit-logs" \
  --resource "/subscriptions/<SUB>/resourceGroups/rg-flood-insurance-mvp/providers/Microsoft.MachineLearningServices/workspaces/flood-insurance-workspace" \
  --logs '[
    {"category":"AmlComputeClusterEvent","enabled":true},
    {"category":"AmlRunStatusChangedEvent","enabled":true},
    {"category":"ModelsChangeEvent","enabled":true},
    {"category":"DeploymentEventACI","enabled":true}
  ]' \
  --workspace "/subscriptions/<SUB>/resourceGroups/rg-flood-insurance-mvp/providers/Microsoft.OperationalInsights/workspaces/flood-log-analytics"
```

### KQL — Alle Modell-Deployments der letzten 30 Tage

```kql
AzureActivity
| where TimeGenerated > ago(30d)
| where ResourceProvider == "Microsoft.MachineLearningServices"
| where OperationNameValue contains "MICROSOFT.MACHINELEARNINGSERVICES/WORKSPACES/MODELS/WRITE"
    or OperationNameValue contains "MICROSOFT.MACHINELEARNINGSERVICES/WORKSPACES/ONLINEENDPOINTS/WRITE"
| project
    Zeitpunkt    = TimeGenerated,
    Aktion       = OperationNameValue,
    Benutzer     = Caller,
    Ergebnis     = ActivityStatusValue,
    Details      = Properties
| order by Zeitpunkt desc
```

---

## EU AI Act Praxis

### Die 4 Risikoklassen

| Klasse | Beispiele | Pflichten |
|---|---|---|
| **Verboten** | Social Scoring durch Behörden, biometrische Massenüberwachung | Darf nicht betrieben werden |
| **High Risk** | KI für Versicherungsprämien, Kreditentscheidungen, HR-Scoring | Dokumentation, Monitoring, menschliche Aufsicht, Registrierung |
| **Transparenzpflicht** | Chatbots, Deepfakes | Muss als KI kenntlich gemacht werden |
| **Minimales Risiko** | Spam-Filter, Empfehlungssysteme | Keine Pflichten |

### Hochwasser-Modell = High Risk

Artikel 6 Absatz 2, Anhang III, Punkt 5b: *"KI-Systeme zur Bewertung von Risiken und zur Preisfestlegung bei Lebens- und Krankenversicherungen"* — Prämienentscheidungen per PLZ fallen darunter.

### High Risk Anforderungen — und wie wir sie erfüllen

| EU AI Act Anforderung | Umsetzung im Projekt |
|---|---|
| Technische Dokumentation | `model_metadata.json` + MLflow Run-History |
| Logging & Audit-Trail | Azure Activity Log + Git-History |
| Menschliche Aufsicht | `quality_gate.py` — kein Deploy ohne R² > 0.80 |
| Erklärbarkeit | Feature Importance via MLflow, SHAP als nächster Schritt |
| Daten-Governance | `test_data_for_rai.csv` mit `high_risk` Flag (risk_score > 66) |
| Monitoring | Azure ML Monitor Job (Tag 4) |

### 3 Fragen für den IT-Abteilungsleiter

1. **"Welche KI-Systeme treffen heute automatisiert Entscheidungen die direkt Kunden betreffen — ohne menschliche Endprüfung?"**
   → Die Antwort überrascht oft. Shadow AI ist das größte Governance-Risiko.

2. **"Haben wir eine vollständige Liste aller eingesetzten KI-Systeme, inklusive Tools die Fachbereiche selbst eingekauft haben?"**
   → Wenn nein: EU AI Act-Inventarisierung ist Pflicht vor dem 2. August 2026 (Geltungsbeginn für High-Risk-Systeme).

3. **"Wer ist bei uns aktuell verantwortlich wenn ein KI-System eine falsche Entscheidung trifft?"**
   → Wenn niemand die Frage beantworten kann, fehlt Governance grundlegend.
