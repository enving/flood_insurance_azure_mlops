# Tag 5 — FinOps: Kostentransparenz, Showback & Chargeback

> Ziel: Cloud-Kosten in Azure transparent machen, zuordnen und berichten. Showback vs. Chargeback als Konzepte und Implementierung kennen.

---

## Die 3 Konzepte

| Konzept | Was es ist | Wann |
|---|---|---|
| **Cost Transparency** | Ich sehe was ich ausgebe — ohne Zuordnung | Monat 1–6, Plattform neu |
| **Showback** | Ich sehe wer was verursacht hat — niemand zahlt intern | Ab Monat 6, erste Use Cases live |
| **Chargeback** | Echte interne Verrechnung aus Abteilungs-Budget | Ab Jahr 2, mehrere Abteilungen mit festen Budgets |

**Faustregel:** Chargeback setzt Kostenstellen, interne Buchungsprozesse und Buy-in vom Controlling voraus. Für neue KI-Plattformen immer mit Showback starten — es sensibilisiert ohne organisatorischen Aufwand.

---

## Azure Cost Management — Praktisch

### Tag-Schema (Fundament für Showback)

Ohne Tags kein Showback. Jede Ressource beim Erstellen taggen:

```bash
az ml compute create \
  --name flood-compute \
  --tags \
    Abteilung="Underwriting" \
    UseCase="Hochwasser-Scoring" \
    Umgebung="Produktion" \
    Verantwortlicher="tristan.wilms" \
    KostenTyp="Compute"
```

**Vollständiges Tag-Schema für 5 KI-Use-Cases:**

| Tag | Beispielwerte | Zweck |
|---|---|---|
| `Abteilung` | Underwriting, Schaden, Vertrieb | Showback pro Fachbereich |
| `UseCase` | Hochwasser-Scoring, Fraud-Detection | Kosten pro Modell |
| `Umgebung` | Dev, Staging, Produktion | Dev-Kosten rausrechnen |
| `Verantwortlicher` | tristan.wilms | Ansprechpartner bei Kostenfragen |
| `KostenTyp` | Compute, Storage, Endpoint | Kostenart-Analyse |

### Tags per Azure Policy erzwingen

```bash
# Ressource ohne 'Abteilung'-Tag kann nicht erstellt werden
az policy assignment create \
  --name "enforce-abteilung-tag" \
  --policy "96670d01-0a4d-4649-9c89-2d3bae9c9e52" \
  --params '{"tagName":{"value":"Abteilung"}}'
```

### Budget Alert (80% + 100%)

```bash
az consumption budget create \
  --budget-name "KI-Plattform-Monatsbudget" \
  --amount 500 \
  --time-grain Monthly \
  --start-date 2026-06-01 \
  --end-date 2027-06-01 \
  --resource-group rg-flood-insurance-mvp \
  --notifications \
    "{'Warnung-80':{'enabled':true,'operator':'GreaterThan','threshold':80,'contactEmails':['tristanwilms111@gmail.com']},'Warnung-100':{'enabled':true,'operator':'GreaterThan','threshold':100,'contactEmails':['tristanwilms111@gmail.com']}}"
```

### Kostendaten exportieren (Basis für Showback-Report)

```bash
# Täglicher Export als CSV in Blob Storage → Excel / Power BI
az costmanagement export create \
  --name "monatlicher-ki-kostenexport" \
  --scope "subscriptions/<SUBSCRIPTION_ID>" \
  --storage-account-id "/subscriptions/<SUB>/resourceGroups/rg-flood-insurance-mvp/providers/Microsoft.Storage/storageAccounts/floodinsstorage340058cf8" \
  --storage-container "cost-exports" \
  --recurrence Monthly \
  --recurrence-period from="2026-06-01" to="2027-06-01" \
  --dataset-type ActualCost
```

---

## Showback-Report Design

### Was die IT-Leitung sieht (1 Seite)
1. Gesamtkosten KI-Plattform diese Woche / Monat / Trend
2. Top 3 Kostentreiber (welche Use Cases, welche Ressourcentypen)
3. Budget-Auslastung in % mit Ampel (Grün / Gelb / Rot)
4. Geplante vs. tatsächliche Kosten

### Was eine Abteilung sieht (nur ihre Zahlen)
1. Kosten ihrer KI-Use-Cases diese Woche
2. Aufschlüsselung: Training vs. Endpoint vs. Storage
3. Vergleich zum Vormonat
4. "Was hätte das bei Azure ML on-demand gekostet?" (Rechtfertigung des Plattform-Investments)

---

## 3 FinOps-Maßnahmen von Tag 1 an

### 1. Tags von Anfang an erzwingen — nicht nachrüsten
Nachträgliches Taggen kostet Wochen. Azure Policy von Anfang an aktivieren.

### 2. Compute Cluster immer mit `min_instances: 0`
Der häufigste Anfängerfehler: Cluster läuft permanent.
```yaml
# In job.yaml / compute create
min_instances: 0      # skaliert auf Null wenn nichts rechnet
idle_time_before_scale_down: 120  # 2 Minuten Leerlauf → shutdown
```
`flood-compute` ist bereits so konfiguriert ✅

### 3. Budget Alert vor dem ersten produktiven Job
Ein Hyperparameter-Sweep ohne Early Termination kann 200€ in einer Nacht kosten. Budget Alert bei 80% schützt davor.

---

## Die häufigste FinOps-Falle

Alle Ressourcen landen in einer Resource Group, ohne Tags, ohne Budget. Nach 3 Monaten weiß niemand mehr warum 3.200€ im letzten Monat weggegangen sind. Das Projekt wird politisch — nicht wegen dem Ergebnis, sondern wegen unkontrollierten Kosten.

**Lösung:** Cost Transparency ist eine technische Maßnahme (Tags + Policy), keine organisatorische. Sie kostet 2 Stunden Einrichtung und spart Wochen an Diskussionen.
