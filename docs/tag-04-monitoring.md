# Tag 4 — Monitoring & Observability für KI-Systeme

> Ziel: Verstehen was "Model Monitoring" in Azure konkret bedeutet — Drift-Konzepte, Latenz-Tracking, Alerting.

---

## Die 4 Drift-Konzepte (konkret für Versicherungen)

### Data Drift
Die Eingangsdaten verändern sich gegenüber den Trainingsdaten.

**Beispiel Hochwasser-Modell:**
Das Modell wurde mit PLZs trainiert, wo `Geographische_Hoehe_m` zwischen 0–1500m liegt. Nach einem Jahr kommen plötzlich viele Anfragen aus Küstenregionen mit negativen Höhenwerten. Das Modell hat diese Verteilung nie gesehen → Prämien werden falsch berechnet, ohne dass irgendjemand es merkt.

### Concept Drift
Die Realität ändert sich, aber die Feature-Werte sehen noch gleich aus.

**Beispiel:** Vor dem Elbe-Hochwasser 2025 war `Naehe_zu_Fluss=1` in einer PLZ ein mittleres Risiko. Danach ist dieselbe PLZ ein Hochrisiko-Gebiet — aber die Feature-Werte haben sich nicht geändert. Das Modell liegt systematisch falsch, weil sich die Welt verändert hat.

### Prediction Drift
Die Ausgabe-Verteilung des Modells verschiebt sich — ohne neue Daten.

**Beispiel:** Das Modell gibt plötzlich im Durchschnitt 20% höhere `risk_scores` aus als vor 3 Monaten. Irgendwas in der Datenpipeline oder im Feature Engineering hat sich verändert. Erkennbar ohne Ground Truth daran, dass sich die Output-Verteilung verschiebt.

### Latency Drift (ML-spezifisch)
Bei ML-Endpoints kommt zur normalen Response Time noch hinzu: Feature Engineering vor dem Modell, Modell-Inferenz selbst, Post-Processing. Wenn das Modell plötzlich 5× langsamer wird, liegt es oft nicht am Modell sondern an einem Feature das live aus einer Datenbank gezogen wird.

---

## Azure ML Model Monitoring

### Minimale Monitor YAML

```yaml
# src/monitor.yaml
$schema: https://azuremlschemas.azureedge.net/latest/monitorSchedule.schema.json
name: hochwasser-drift-monitor
trigger:
  type: recurrence
  frequency: day
  interval: 1

create_monitor:
  compute:
    instance_type: standard_e4s_v3

  monitoring_target:
    ml_task: regression
    endpoint_deployment_id: azureml:hochwasser-endpoint/hochwasser-deployment

  monitoring_signals:
    data_drift:
      type: data_drift
      reference_data:
        input_data:
          path: azureml:flood-baseline-data:1
          type: mltable
        data_context: training
      production_data:
        input_data:
          path: azureml:flood-production-data:latest
          type: mltable
        data_context: production
      features:
        top_n_feature_importance: 6
      metric_thresholds:
        - applicable_feature_type: numerical
          jensen_shannon_distance: 0.1   # > 0.1 → Alert

  alert_notification:
    emails:
      - tristanwilms111@gmail.com
```

Erstellen:
```bash
az ml schedule create \
  --file src/monitor.yaml \
  --resource-group rg-flood-insurance-mvp \
  --workspace-name flood-insurance-workspace
```

### Jensen-Shannon-Distanz verstehen
- 0.0 = Trainings- und Produktionsverteilung identisch
- 0.1 = merkliche Abweichung → Alert empfohlen
- 0.3+ = starke Abweichung → Retraining dringend nötig
- 1.0 = komplett verschiedene Verteilungen

---

## Application Insights für den Endpoint

### Automatisch erfasst (ohne Code)
- Request Rate, Response Time, Failure Rate
- HTTP 4xx / 5xx Fehler

### Custom Metrics im Scoring Script

```python
# src/score.py
import json, os, logging
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=os.environ["APPINSIGHTS_CONNECTION_STRING"]
))

def run(raw_data):
    data = json.loads(raw_data)
    risk_score = model.predict([data["features"]])[0]

    logger.warning("score", extra={
        "custom_dimensions": {
            "risk_score": float(risk_score),
            "plz":        data.get("plz"),
            "region":     data.get("region"),
        }
    })
    return {"risk_score": round(float(risk_score), 2)}
```

### KQL — Wöchentlicher Performance Report

```kql
requests
| where timestamp > ago(7d)
| where cloud_RoleName == "hochwasser-endpoint"
| summarize
    avg_duration_ms = avg(duration),
    error_rate_pct  = countif(success == false) * 100.0 / count(),
    total_requests  = count()
  by bin(timestamp, 1d)
| order by timestamp desc
```

---

## Monitoring-Konzept für 5 KI-Systeme

### 5 Standard-KPIs pro Modell

| KPI | Was es misst | Alert-Schwelle |
|---|---|---|
| Jensen-Shannon Drift | Abweichung neue Daten vs. Trainingsdaten | > 0.1 |
| Prediction Drift | Verschiebung Output-Verteilung | > 15% Abweichung Baseline-Median |
| Request Latency P95 | 95% der Requests unter diesem Wert | > 500ms |
| Error Rate | % fehlgeschlagene Anfragen | > 1% |
| Model R² auf Sample | Stichproben Ground-Truth Vergleich | < 0.75 |

### Wöchentlicher Report an IT-Leitung
1. Traffic-Übersicht: Wie viele Anfragen, Trend
2. Drift-Status: Grün/Gelb/Rot pro Modell
3. Letzte Retraining-Dates + Modell-Versionen
4. Offene Alerts der Woche + Maßnahmen
5. Kosten der Woche (Compute + Endpoint)

### Häufigste Monitoring-Fehler (erste 6 Monate)
1. **Keine Baseline definiert** — man merkt Drift nicht, weil man nicht weiß wie "normal" aussieht
2. **Alert ohne Prozess** — Drift-Alert geht raus, aber niemand ist zuständig → von Anfang an: Alert → Ticket → Person definieren
3. **Nur technisches Monitoring** — Response Time grün, aber Modell liefert inhaltlich falsche Ergebnisse. Ground-Truth-Sampling (auch manuell) ist Pflicht
