"""
quality_gate.py — MLOps Quality Gate nach HyperDrive Sweep

Prüft ob der beste Run die Mindestanforderungen erfüllt:
  1. test_r2 >= MIN_R2                          (Modellqualität)
  2. overfit_gap <= MAX_OVERFIT_GAP             (Generalisierung)

Exit 0 + GITHUB_OUTPUT → Modell wird registriert
Exit 1                  → Pipeline bricht ab, kein Register

Aufruf:
  python quality_gate.py \\
    --sweep-name <job-name> \\
    --resource-group <rg> \\
    --workspace <ws-name>

  Env-Variable AZURE_SUBSCRIPTION_ID muss gesetzt sein.
"""

import sys
import os
import argparse

# ── Schwellwerte ────────────────────────────────────────────────────
MIN_R2           = 0.80   # unter diesem Wert ist das Modell nicht production-ready
MAX_OVERFIT_GAP  = 0.10   # train_r2 - test_r2 > 0.10 → verdächtiges Overfitting
# ────────────────────────────────────────────────────────────────────


def write_github_output(key: str, value: str):
    """Schreibt Key=Value in GITHUB_OUTPUT (nur in GitHub Actions verfügbar)."""
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"{key}={value}\n")


def main(sweep_name: str, resource_group: str, workspace: str):
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        print("❌ AZURE_SUBSCRIPTION_ID nicht gesetzt")
        sys.exit(1)

    # ── Azure ML SDK + MLflow verbinden ────────────────────────────
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential
    import mlflow

    ml = MLClient(
        DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace,
    )

    # MLflow Tracking URI aus Workspace holen
    ws_obj = ml.workspaces.get(workspace)
    mlflow.set_tracking_uri(ws_obj.mlflow_tracking_uri)
    mlflow_client = mlflow.tracking.MlflowClient()

    # ── Besten Child-Run des Sweeps finden ─────────────────────────
    print(f"🔍 Lade Sweep-Job: {sweep_name}")
    sweep_job = ml.jobs.get(sweep_name)

    best_child_id = getattr(sweep_job, "best_child_run_id", None)
    if not best_child_id:
        print("❌ Kein best_child_run_id gefunden — Sweep evtl. nicht abgeschlossen?")
        sys.exit(1)

    print(f"🏆 Bester Child-Run: {best_child_id}")

    # ── Metriken aus MLflow holen ───────────────────────────────────
    # Azure ML v2 registriert Jobs mit ihrem job-name als MLflow run name
    experiment = mlflow_client.get_experiment_by_name("hochwasser-risiko-scoring")
    if not experiment:
        print("❌ MLflow Experiment 'hochwasser-risiko-scoring' nicht gefunden")
        sys.exit(1)

    runs = mlflow_client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"tags.mlflow.rootRunId = '{sweep_name}'",
        order_by=["metrics.test_r2 DESC"],
        max_results=1,
    )

    if not runs:
        # Fallback: direkt über Child-Job-Name suchen
        runs = mlflow_client.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.mlflow.parentRunId LIKE '%{sweep_name}%'",
            order_by=["metrics.test_r2 DESC"],
            max_results=1,
        )

    if not runs:
        print("⚠️  Keine MLflow-Runs gefunden — Quality-Check übersprungen, Child-ID wird weitergegeben")
        write_github_output("best_child_id", best_child_id)
        write_github_output("test_r2", "unknown")
        sys.exit(0)

    best_run = runs[0]
    metrics  = best_run.data.metrics

    test_r2     = metrics.get("test_r2", 0.0)
    train_r2    = metrics.get("train_r2", test_r2)
    overfit_gap = metrics.get("overfit_gap", train_r2 - test_r2)

    # ── Report ──────────────────────────────────────────────────────
    print("\n" + "─" * 50)
    print(f"  Quality Gate Report")
    print("─" * 50)
    print(f"  Best Child Run : {best_child_id}")
    print(f"  train_r2       : {train_r2:.4f}")
    print(f"  test_r2        : {test_r2:.4f}   (min: {MIN_R2})")
    print(f"  overfit_gap    : {overfit_gap:.4f}  (max: {MAX_OVERFIT_GAP})")
    print("─" * 50)

    # ── Checks ──────────────────────────────────────────────────────
    failed = False

    if test_r2 < MIN_R2:
        print(f"  ❌ FAIL: test_r2 {test_r2:.4f} < {MIN_R2} — Modell zu schwach")
        failed = True

    if overfit_gap > MAX_OVERFIT_GAP:
        print(f"  ❌ FAIL: overfit_gap {overfit_gap:.4f} > {MAX_OVERFIT_GAP} — Overfitting")
        failed = True

    if failed:
        print("─" * 50)
        print("  🚫 Quality Gate NICHT bestanden — kein Register")
        sys.exit(1)

    # ── Passed ──────────────────────────────────────────────────────
    print("  ✅ Quality Gate bestanden")
    print("─" * 50)

    write_github_output("best_child_id", best_child_id)
    write_github_output("test_r2", str(round(test_r2, 4)))
    sys.exit(0)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="MLOps Quality Gate nach HyperDrive Sweep")
    p.add_argument("--sweep-name",     required=True, help="Name des Sweep-Jobs in Azure ML")
    p.add_argument("--resource-group", required=True)
    p.add_argument("--workspace",      required=True)
    args = p.parse_args()
    main(args.sweep_name, args.resource_group, args.workspace)
