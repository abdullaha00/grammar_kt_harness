#!/usr/bin/env python3
"""Build the offline, read-only measurement-realism results notebook."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "notebooks/measurement_realism_results.ipynb"

# Every notebook input is a retained summary/analysis artifact. In particular,
# the notebook never reads response streams, oracle streams, model predictions,
# model-call archives, or the immutable full-v1 dataset itself.
SOURCE_PATHS = {
    "strict_audit": "experiments/measurement_realism/audits/item_audit/summary.json",
    "cross_audit": "experiments/measurement_realism/audits/platform_audit_synthesis.json",
    "kc_induction": "experiments/measurement_realism/kc_induction_v1/results.json",
    "matched_bank": (
        "experiments/measurement_realism/design/bank_protocol/runs/"
        "matched_bank_v0_2_20260830/analysis/failure_analysis.json"
    ),
    "controlled_worlds": (
        "experiments/measurement_realism/worlds/controlled_instrument_v1/"
        "synthesis/results.json"
    ),
    "policy_recovery": (
        "experiments/measurement_realism/worlds/controlled_instrument_v1/"
        "policy_recovery_v1/results/results.json"
    ),
    "dialogue_continuum": (
        "experiments/measurement_realism/dialogue_pilot_live_v1/analysis.json"
    ),
}

EXPECTED_SOURCE_SHA256 = {
    "strict_audit": "8bf914158588dd6952730496e609ecb966e5278311de5476649cef6ff41ea419",
    "cross_audit": "ba2bbd8b454db0e54059b940cc77309a3921786ec19ae43c4f50507366189094",
    "kc_induction": "d535a727b5c3cf87038bfef4c183824469a17614113733658a1dbae0d20bd376",
    "matched_bank": "1761db11853163421cd83cb9b4410f00ec887a2e0f574e1578c474eba203b7c3",
    "controlled_worlds": "55ac72dfdaf739597451e5766edb399690b780bbfa9499474c9142cf919e844a",
    "policy_recovery": "29702c895ae9ba34cd0e1313514b23694572d3ca60b9629923b4713c5340a5c6",
    "dialogue_continuum": "5d2538e7866855782f92fe0c946bfcfb714463ae60f8879f01135f2459e797ef",
}


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
    source_literal = json.dumps(SOURCE_PATHS, indent=4, sort_keys=True)
    hash_literal = json.dumps(EXPECTED_SOURCE_SHA256, indent=4, sort_keys=True)
    cells = [
        markdown(
            """
# Measurement realism: retained results

> **CONTROLLED SCENARIO — NOT A DATASET RELEASE.** The matched learner-facing
> bank failed its preregistered freeze gate, so the A–D, structured-error, and
> schedule worlds use a deterministic **content-free controlled instrument**.
> They establish structural sensitivity only; they do not establish learner-facing
> measurement validity or platform plausibility.
>
> **NO HUMAN VALIDATION.** Item, KC, bank, and dialogue judgments shown here are
> automated stress tests—not judgments from learners, teachers, measurement
> experts, or platform practitioners. No new dataset is released by this notebook,
> and the frozen `grammar_kt_full_v1` reference is neither opened nor modified.

This executable notebook is an offline, read-only view over seven compact retained
JSON analyses. It never reads learner-response archives, oracle trajectories,
prediction rows, or raw model-call archives, and it makes no network/model calls.
"""
        ),
        code(
            """
EVIDENCE_ROOT = "experiments/measurement_realism"
EVIDENCE_ROOT
""",
            tags=["parameters"],
        ),
        code(
            f"""
from pathlib import Path
import hashlib
import json

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

ROOT_CANDIDATES = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
ROOT = next(path for path in ROOT_CANDIDATES if (path / "pyproject.toml").is_file())
pd.set_option("display.max_colwidth", 140)
plt.style.use("seaborn-v0_8-whitegrid")

SOURCE_PATHS = {source_literal}
EXPECTED_SOURCE_SHA256 = {hash_literal}

def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(name):
    path = ROOT / SOURCE_PATHS[name]
    observed = sha256_file(path)
    assert observed == EXPECTED_SOURCE_SHA256[name], (name, observed)
    return json.loads(path.read_text(encoding="utf-8"))

ARTIFACTS = {{name: load_json(name) for name in SOURCE_PATHS}}
strict = ARTIFACTS["strict_audit"]
cross = ARTIFACTS["cross_audit"]
kc = ARTIFACTS["kc_induction"]
bank = ARTIFACTS["matched_bank"]
worlds = ARTIFACTS["controlled_worlds"]
policy = ARTIFACTS["policy_recovery"]
dialogue = ARTIFACTS["dialogue_continuum"]

# Fail closed if any scientific boundary changes.
assert strict["scope"]["human_or_learner_evidence"] is False
assert cross["evidence_boundary"]["full_v1_mutated"] is False
assert cross["evidence_boundary"]["human_or_expert_gold"] is False
assert kc["evidence_boundary"]["human_or_expert_gold"] is False
assert bank["status"] == "FAILED_PREREGISTERED_BANK_FREEZE_GATE"
assert bank["release_gate_failure"]["freeze_permitted"] is False
assert worlds["controlled_scenario"] is True
assert worlds["content_free_instrument"] is True
assert worlds["release_eligible"] is False
assert worlds["claim_boundary"]["permitted"] == "controlled_structural_sensitivity_only"
assert worlds["claim_boundary"]["learner_facing_measurement_validity"] == "NOT_ASSESSED"
assert worlds["claim_boundary"]["platform_plausibility"] == "NOT_ASSESSED"
assert policy["controlled_scenario"] is True and policy["release_eligible"] is False
assert dialogue["evidence_boundary"]["scalar_realism_score_computed"] is False

integrity_rows = [
    {{"artifact": name, "bytes": (ROOT / path).stat().st_size, "sha256": EXPECTED_SOURCE_SHA256[name]}}
    for name, path in SOURCE_PATHS.items()
]
display(Markdown("**Offline integrity check: PASS — seven exact compact artifacts matched.**"))
display(pd.DataFrame(integrity_rows))
"""
        ),
        markdown(
            """
## 1. Platform-facing audit of the frozen 113-item bank

The strict census asks whether each stored task is comprehensible, answerable,
pedagogically and platform plausible, and diagnostically aligned. A second audit
used four role-specific automated critics. Percentages below describe these
automated judgments only; they are not estimates of human usability.
"""
        ),
        code(
            """
disposition_order = [
    "usable_as_stored",
    "minor_ui_or_context_change",
    "technically_valid_but_artificial",
    "answer_space_problem",
    "rewrite_or_withhold",
]
counts = strict["categorical_results"]["primary_disposition"]
audit_rows = [
    {
        "disposition": label,
        "items": counts[label],
        "share": counts[label] / strict["scope"]["items_reviewed"],
    }
    for label in disposition_order
]
audit_frame = pd.DataFrame(audit_rows)
display(audit_frame.style.format({"share": "{:.1%}"}))

ax = audit_frame.plot.barh(x="disposition", y="items", legend=False, color="#4472C4", figsize=(8, 3.2))
ax.set(xlabel="items (automated strict census)", ylabel="")
ax.invert_yaxis()
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """
action = cross["agreement"]["action_threshold"]
cross_rows = [
    {"cross-audit outcome": "usable in both audits", "items": action["both_usable"]["count"]},
    {"cross-audit outcome": "action in both audits", "items": action["both_require_action"]["count"]},
    {"cross-audit outcome": "action in strict audit only", "items": action["strict_only_requires_action"]["count"]},
    {"cross-audit outcome": "action in role-specific audit only", "items": action["live_only_requires_action"]["count"]},
]
display(pd.DataFrame(cross_rows))
print(
    f"Coverage: {cross['coverage']['common_items']} items; "
    f"{cross['coverage']['live_judgments']} role judgments across "
    f"{len(cross['coverage']['live_roles'])} roles. "
    f"Union requiring action: {sum(row['items'] for row in cross_rows[1:])}/113."
)
"""
        ),
        markdown(
            """
### Exact stored learner-facing examples

These are verbatim prompt/target pairs retained in the compact cross-audit
summary. They illustrate why linguistic validity and learner-facing measurement
validity must be recorded separately.
"""
        ),
        code(
            """
panels = ["shared_clear_pass", "shared_answer_space_failure", "shared_artificial_interface"]
examples_by_panel = {row["panel"]: row for row in cross["representative_items"]}
example_rows = []
for panel in panels:
    row = examples_by_panel[panel]
    example_rows.append({
        "panel": panel,
        "item_id": row["item_id"],
        "prompt (verbatim)": row["prompt"],
        "target (verbatim)": row["target_answer"],
        "strict disposition": row["strict"]["raw_disposition"],
        "strict learner note": row["strict"]["learner_note"],
    })
display(pd.DataFrame(example_rows))
"""
        ),
        markdown(
            """
**Audit interpretation.** Seventy of 113 items were usable as stored in the
strict audit, but 43 required at least some action there; the union across both
automated audits flagged 53. The examples show the distinction: a clean cloze,
an underdetermined answer space, and an answerable but annotation-like interface.
This triage motivated a matched-format construction attempt; it does not validate
deployability.
"""
        ),
        markdown(
            """
## 2. Outcome-blind KC induction stability

Three independent automated inductions received frozen GrammarCell inputs but no
learner outcomes. Hypotheses are canonicalized by their activation sets, so the
comparison concerns structural behavior rather than wording.
"""
        ),
        code(
            """
replicate_rows = []
for row in kc["replicates"]:
    replicate_rows.append({
        "replicate": row["replicate_id"],
        "raw hypotheses": row["raw_hypotheses"],
        "unique activations": row["unique_activation_hypotheses"],
        "Q rank": row["unique_q_rank"],
        "exact K* activation matches": row["exact_kstar_match_count"],
        "median support cells": row["support_cells"]["median"],
    })
display(pd.DataFrame(replicate_rows))

agreement_rows = [
    {
        "pair": f"{row['left']} vs {row['right']}",
        "shared activations": row["shared_activation_hypotheses"],
        "union activations": row["union_activation_hypotheses"],
        "activation Jaccard": row["jaccard"],
    }
    for row in kc["pairwise_activation_set_agreement"]
]
display(pd.DataFrame(agreement_rows).style.format({"activation Jaccard": "{:.3f}"}))

pd.DataFrame(agreement_rows).plot.bar(
    x="pair", y="activation Jaccard", legend=False, color="#ED7D31", ylim=(0, 1), figsize=(7, 3)
)
plt.ylabel("activation-set Jaccard")
plt.xlabel("")
plt.tight_layout()
plt.show()
print(
    f"Union={kc['activation_hypotheses_in_union']}; shared by all="
    f"{kc['activation_hypotheses_shared_by_all_replicates']}; "
    f"K* columns exactly recovered by any replicate="
    f"{kc['kstar_columns_recovered_by_any_exact_activation']}/18."
)
"""
        ),
        markdown(
            """
**KC interpretation.** Pairwise activation Jaccard is only 0.400–0.458, with
9 hypotheses shared across all runs out of a 30-signature union. Rank can be high
while ontology choice remains unstable. These runs therefore diagnose
underdetermination from GrammarCells alone; they neither select a replacement for
K* nor establish psychological truth.
"""
        ),
        markdown(
            """
## 3. Matched-format bank: funnel, geometry, and the failed release gate

The protocol required 38 semantic families × four formats = 152 validated slots,
with the 18 seen cells retaining rank 18. Whole-family acceptance was deliberately
strict: one weak format rejected the family.
"""
        ),
        code(
            """
round_rows = []
for row in bank["pass_funnel"]["by_candidate_round"]:
    round_rows.append({
        "round": row["candidate_round"],
        "evaluated": row["candidates_evaluated"],
        "deterministic pass": row["deterministic_gate_pass"],
        "solver pass": row["solver_family_gate_pass"],
        "critic/accepted": row["critic_family_gate_pass"],
    })
round_frame = pd.DataFrame(round_rows)
display(round_frame)
round_frame.set_index("round")[["deterministic pass", "solver pass", "critic/accepted"]].plot(
    marker="o", figsize=(7, 3)
)
plt.ylabel("families")
plt.xticks([1, 2, 3])
plt.tight_layout()
plt.show()

g = bank["accepted_family_geometry"]
geometry_rows = [
    {"gate": "families", "observed": g["accepted_family_count"], "required": g["required_families"]},
    {"gate": "format slots", "observed": g["accepted_item_slots"], "required": g["required_item_slots"]},
    {"gate": "selected cells covered", "observed": g["selected_cells_covered"], "required": g["selected_cells_required"]},
    {"gate": "generator KCs covered", "observed": g["active_kcs_covered"], "required": g["generator_kcs_required"]},
    {"gate": "seen Q rank", "observed": g["accepted_seen_q_rank"], "required": g["required_seen_q_rank"]},
]
display(pd.DataFrame(geometry_rows))
"""
        ),
        markdown(
            """
### Exact four-format family that passed

This verbatim retained example shows what the intended crossing looked like.
It is **construction evidence only**: five families passed in total, so this is
not a partial dataset release and does not satisfy the bank's coverage/rank gate.
"""
        ),
        code(
            """
family = bank["accepted_family_geometry"]["accepted_family_examples"][0]
print("Canonical target:", family["canonical_target_sentence"])
print("GrammarCell:", family["cell_id"], "| KCs:", ", ".join(family["generator_kc_ids"]))
family_rows = [
    {
        "format": item["format"],
        "context (verbatim)": item["context"],
        "instruction (verbatim)": item["instruction"],
        "target response (verbatim)": item["target_response"],
    }
    for item in family["learner_facing_items"]
]
display(pd.DataFrame(family_rows))
"""
        ),
        markdown(
            """
**Bank conclusion.** After three preregistered rounds, only 5/38 families
(20/152 item slots) passed, covering 4/20 selected cells and 6/18 KCs; seen-cell
rank was 3/18. The release gate correctly failed. All downstream simulation
results in this notebook therefore use neutral format labels and Q rows in a
content-free controlled scaffold—not rejected prompts and not a learner-facing
bank.
"""
        ),
        markdown(
            """
## 4. Controlled A–D nuisance worlds

The primary estimand is held-out-learner prediction on **seen terminal probes**
(82 learners × 144 slots per seed). Lower log loss/Brier/ECE and lower
item-prerequisite-state RMSE are better. K* is generator truth only inside this
declared simulator.
"""
        ),
        code(
            """
model_rows = []
for label, row in worlds["model_conditions"].items():
    model_rows.append({
        "model": label,
        "features": row["feature_count"],
        "KC representation": row["kc_representation"],
        "nuisance representation": row["nuisance"],
        "scientific role": row.get("role", "comparison model"),
    })
display(pd.DataFrame(model_rows))
"""
        ),
        code(
            """
world_order = [
    "clean_zero", "format_moderate", "format_strong_control",
    "item_moderate", "item_format_moderate", "combined_heterogeneous",
]
abcd_rows = []
for world_id in world_order:
    for model in "ABCD":
        metrics = worlds["abcd_seen_terminal_probe_summary"]["models"][world_id][model]["across_seed"]
        abcd_rows.append({
            "world": world_id,
            "model": model,
            "log loss": metrics["log_loss"]["mean"],
            "Brier": metrics["brier_score"]["mean"],
            "ECE": metrics["ece_10_fixed_width"]["mean"],
            "state RMSE": metrics["item_prerequisite_state_rmse"]["mean"],
        })
abcd_frame = pd.DataFrame(abcd_rows)
display(abcd_frame.style.format({"log loss": "{:.6f}", "Brier": "{:.6f}", "ECE": "{:.6f}", "state RMSE": "{:.6f}"}))

pivot = abcd_frame.pivot(index="world", columns="model", values="log loss").loc[world_order]
pivot.plot(marker="o", figsize=(10, 4))
plt.ylabel("seen-probe log loss (3-seed mean)")
plt.xlabel("")
plt.xticks(range(len(world_order)), world_order, rotation=25, ha="right")
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """
contrast_rows = []
for contrast, row in worlds["contrasts"]["primary_cross_world"].items():
    summary = row["across_seed_point_estimate"]
    exclusions = sum(
        interval["percentile_95"][1] < 0 or interval["percentile_95"][0] > 0
        for interval in row["per_seed"].values()
    )
    contrast_rows.append({
        "contrast": contrast,
        "mean delta log loss": summary["mean"],
        "seed range": f"[{summary['minimum']:.6f}, {summary['maximum']:.6f}]",
        "seed-conditional intervals excluding 0": f"{exclusions}/3",
        "correct sign interpretation": row["corrected_sign_gloss"],
    })
display(pd.DataFrame(contrast_rows).style.format({"mean delta log loss": "{:.6f}"}))
"""
        ),
        code(
            """
def interval_rows(label, payload):
    rows = []
    for seed, result in payload["per_seed"].items():
        lo, hi = result["percentile_95"]
        rows.append({
            "control": label,
            "seed": seed,
            "delta log loss": result["point_estimate"],
            "conditional 95% interval": f"[{lo:.6f}, {hi:.6f}]",
            "relation to zero": "below" if hi < 0 else "above" if lo > 0 else "contains",
        })
    return rows

sensitivity_rows = []
sensitivity_rows += interval_rows("item-only B−A", worlds["contrasts"]["item_only_false_split_B_minus_A"])
sensitivity_rows += interval_rows("heterogeneous C−B", worlds["contrasts"]["combined_heterogeneous"]["C_minus_B"])
sensitivity_rows += interval_rows("heterogeneous D−C", worlds["contrasts"]["combined_heterogeneous"]["D_minus_C"])
display(pd.DataFrame(sensitivity_rows).style.format({"delta log loss": "{:+.6f}"}))
"""
        ),
        markdown(
            """
**A–D interpretation.** The format difference-in-differences is −0.03155:
the correct sign gloss is that planted format nuisance increases false-split B's
relative predictive advantage over shared-K* A. It does **not** validate B as a
psychological ontology. Explicit format model C beats B in the strong control,
but that remedy is mixed under combined heterogeneity (all three intervals contain
zero). D beats C under planted item effects, but D is an **oracle-aligned,
same-seen-item positive control**: the planted effect lies in its 123-dimensional
seen-item residual basis and held-out items are zero encoded. This is not evidence
that an arbitrary real-data item model will deconfound unseen items.

All intervals are 2,000-repeat learner-cluster percentile bootstraps over fixed
held-out predictions. They cover test-learner variation conditional on the frozen
fit; they exclude train/dev sampling, refitting/tuning, item-bank sampling,
simulator/world uncertainty, and seed uncertainty. Three-seed means/ranges are
descriptive, not confidence intervals.
"""
        ),
        markdown(
            """
## 5. Structured synthetic error histories

The same binary outcomes are augmented with linked, 80%-linked, or within-item
shuffled categories. The target is a **post-outcome deficit-proportional
attribution**, not a causal human error diagnosis. Prediction uses only prior
categories; current-response labels are not leaked.
"""
        ),
        code(
            """
stream_order = [
    "binary_only", "linked_positive_control", "linked_80_percent",
    "within_item_shuffled_negative_control",
]
error_rows = []
for stream in stream_order:
    pred = worlds["error_history"]["prediction_and_item_prerequisite_state"][stream]["across_seed"]
    loc = worlds["error_history"]["failed_kc_localisation"][stream]
    terminal = worlds["error_history"]["secondary_terminal_kc_evidence_diagnostic"][stream]
    error_rows.append({
        "history": stream,
        "prediction log loss": pred["log_loss"]["mean"],
        "prediction Brier": pred["brier_score"]["mean"],
        "item-state RMSE": pred["item_prerequisite_state_rmse"]["mean"],
        "failed-KC compatible top-1": loc["across_seed"]["compatible_top1"]["mean"],
        "terminal KC evidence RMSE": terminal["across_seed"]["rmse"]["mean"],
    })
error_frame = pd.DataFrame(error_rows)
display(error_frame.style.format({column: "{:.6f}" for column in error_frame.columns if column != "history"}))
"""
        ),
        code(
            """
paired_rows = []
for comparison, payload in worlds["error_history"]["paired_prediction_log_loss"].items():
    for seed, result in payload["per_seed"].items():
        lo, hi = result["percentile_95"]
        paired_rows.append({
            "comparison": comparison,
            "seed": seed,
            "delta log loss": result["point_estimate"],
            "conditional 95% interval": f"[{lo:.6f}, {hi:.6f}]",
            "relation to zero": "below" if hi < 0 else "above" if lo > 0 else "contains",
        })
display(pd.DataFrame(paired_rows).style.format({"delta log loss": "{:+.6f}"}))
"""
        ),
        markdown(
            """
**Error interpretation.** Fully linked categories are a positive control and
localize the synthetic target perfectly by construction; 80%-linked categories
remain strongly diagnostic. Their next-response log-loss gains are small and not
uniform across seeds, so a predictive benefit is not consistently established.
Within-item shuffling is an event-link negative control—not an information-free
chance null—because it preserves item/category marginals. Its localization log
loss is also on a different task/scale from response prediction and must not be
compared numerically. The terminal-KC RMSE is a separate model-independent
Beta(1,1) evidence-count diagnostic, not an A–D fitted state and not human mastery.
"""
        ),
        markdown(
            """
## 6. Exploratory schedule-policy recovery

These post-response derived analyses apply the frozen A–D fitting protocol to
alternative controlled histories. They are explicitly exploratory
recovery/model-fit comparisons—not policy efficacy estimates.
"""
        ),
        code(
            """
policy_order = ["q_balanced_lab", "curriculum", "mixed_practice", "adaptive_weakness"]
policy_rows = []
for name in policy_order:
    result = policy["policy_results"][name]
    schedule = worlds["schedule_diagnostics"]["policies"][name]["across_seed"]
    policy_rows.append({
        "policy": name,
        "D seen log loss": result["condition_D_seen_log_loss"]["mean"],
        "D item-state RMSE": result["condition_D_seen_item_prerequisite_state_rmse"]["mean"],
        "binary terminal-KC evidence RMSE": result["binary_terminal_Kstar_evidence_rmse"]["mean"],
        "item exposure Gini": schedule["item_exposure_gini"]["mean"],
        "median item repetition gap": schedule["median_repetition_gap"]["mean"],
        "mean adjacent-Q Jaccard": schedule["mean_adjacent_q_jaccard_design_linked"]["mean"],
    })
policy_frame = pd.DataFrame(policy_rows)
display(policy_frame.style.format({column: "{:.6f}" for column in policy_frame.columns if column != "policy"}))

comparison_rows = []
for name, payload in policy["learner_paired_seen_log_loss_comparisons"].items():
    summary = payload["point_estimate_summary"]
    excluded = sum(
        result["percentile_95"][1] < 0 or result["percentile_95"][0] > 0
        for result in payload["per_seed"].values()
    )
    comparison_rows.append({
        "comparison": name,
        "mean policy−q-balanced log loss": summary["mean"],
        "seed range": f"[{summary['minimum']:.6f}, {summary['maximum']:.6f}]",
        "seed-conditional intervals excluding 0": f"{excluded}/3",
    })
display(pd.DataFrame(comparison_rows).style.format({"mean policy−q-balanced log loss": "{:+.6f}"}))
"""
        ),
        markdown(
            """
**Schedule interpretation.** Mixed practice is nearly null against q-balanced
(mean Δ log loss −0.000018; 0/3 seed-conditional intervals exclude zero).
Curriculum and adaptive point means are +0.003420 and +0.003118, but exclusions
occur in only 2/3 and 1/3 seeds. Q-balanced, curriculum, and mixed use the same
188-event multiset and have identical terminal oracle mastery by construction;
adaptive changes exposure/state and therefore mixes mechanisms. The schedule
columns characterize exposure, spacing, and interleaving only. No policy ranking,
causal efficacy claim, or real-platform claim is permitted.
"""
        ),
        markdown(
            """
## 7. Ecological-realism / measurement-precision continuum

Four matched GrammarCell families were rendered at five openness levels and
assessed by five automated critic roles (20 opportunities, 100 judgments). The
separate diagnostics are retained without a composite “realism score.”
"""
        ),
        code(
            """
format_order = dialogue["format_order"]
dialogue_rows = []
for name in format_order:
    result = dialogue["by_format"][name]
    ratings = result["rating_distributions"]
    dialogue_rows.append({
        "format": name,
        "determinate": ratings["answer_determinacy"].get("determinate", 0),
        "KC clear": ratings["kc_attribution"].get("clear", 0),
        "response-family lower bound (mean)": result["plausible_response_lower_bound"]["mean"],
        "interaction naturalness pass": ratings["interaction_naturalness"].get("pass", 0),
        "target-avoiding shortcut": result["target_avoiding_shortcut"]["true"],
        "incidental operations (mean)": result["incidental_grammar"]["count_per_judgment"]["mean"],
    })
dialogue_frame = pd.DataFrame(dialogue_rows)
display(dialogue_frame)

rates = dialogue_frame.set_index("format")[["determinate", "KC clear", "interaction naturalness pass"]] / 20
rates.plot(marker="o", figsize=(9, 3.5), ylim=(0, 1.05))
plt.ylabel("share of 20 automated judgments")
plt.xlabel("")
plt.xticks(range(len(format_order)), format_order, rotation=20, ha="right")
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """
open_deltas = dialogue["matched_deltas_vs_constrained_cloze"]["open_dialogue"]["separate_metric_deltas_target_minus_reference"]
selected_delta_labels = [
    "determinacy_risk", "kc_attribution_risk", "plausible_response_lower_bound",
    "incidental_grammar_count", "target_avoiding_shortcut", "interaction_naturalness_risk",
]
display(pd.DataFrame([
    {
        "open dialogue − constrained cloze diagnostic": label,
        "matched mean delta": open_deltas[label]["mean"],
        "matched comparisons": open_deltas[label]["count"],
    }
    for label in selected_delta_labels
]))
"""
        ),
        markdown(
            """
**Continuum interpretation.** Constrained cloze was determinate and KC-clear in
17/20 judgments; open dialogue was determinate in 0/20 and KC-clear in 4/20, while
passing interaction naturalness in 20/20. Relative to cloze, open dialogue raised
the plausible response-family lower bound by 3.25 and incidental-operation count
by 1.50, while reducing naturalness risk by 0.15. This is an automated stress test
of the ecological-realism/measurement-precision tradeoff—not human response-
process evidence and not proof that an interface is deployable.
"""
        ),
        markdown(
            """
## 8. Evidence ledger and bounded conclusion
"""
        ),
        code(
            """
MEASUREMENT_REALISM_RESULTS = {
    "platform_audit": {
        "strict_usable_as_stored": counts["usable_as_stored"],
        "strict_items": strict["scope"]["items_reviewed"],
        "cross_audit_union_requiring_action": sum(row["items"] for row in cross_rows[1:]),
    },
    "kc_induction": {
        "activation_union": kc["activation_hypotheses_in_union"],
        "activation_shared_all_three": kc["activation_hypotheses_shared_by_all_replicates"],
        "pairwise_jaccard_range": [
            min(row["jaccard"] for row in kc["pairwise_activation_set_agreement"]),
            max(row["jaccard"] for row in kc["pairwise_activation_set_agreement"]),
        ],
    },
    "matched_bank": {
        "families_passed": g["accepted_family_count"],
        "families_required": g["required_families"],
        "seen_rank": g["accepted_seen_q_rank"],
        "required_seen_rank": g["required_seen_q_rank"],
        "release": False,
    },
    "controlled_worlds": {
        "format_DiD_mean": worlds["contrasts"]["primary_cross_world"]["format_confounding_difference_in_differences"]["across_seed_point_estimate"]["mean"],
        "item_positive_control_D_minus_C_mean": worlds["contrasts"]["primary_cross_world"]["explicit_item_remedy_item_only"]["across_seed_point_estimate"]["mean"],
        "release_eligible": worlds["release_eligible"],
    },
    "validation": {
        "human_validation": False,
        "learner_facing_measurement_validity": "NOT_ASSESSED_FOR_CONTROLLED_WORLDS",
        "platform_plausibility": "NOT_ASSESSED_FOR_CONTROLLED_WORLDS",
        "new_dataset_release": False,
    },
}
MEASUREMENT_REALISM_RESULTS
"""
        ),
        markdown(
            """
### Bounded conclusion

The retained evidence supports a methodological claim: in a known-truth
synthetic environment, measurement nuisance can make an incorrect KC split look
predictively useful, explicit nuisance controls can recover planted effects under
their declared controls, and structured error categories can preserve diagnostic
information discarded by correctness alone. It also exposes hard limits: KC
induction from GrammarCells is unstable, the matched learner-facing bank did not
pass its release gate, and increasing interaction openness traded measurement
precision for naturalness in automated critique.

> **Final boundary:** this is a controlled-scenario results notebook, not a new
> dataset release. Its learner-facing examples are audit/construction evidence,
> not a validated bank. It contains no human validation and supports no claim
> that the scaffold is a realistic platform dataset or that its simulator
> parameters describe human learners.
"""
        ),
    ]

    ids = [cell["id"] for cell in cells]
    assert len(ids) == len(set(ids))
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
            "measurement_realism": {
                "controlled_scenario": True,
                "release_eligible": False,
                "human_validation": False,
                "source_kind": "compact_retained_json_only",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_notebook(), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
