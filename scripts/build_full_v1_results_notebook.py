#!/usr/bin/env python3
"""Build the executable, read-only full-v1 results notebook."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "notebooks/final_dataset_results.ipynb"


def _source(text: str) -> list[str]:
    lines = text.strip("\n").splitlines()
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines else [])


def markdown(text: str) -> dict[str, object]:
    source = _source(text)
    return {
        "cell_type": "markdown",
        "id": hashlib.sha256(("markdown\0" + "".join(source)).encode()).hexdigest()[:16],
        "metadata": {},
        "source": source,
    }


def code(text: str, *, tags: list[str] | None = None) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if tags:
        metadata["tags"] = tags
    source = _source(text)
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": hashlib.sha256(("code\0" + "".join(source)).encode()).hexdigest()[:16],
        "metadata": metadata,
        "outputs": [],
        "source": source,
    }


def build_notebook() -> dict[str, object]:
    cells = [
        markdown(
            """
# Grammar-KT full-v1: frozen dataset and final evidence

This executable notebook reads the immutable public dataset and aggregate
experiment artifacts. It makes no model calls, does not mutate the dataset,
and never opens the learner-oracle trajectory. GrammarCells, generator K*, and
downstream K-hat hypotheses remain separate throughout.
"""
        ),
        code(
            """
import os

DATA_FOLDER = os.environ.get("GRAMMAR_KT_DATA_FOLDER", "data/grammar_kt_full_v1")
DATA_FOLDER
""",
            tags=["parameters"],
        ),
        code(
            """
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import json

import pandas as pd
from IPython.display import display

ROOT = Path.cwd().resolve()
if not (ROOT / "pyproject.toml").is_file():
    ROOT = ROOT.parent
DATASET = (ROOT / DATA_FOLDER).resolve()
assert DATASET.name == "grammar_kt_full_v1" and (DATASET / "manifest.json").is_file()

def load_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))

def read_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]

def show_table(rows, columns=None):
    frame = pd.DataFrame(rows)
    if columns:
        frame = frame.loc[:, columns]
    display(frame.reset_index(drop=True))
    return frame

SETUP = {"repo_root": str(ROOT), "dataset": str(DATASET), "read_only": True}
SETUP
"""
        ),
        markdown("## 1. Frozen release"),
        code(
            """
manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
release_rows = [
    {"object": key, "count": value}
    for key, value in manifest["scale"].items()
]
show_table(release_rows)
"""
        ),
        code(
            """
simulation = manifest["simulation"]["stream_summary"]
show_table([
    {"phase": phase, "events": count, "correct": simulation["correct_counts_by_phase"].get(phase)}
    for phase, count in simulation["phase_counts"].items()
])
"""
        ),
        markdown("## 2. Linguistic census and regimes"),
        code(
            """
normalisation = json.loads((DATASET / "provenance/normalisation/full_audit.json").read_text(encoding="utf-8"))
counts = normalisation["final"]["results"]["counts"]
show_table([{"outcome": key, "count": value, "share": value / 1222} for key, value in counts.items()])
"""
        ),
        code(
            """
cells = read_jsonl(DATASET / "grammar/cells.jsonl")
regimes = read_jsonl(DATASET / "grammar/regime_assignments.jsonl")
regime_counts = Counter(row["grammar_regime"] for row in regimes)
show_table([{"grammar_regime": key, "cells": value} for key, value in sorted(regime_counts.items())])
"""
        ),
        markdown("## 3. Generator K* and measurement bank"),
        code(
            """
kcs = read_jsonl(DATASET / "kcs.jsonl")
kc_rows = [{"kc_id": row["id"], "name": row["name"], "language_specific": row["language_specific"]} for row in kcs]
show_table(kc_rows)
"""
        ),
        code(
            """
items = read_jsonl(DATASET / "items/items.jsonl")
item_campaigns = Counter(
    row["generation_metadata"].get("campaign", "baseline_n3")
    for row in items
)
show_table([{"campaign": key, "selected_items": value} for key, value in sorted(item_campaigns.items())])
"""
        ),
        code(
            """
measurement = json.loads((DATASET / "provenance/measurement/audit.json").read_text(encoding="utf-8"))
show_table([{"diagnostic": key, "value": value} for key, value in measurement["counts"].items()])
"""
        ),
        markdown("## 4. RQ2 — controlled KC/Q misspecification"),
        code(
            """
rq2 = load_json("reports/full_v1_artifacts/rq2_misspecification_v1/results.json")
rq2_order = ["all_merged", "coarse_linguistic_families", "true_kstar", "structural_split2", "structural_split4", "exact_cell"]
rq2_rows = []
reference_loss = rq2["metrics_by_representation"]["true_kstar"]["probe_metrics"]["all_probe"]["log_loss"]
for representation in rq2_order:
    record = rq2["metrics_by_representation"][representation]
    metric = record["probe_metrics"]["all_probe"]
    rq2_rows.append({
        "representation": representation,
        "KCs": record["model_audit"]["hypothesis_kcs"],
        "log_loss": metric["log_loss"],
        "delta_vs_K*": metric["log_loss"] - reference_loss,
        "brier": metric["brier_score"],
    })
show_table(rq2_rows)
"""
        ),
        markdown("## 5. RQ3 — observable-only discovery"),
        code(
            """
rq3 = load_json("experiments/full_v1/rq3_kc_discovery_v1/final_evaluation.json")
rq3_ids = ["compositional_operations", "atomic_features", "coarse_operations", "fine_exact_cells", "hash_distractor_negative_control"]
rq3_rows = []
for policy in rq3_ids:
    recovery = rq3["structural_recovery"][policy]["all"]
    prediction = rq3["predictive_probe_evaluation"][policy]["all_probes"]
    rq3_rows.append({
        "policy": policy,
        "exact_true_KCs": recovery["characterisation"]["exact_true_kcs_recovered"],
        "activation_Jaccard": recovery["optimal_matching"]["mean_activation_jaccard_padded"],
        "aligned_Q_F1": recovery["aligned_q_edges"]["f1"],
        "probe_log_loss": prediction["log_loss"],
    })
show_table(rq3_rows)
"""
        ),
        markdown("## 6. RQ4 — linguistic generalisation"),
        code(
            """
rq4 = load_json("experiments/full_v1/rq4_generalisation_v1/results.json")
rq4_rows = []
for representation, record in rq4["baseline_generalisation"].items():
    for regime in ("seen", "unseen_combination", "unseen_value"):
        metric = record["by_grammar_regime"][regime]["event_weighted"]
        rq4_rows.append({"representation": representation, "regime": regime, "log_loss": metric["log_loss"], "brier": metric["brier_score"]})
show_table(rq4_rows)
"""
        ),
        markdown("## 7. Oracle-only state evaluation"),
        code(
            """
mastery = load_json("reports/full_v1_artifacts/mastery_recovery_v1/results.json")
mastery_rows = []
for representation, record in mastery["metrics_by_representation"].items():
    metric = record["metrics_by_regime"]["all_probe"]
    mastery_rows.append({
        "representation": representation,
        "RMSE": metric["rmse"],
        "MAE": metric["mae"],
        "correlation": metric["pearson_correlation"],
        "bias": metric["calibration"]["mean_estimate_minus_oracle"],
    })
show_table(mastery_rows)
"""
        ),
        markdown("## 8. Compact simulator robustness"),
        code(
            """
robustness = load_json("experiments/full_v1/simulator_robustness_v1/results.json")
robust_rows = []
for row in robustness["summary"]["candidate_minus_kstar_by_condition_across_seeds"]:
    if row["analysis_role"] != "primary":
        continue
    delta = row["delta_log_loss"]
    robust_rows.append({
        "condition": row["condition_id"],
        "candidate": row["candidate_representation"],
        "mean_delta_LL": delta["mean"],
        "minimum": delta["minimum"],
        "maximum": delta["maximum"],
    })
show_table(robust_rows)
"""
        ),
        markdown("## 9. Collection-design controls"),
        code(
            """
collection_path = ROOT / "experiments/full_v1/collection_design_v1/results.json"
assert collection_path.is_file(), "Frozen collection-design result is required"
collection = json.loads(collection_path.read_text(encoding="utf-8"))
boundary = collection["boundary_audit"]
assert boundary["baseline_immutable"] is True
assert boundary["probe_outcomes_used_for_selection"] is False
assert boundary["oracle_state_exposed_to_predictor"] is False
show_table([
    {"learners": int(learners), **record}
    for learners, record in collection["A_learner_count_stability"]["selection_frequency"].items()
])
"""
        ),
        code(
            """
opportunity_rows = []
for target, representations in collection["B_opportunities_per_learner"]["summary"].items():
    for representation, regimes_at_target in representations.items():
        opportunity_rows.append({
            "target_opportunities": int(target),
            "representation": representation,
            "all_probe_log_loss": regimes_at_target["all_probe"]["mean_log_loss"],
            "combination_log_loss": regimes_at_target["unseen_combination"]["mean_log_loss"],
        })
show_table(opportunity_rows)
"""
        ),
        code(
            """
item_support = collection["C_items_per_kc"]
show_table([
    {
        "bank": bank,
        "items": record["items"],
        "unique_Q_rows": record["unique_q_rows"],
        "Q_rank": record["rank"],
        "minimum_items_per_KC": record["item_support_per_kc"]["minimum"],
        "median_items_per_KC": record["item_support_per_kc"]["median"],
    }
    for bank, record in item_support.items()
    if bank.startswith("max_")
])
"""
        ),
        code(
            """
anchor_rows = []
for world, designs in collection["D_anchor_identifiability"]["summary"].items():
    for design, learner_results in designs.items():
        for learners, comparisons in learner_results.items():
            for comparison, metric in comparisons.items():
                anchor_rows.append({
                    "world": world,
                    "design": design,
                    "learners": int(learners),
                    "comparison": comparison,
                    "mean_delta_log_loss_vs_true": metric["mean_delta_log_loss_vs_true"],
                    "seed_minimum": metric["seed_range"][0],
                    "seed_maximum": metric["seed_range"][1],
                })
show_table(anchor_rows)
"""
        ),
        markdown("## 10. Integrity and RQ ledger"),
        code(
            """
hash_rows = []
for relative in ["manifest.json", "q_matrix.csv", "interactions.jsonl.gz"]:
    path = DATASET / relative
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = manifest["artifact_inventory"].get(relative, {}).get("sha256")
    hash_rows.append({
        "artifact": relative,
        "sha256": observed,
        "bytes": path.stat().st_size,
        "matches_manifest": observed == expected if expected else "self-manifest",
    })
show_table(hash_rows)
"""
        ),
        code(
            """
FINAL_DATASET_SUMMARY = {
    "scientific_distinction": "GrammarCell != generator K* != discovered K_hat",
    "dataset_status": manifest["status"],
    "cells": manifest["scale"]["canonical_grammar_cells"],
    "generator_kcs": manifest["scale"]["generator_kcs"],
    "items": manifest["scale"]["items"],
    "events": manifest["scale"]["interactions"],
    "RQ1": "supported within declared scope",
    "RQ2": "supported for frozen perturbations; item-difficulty caveat",
    "RQ3": "unique recovery rejected; equivalence-class recovery supported",
    "RQ4": "recombination supported; unseen-value ontology choice inconclusive",
    "oracle_trajectory_opened": False,
}
FINAL_DATASET_SUMMARY
"""
        ),
        markdown(
            """
## Interpretation boundary

The notebook demonstrates retained artifacts; it does not regenerate LLM
annotations, fit policies on holdout outcomes, or expose oracle trajectories.
K*, simulator parameters, and sample-size results are controlled synthetic
truths—not estimates of human cognition. Automatic item judgments are not human
pedagogical validation, and the alternate-schema contract is not cross-lingual
empirical evidence.
"""
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_notebook(), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
