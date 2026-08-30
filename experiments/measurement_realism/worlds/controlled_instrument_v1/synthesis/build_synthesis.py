#!/usr/bin/env python3
"""Deterministic, read-only synthesis of the frozen controlled-world evidence.

The response runs, analyses, study plan, runner, and aggregate are inputs.  This
module never rewrites them.  ``--write`` creates only ``results.json``,
``report.md``, and ``manifest.json`` beside this script; ``--check`` recomputes
the synthesis in memory and verifies those three retained files byte-for-byte.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from statistics import fmean
import sys
from typing import Any, Iterable, Mapping, Sequence


SCENARIO_KIND = "controlled_instrument_scaffold"
STUDY_ID = "measurement_realism_controlled_instrument_v1"
WORLDS = (
    "clean_zero",
    "format_moderate",
    "format_strong_control",
    "item_moderate",
    "item_format_moderate",
    "combined_heterogeneous",
)
SEEDS = (20260829, 20260830, 20260831)
POLICIES = (
    "q_balanced_lab",
    "curriculum",
    "mixed_practice",
    "adaptive_weakness",
)
CONDITIONS = ("A", "B", "C", "D")
EXPECTED_FEATURE_COUNTS = {"A": 20, "B": 74, "C": 23, "D": 146}
ERROR_STREAMS = (
    "binary_only",
    "linked_positive_control",
    "linked_80_percent",
    "within_item_shuffled_negative_control",
)
MODEL_METRICS = (
    "log_loss",
    "brier_score",
    "ece_10_fixed_width",
)
STATE_METRICS = (
    "item_prerequisite_state_rmse",
    "item_prerequisite_state_mae",
    "item_prerequisite_state_correlation",
)
LOCALISATION_METRICS = (
    "candidate_set_size",
    "compatible_top1",
    "compatible_mrr",
    "compatible_log_loss",
    "deficit_top1",
    "deficit_mrr",
    "deficit_log_loss",
    "uniform_top1",
    "uniform_mrr",
    "uniform_log_loss",
)
FALSE_CLAIM_FIELDS = (
    "format_labels_instantiated_as_tasks",
    "learner_facing_item_bank",
    "measurement_validity_claimed",
    "platform_plausibility_claimed",
    "response_space_defined",
)
PRIMARY_CONTRAST_INTERPRETATIONS = {
    "format_confounding_difference_in_differences": (
        "Negative means planted format nuisance increases false format-split "
        "model B's predictive advantage relative to shared-K* model A. It does "
        "not mean that an explicitly corrected model wins and does not validate "
        "B as a psychological ontology."
    ),
    "explicit_format_remedy": (
        "Negative means shared-K* model C with an explicit observed format "
        "covariate predicts better than false format-split model B in the "
        "strong planted-format control world."
    ),
    "explicit_item_remedy_item_only": (
        "Negative means model D recovers deliberately planted stable effects "
        "for acquisition-seen item IDs better than C in the item-only world."
    ),
    "explicit_item_remedy_combined": (
        "Negative means model D recovers deliberately planted stable effects "
        "for acquisition-seen item IDs better than C in the item-plus-format world."
    ),
}


class SynthesisError(ValueError):
    """Raised when a frozen input or scientific invariant fails validation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def semantic_hash(rows: Iterable[Any]) -> str:
    """Match the frozen runner's newline-delimited semantic hash."""

    digest = hashlib.sha256()
    for row in rows:
        payload = json.dumps(
            row,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        digest.update(payload)
        digest.update(b"\n")
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SynthesisError(f"expected JSON object: {path}")
    return value


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SynthesisError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise SynthesisError(f"expected object at {path}:{line_number}")
            rows.append(row)
    return rows


def repo_root_from(path: Path) -> Path:
    for candidate in (path.resolve(), *path.resolve().parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise SynthesisError(f"could not locate repository root above {path}")


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SynthesisError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def require_close(actual: float, expected: float, label: str, tolerance: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance):
        raise SynthesisError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def validate_claim_boundary(plan: Mapping[str, Any]) -> None:
    require_equal(plan.get("controlled_scenario"), True, "controlled_scenario")
    require_equal(plan.get("release_eligible"), False, "release_eligible")
    require_equal(plan.get("scenario_kind"), SCENARIO_KIND, "scenario_kind")
    boundary = plan.get("claim_boundary")
    if not isinstance(boundary, Mapping):
        raise SynthesisError("study plan claim_boundary is missing")
    for field in FALSE_CLAIM_FIELDS:
        require_equal(boundary.get(field), False, f"claim_boundary.{field}")
    require_equal(
        boundary.get("permitted_claim"),
        "controlled_structural_sensitivity_only",
        "claim_boundary.permitted_claim",
    )
    require_equal(
        plan.get("production_curated_bank_evidence"),
        None,
        "production_curated_bank_evidence",
    )


def validate_retained_manifest_claims(manifest: Mapping[str, Any], label: str) -> None:
    require_equal(manifest.get("controlled_scenario"), True, f"{label}.controlled_scenario")
    require_equal(manifest.get("release_eligible"), False, f"{label}.release_eligible")
    require_equal(manifest.get("scenario_kind"), SCENARIO_KIND, f"{label}.scenario_kind")
    if "learner_facing_measurement_validity" in manifest:
        require_equal(
            manifest.get("learner_facing_measurement_validity"),
            "NOT_ASSESSED",
            f"{label}.learner_facing_measurement_validity",
        )
    if "platform_plausibility" in manifest:
        require_equal(
            manifest.get("platform_plausibility"),
            "NOT_ASSESSED",
            f"{label}.platform_plausibility",
        )


def verify_hash(path: Path, expected: str, label: str, recorded: dict[str, str], repo: Path) -> None:
    if not path.is_file():
        raise SynthesisError(f"missing {label}: {path}")
    actual = sha256_file(path)
    require_equal(actual, expected, f"{label} sha256")
    try:
        key = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        key = str(path.resolve())
    recorded[key] = actual


def verify_declared_artifacts(
    parent: Path,
    artifacts: Mapping[str, Any],
    label: str,
    recorded: dict[str, str],
    repo: Path,
) -> None:
    if not artifacts:
        raise SynthesisError(f"{label} declares no artifacts")
    for relative, expected in sorted(artifacts.items()):
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise SynthesisError(f"invalid artifact declaration in {label}")
        verify_hash(parent / relative, expected, f"{label}/{relative}", recorded, repo)


def seed_summary(values_by_seed: Mapping[str, float]) -> dict[str, Any]:
    require_equal(tuple(int(seed) for seed in values_by_seed), SEEDS, "seed summary order")
    values = [float(values_by_seed[str(seed)]) for seed in SEEDS]
    if not all(math.isfinite(value) for value in values):
        raise SynthesisError("seed summary contains a non-finite value")
    return {
        "values_by_seed": {str(seed): values[index] for index, seed in enumerate(SEEDS)},
        "mean": float(fmean(values)),
        "minimum": float(min(values)),
        "maximum": float(max(values)),
        "n_seeds": len(values),
    }


def metric_bundle(per_seed: Mapping[str, Mapping[str, float]], metrics: Sequence[str]) -> dict[str, Any]:
    return {
        "per_seed": {seed: {metric: float(row[metric]) for metric in metrics} for seed, row in per_seed.items()},
        "across_seed": {
            metric: seed_summary({seed: float(row[metric]) for seed, row in per_seed.items()})
            for metric in metrics
        },
    }


def run_name(world: str, policy: str, seed: int) -> str:
    return f"{world}__{policy}__seed_{seed}"


def prediction_identity(rows: Sequence[Mapping[str, Any]]) -> list[list[Any]]:
    return [
        [str(row["learner_id"]), int(row["sequence_index"]), str(row["item_id"])]
        for row in rows
    ]


def primary_prediction_identity(rows: Sequence[Mapping[str, Any]]) -> list[list[Any]]:
    return [identity for identity, row in zip(prediction_identity(rows), rows) if row["grammar_regime"] == "seen"]


def assert_cross_world_row_alignment(
    hashes_by_seed: Mapping[str, Mapping[str, str]], label: str
) -> None:
    require_equal(tuple(int(seed) for seed in hashes_by_seed), SEEDS, f"{label} seeds")
    for seed, by_world in hashes_by_seed.items():
        require_equal(tuple(by_world), WORLDS, f"{label} worlds/{seed}")
        values = set(by_world.values())
        if len(values) != 1:
            raise SynthesisError(f"{label} differs across worlds for seed {seed}: {by_world}")


def _expected_run_matrix() -> list[dict[str, Any]]:
    rows = [
        {"world_id": world, "policy_id": "q_balanced_lab", "seed": seed}
        for world in WORLDS
        for seed in SEEDS
    ]
    rows.extend(
        {"world_id": "combined_heterogeneous", "policy_id": policy, "seed": seed}
        for policy in POLICIES[1:]
        for seed in SEEDS
    )
    return rows


def _validate_plan_and_inputs(
    worlds_dir: Path, repo: Path, recorded: dict[str, str]
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    plan_path = worlds_dir / "study_plan.json"
    plan = read_json(plan_path)
    plan_sha = sha256_file(plan_path)
    recorded[plan_path.resolve().relative_to(repo.resolve()).as_posix()] = plan_sha
    validate_claim_boundary(plan)
    require_equal(plan.get("study_id"), STUDY_ID, "study_id")
    require_equal(tuple(plan.get("world_ids", [])), WORLDS, "world_ids")
    require_equal(tuple(plan.get("seeds", [])), SEEDS, "seeds")
    require_equal(tuple(plan.get("policies", [])), POLICIES, "policies")
    require_equal(plan.get("run_matrix"), _expected_run_matrix(), "run_matrix")
    require_equal(plan.get("created_before_response_generation"), True, "pre-response plan")
    require_equal(
        plan.get("status"),
        "PREREGISTERED_CONTROLLED_SCENARIO_BEFORE_RESPONSES",
        "plan status",
    )
    for input_id, declaration in sorted(plan.get("inputs", {}).items()):
        if not isinstance(declaration, Mapping):
            raise SynthesisError(f"invalid plan input: {input_id}")
        path = repo / str(declaration["path"])
        verify_hash(path, str(declaration["sha256"]), f"plan input {input_id}", recorded, repo)
        require_equal(path.stat().st_size, int(declaration["bytes"]), f"plan input bytes {input_id}")
    runner_path = repo / str(plan["inputs"]["implementation_script"]["path"])
    source_dir = repo / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    spec = importlib.util.spec_from_file_location(
        "measurement_realism_worlds_frozen_for_synthesis", runner_path
    )
    if spec is None or spec.loader is None:
        raise SynthesisError("could not load frozen measurement-world runner")
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    # Re-evaluate every semantic plan field against the frozen runner/config.
    # Package patch versions can drift after response generation; pin only the
    # runtime-version field to its recorded value.  The retained synthesis is
    # intentionally independent of the interpreter used to check it.
    runner._planned_runtime_versions = lambda: plan["runtime_versions"]
    replayed_plan, config, _, _ = runner.validate_run_plan(
        worlds_dir, controlled_scenario=True
    )
    require_equal(replayed_plan, plan, "full semantic study-plan replay")
    controlled = config.get("controlled_scenario_overlay", {})
    require_equal(controlled.get("claim_boundary"), plan["claim_boundary"], "config claim boundary")
    failed_bank = controlled.get("failed_curated_bank_evidence", {})
    require_equal(failed_bank.get("accepted_content_used"), False, "accepted content use")
    require_equal(failed_bank.get("rejected_content_used"), False, "rejected content use")
    return plan, plan_sha, {
        "frozen_response_runtime_versions": plan["runtime_versions"],
        "semantic_replay_runtime_field": "pinned_to_frozen_plan_while_all_other_fields_replayed",
    }


def _validate_response_run(
    run_dir: Path,
    *,
    world: str,
    policy: str,
    seed: int,
    plan_sha: str,
    recorded: dict[str, str],
    repo: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = run_dir / "run_manifest.json"
    manifest = read_json(manifest_path)
    recorded[manifest_path.resolve().relative_to(repo.resolve()).as_posix()] = sha256_file(manifest_path)
    validate_retained_manifest_claims(manifest, f"response {run_dir.name}")
    require_equal(manifest.get("run_kind"), "controlled_instrument_response_only", "response run_kind")
    require_equal(manifest.get("world_id"), world, "response world")
    require_equal(manifest.get("policy_id"), policy, "response policy")
    require_equal(manifest.get("seed"), seed, "response seed")
    require_equal(manifest.get("study_plan_sha256"), plan_sha, "response plan hash")
    require_equal(manifest.get("learners"), 500, "response learners")
    verify_declared_artifacts(run_dir, manifest.get("artifacts", {}), "response artifacts", recorded, repo)
    diagnostic = read_json(run_dir / "observable_diagnostics.json")
    return manifest, diagnostic


def _validate_analysis_run(
    run_dir: Path,
    *,
    world: str,
    seed: int,
    response_manifest_sha: str,
    implementation_sha: str,
    recorded: dict[str, str],
    repo: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    analysis_dir = run_dir / "analysis"
    manifest_path = analysis_dir / "analysis_manifest.json"
    manifest = read_json(manifest_path)
    recorded[manifest_path.resolve().relative_to(repo.resolve()).as_posix()] = sha256_file(manifest_path)
    validate_retained_manifest_claims(manifest, f"analysis {run_dir.name}")
    require_equal(manifest.get("analysis_kind"), "controlled_instrument_analysis_v1", "analysis kind")
    require_equal(manifest.get("world_id"), world, "analysis world")
    require_equal(manifest.get("policy_id"), "q_balanced_lab", "analysis policy")
    require_equal(manifest.get("seed"), seed, "analysis seed")
    require_equal(manifest.get("response_run_manifest_sha256"), response_manifest_sha, "analysis response hash")
    require_equal(manifest.get("implementation_sha256"), implementation_sha, "analysis implementation hash")
    verify_declared_artifacts(analysis_dir, manifest.get("artifacts", {}), "analysis artifacts", recorded, repo)
    models = read_json(analysis_dir / "model_results.json")
    require_equal(tuple(models.get("conditions", {})), CONDITIONS, "A-D condition order")
    require_equal(models.get("primary_evaluation_scope"), "seen_terminal_probes", "primary scope")
    full_hash = str(models["evaluation_row_sha256"])
    seen_hash = str(models["primary_seen_evaluation_row_sha256"])
    for condition in CONDITIONS:
        row = models["conditions"][condition]
        require_equal(row.get("evaluation_row_sha256"), full_hash, f"{condition} full row hash")
        require_equal(row.get("primary_seen_evaluation_row_sha256"), seen_hash, f"{condition} seen row hash")
        require_equal(row.get("primary_evaluation_scope"), "seen_terminal_probes", f"{condition} scope")
        require_equal(row.get("training_design_full_rank"), True, f"{condition} full-rank fit")
        require_equal(row.get("features"), EXPECTED_FEATURE_COUNTS[condition], f"{condition} feature count")
        require_equal(row.get("fitted_parameters", {}).get("optimizer", {}).get("converged"), True, f"{condition} convergence")
        metrics = row.get("metrics", {})
        state = row.get("state_recovery", {})
        require_equal(metrics.get("n"), 11808, f"{condition} seen-probe n")
        require_equal(
            state.get("by_grammar_regime", {}).get("seen", {}).get("n"),
            11808,
            f"{condition} seen state n",
        )
        for metric in MODEL_METRICS:
            value = float(metrics[metric])
            if not math.isfinite(value) or value < 0:
                raise SynthesisError(f"invalid {condition} metric {metric}: {value}")
            if metric in {"brier_score", "ece_10_fixed_width"} and value > 1:
                raise SynthesisError(f"out-of-range {condition} metric {metric}: {value}")
        for metric in STATE_METRICS:
            value = float(state[metric])
            if not math.isfinite(value):
                raise SynthesisError(f"invalid {condition} state metric {metric}: {value}")
            if metric.endswith(("rmse", "mae")) and value < 0:
                raise SynthesisError(f"negative {condition} state metric {metric}: {value}")
            if metric.endswith("correlation") and not -1 <= value <= 1:
                raise SynthesisError(f"out-of-range {condition} state correlation: {value}")
    predictions = read_jsonl_gz(analysis_dir / "test_predictions.jsonl.gz")
    identities = prediction_identity(predictions)
    primary_identities = primary_prediction_identity(predictions)
    require_equal(semantic_hash(identities), full_hash, "prediction full semantic row hash")
    require_equal(semantic_hash(primary_identities), seen_hash, "prediction seen semantic row hash")
    for condition in CONDITIONS:
        row = models["conditions"][condition]
        require_equal(len(predictions), int(row["metrics_all_terminal_probes"]["n"]), f"{condition} full probe n")
        require_equal(len(primary_identities), int(row["metrics"]["n"]), f"{condition} seen probe n")
    return models, predictions, manifest


def _load_and_validate_frozen_evidence(worlds_dir: Path) -> dict[str, Any]:
    repo = repo_root_from(worlds_dir)
    canonical_worlds_dir = (
        repo
        / "experiments"
        / "measurement_realism"
        / "worlds"
        / "controlled_instrument_v1"
    ).resolve()
    require_equal(worlds_dir.resolve(), canonical_worlds_dir, "canonical controlled worlds root")
    recorded: dict[str, str] = {}
    plan, plan_sha, runtime_replay = _validate_plan_and_inputs(worlds_dir, repo, recorded)
    implementation_sha = str(plan["inputs"]["implementation_script"]["sha256"])

    models_by_world_seed: dict[str, dict[str, dict[str, Any]]] = {world: {} for world in WORLDS}
    predictions_by_world_seed: dict[str, dict[str, list[dict[str, Any]]]] = {world: {} for world in WORLDS}
    diagnostics_by_policy_seed: dict[str, dict[str, dict[str, Any]]] = {policy: {} for policy in POLICIES}
    run_manifest_hashes: dict[str, str] = {}
    analysis_manifest_hashes: dict[str, str] = {}

    expected_run_names = {
        run_name(str(run["world_id"]), str(run["policy_id"]), int(run["seed"]))
        for run in _expected_run_matrix()
    }
    actual_run_names = {
        path.name for path in (worlds_dir / "runs").iterdir() if path.is_dir()
    }
    require_equal(actual_run_names, expected_run_names, "planned run-directory set")

    for run in _expected_run_matrix():
        world, policy, seed = str(run["world_id"]), str(run["policy_id"]), int(run["seed"])
        run_dir = worlds_dir / "runs" / run_name(world, policy, seed)
        response, diagnostic = _validate_response_run(
            run_dir,
            world=world,
            policy=policy,
            seed=seed,
            plan_sha=plan_sha,
            recorded=recorded,
            repo=repo,
        )
        run_manifest_hashes[run_dir.name] = sha256_file(run_dir / "run_manifest.json")
        if world == "combined_heterogeneous":
            diagnostics_by_policy_seed[policy][str(seed)] = diagnostic
        if policy == "q_balanced_lab":
            models, predictions, analysis_manifest = _validate_analysis_run(
                run_dir,
                world=world,
                seed=seed,
                response_manifest_sha=run_manifest_hashes[run_dir.name],
                implementation_sha=implementation_sha,
                recorded=recorded,
                repo=repo,
            )
            models_by_world_seed[world][str(seed)] = models
            predictions_by_world_seed[world][str(seed)] = predictions
            analysis_manifest_hashes[run_dir.name] = sha256_file(run_dir / "analysis" / "analysis_manifest.json")

    full_hashes = {
        str(seed): {world: str(models_by_world_seed[world][str(seed)]["evaluation_row_sha256"]) for world in WORLDS}
        for seed in SEEDS
    }
    seen_hashes = {
        str(seed): {world: str(models_by_world_seed[world][str(seed)]["primary_seen_evaluation_row_sha256"]) for world in WORLDS}
        for seed in SEEDS
    }
    assert_cross_world_row_alignment(full_hashes, "full evaluation-row hash")
    assert_cross_world_row_alignment(seen_hashes, "primary seen evaluation-row hash")
    for seed in SEEDS:
        reference = prediction_identity(predictions_by_world_seed[WORLDS[0]][str(seed)])
        for world in WORLDS[1:]:
            require_equal(
                prediction_identity(predictions_by_world_seed[world][str(seed)]),
                reference,
                f"cross-world prediction identities/{seed}/{world}",
            )

    aggregate_dir = worlds_dir / "aggregate"
    aggregate_manifest_path = aggregate_dir / "manifest.json"
    aggregate_manifest = read_json(aggregate_manifest_path)
    recorded[aggregate_manifest_path.resolve().relative_to(repo.resolve()).as_posix()] = sha256_file(aggregate_manifest_path)
    validate_retained_manifest_claims(aggregate_manifest, "aggregate manifest")
    require_equal(aggregate_manifest.get("aggregate_kind"), "controlled_instrument_cross_scenario_v1", "aggregate kind")
    require_equal(aggregate_manifest.get("study_plan_sha256"), plan_sha, "aggregate plan hash")
    verify_declared_artifacts(aggregate_dir, aggregate_manifest.get("artifacts", {}), "aggregate artifacts", recorded, repo)
    aggregate = read_json(aggregate_dir / "results.json")
    validate_retained_manifest_claims(aggregate, "aggregate results")
    require_equal(aggregate.get("study_id"), STUDY_ID, "aggregate study_id")
    require_equal(tuple(aggregate.get("seeds", [])), SEEDS, "aggregate seeds")
    require_equal(aggregate.get("primary_scope"), "seen_terminal_probes", "aggregate scope")

    for world in WORLDS:
        for seed in SEEDS:
            source = models_by_world_seed[world][str(seed)]
            for condition in CONDITIONS:
                require_close(
                    aggregate["condition_world_seed_log_loss"][world][str(seed)][condition],
                    source["conditions"][condition]["metrics"]["log_loss"],
                    f"aggregate log loss/{world}/{seed}/{condition}",
                )
    for contrast_id, contrast in aggregate["primary_cross_world_contrasts"].items():
        if contrast_id not in PRIMARY_CONTRAST_INTERPRETATIONS:
            raise SynthesisError(f"unknown aggregate contrast: {contrast_id}")
        for seed in SEEDS:
            expected = sum(
                float(term["coefficient"])
                * float(models_by_world_seed[str(term["world_id"])][str(seed)]["conditions"][str(term["condition"])]["metrics"]["log_loss"])
                for term in contrast["terms"]
            )
            require_close(
                contrast["per_seed"][str(seed)]["point_estimate"],
                expected,
                f"aggregate contrast/{contrast_id}/{seed}",
            )

    return {
        "repo": repo,
        "plan": plan,
        "plan_sha": plan_sha,
        "aggregate": aggregate,
        "aggregate_manifest": aggregate_manifest,
        "models": models_by_world_seed,
        "predictions": predictions_by_world_seed,
        "diagnostics": diagnostics_by_policy_seed,
        "recorded_hashes": dict(sorted(recorded.items())),
        "run_manifest_hashes": dict(sorted(run_manifest_hashes.items())),
        "analysis_manifest_hashes": dict(sorted(analysis_manifest_hashes.items())),
        "row_hashes": {"full": full_hashes, "primary_seen": seen_hashes},
        "runtime_replay": runtime_replay,
    }


def _model_summary(models: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for world in WORLDS:
        output[world] = {}
        for condition in CONDITIONS:
            per_seed: dict[str, dict[str, float]] = {}
            for seed in SEEDS:
                row = models[world][str(seed)]["conditions"][condition]
                metrics = {metric: float(row["metrics"][metric]) for metric in MODEL_METRICS}
                metrics.update({metric: float(row["state_recovery"][metric]) for metric in STATE_METRICS})
                per_seed[str(seed)] = metrics
            output[world][condition] = metric_bundle(per_seed, (*MODEL_METRICS, *STATE_METRICS))
    return {
        "analysis_status": "preregistered_estimand_reexpression",
        "primary_scope": "seen_terminal_probes",
        "models": output,
    }


def _paired_summary(rows_by_seed: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "per_seed": {seed: dict(row) for seed, row in rows_by_seed.items()},
        "point_estimate_across_seed": seed_summary(
            {seed: float(row["point_estimate"]) for seed, row in rows_by_seed.items()}
        ),
        "uncertainty_scope": (
            "Percentile intervals resample held-out test learners after one frozen fit and "
            "hyperparameter selection. They are conditional on the retained train/dev sample, "
            "instrument, simulator seed, and model selection; they do not cover refitting, "
            "instrument/item sampling, or population-level simulator uncertainty."
        ),
    }


def _contrast_summary(
    aggregate: Mapping[str, Any], models: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> dict[str, Any]:
    primary = {}
    for contrast_id, row in aggregate["primary_cross_world_contrasts"].items():
        primary[contrast_id] = {
            "terms": row["terms"],
            "per_seed": row["per_seed"],
            "across_seed_point_estimate": row["across_seed_point_estimate"],
            "frozen_aggregate_sign_gloss": row["delta_sign"],
            "corrected_sign_gloss": PRIMARY_CONTRAST_INTERPRETATIONS[contrast_id],
        }

    def within_world(world: str, contrast: str) -> dict[str, Any]:
        return _paired_summary(
            {
                str(seed): models[world][str(seed)]["paired_log_loss_intervals"][contrast]
                for seed in SEEDS
            }
        )

    return {
        "analysis_status": "preregistered_estimand_reexpression_with_posthoc_interpretive_labels",
        "primary_cross_world": primary,
        "clean_zero_falsification_B_minus_A": within_world("clean_zero", "B_minus_A"),
        "item_only_false_split_B_minus_A": within_world("item_moderate", "B_minus_A"),
        "combined_heterogeneous": {
            "B_minus_A": within_world("combined_heterogeneous", "B_minus_A"),
            "C_minus_B": within_world("combined_heterogeneous", "C_minus_B"),
            "D_minus_C": within_world("combined_heterogeneous", "D_minus_C"),
        },
        "interpretation": {
            "format": (
                "The robust negative format DiD and negative C-minus-B contrast establish "
                "prediction-level sensitivity to a planted format label effect in this "
                "content-free scaffold. They do not establish effects of real task formats."
            ),
            "item": (
                "D is an oracle-aligned same-seen-item positive control. The planted seen-item "
                "vector is constructed in D's Q*/format-orthogonal basis, and probe-only items "
                "are zero encoded. D-minus-C therefore does not establish arbitrary item "
                "deconfounding or unseen-item generalisation."
            ),
            "false_split_item_absorption": (
                "Item-only B-minus-A is mixed and near zero across seeds with every conditional "
                "interval crossing zero; these runs do not support a claim that false "
                "format-split KCs absorb item difficulty."
            ),
            "heterogeneity": (
                "In the combined heterogeneous world, C-minus-B is mixed and all conditional "
                "intervals cross zero, whereas D-minus-C remains negative in all seeds. The "
                "explicit format remedy is not consistently demonstrated under combined "
                "heterogeneity; the aligned item positive control is."
            ),
        },
    }


def _error_summary(
    worlds_dir: Path,
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    repo = evidence["repo"]
    recorded: dict[str, str] = {}
    stream_per_seed: dict[str, dict[str, dict[str, float]]] = {stream: {} for stream in ERROR_STREAMS}
    localisation_per_seed: dict[str, dict[str, dict[str, float]]] = {stream: {} for stream in ERROR_STREAMS}
    terminal_per_seed: dict[str, dict[str, dict[str, float]]] = {stream: {} for stream in ERROR_STREAMS}
    paired: dict[str, dict[str, Any]] = {}
    shuffle_audit: dict[str, Any] = {}
    localisation_support: dict[str, dict[str, int]] = {stream: {} for stream in ERROR_STREAMS}
    terminal_support: dict[str, dict[str, int]] = {stream: {} for stream in ERROR_STREAMS}

    for seed in SEEDS:
        run_dir = worlds_dir / "runs" / run_name("combined_heterogeneous", "q_balanced_lab", seed)
        analysis_dir = run_dir / "analysis"
        error_path = analysis_dir / "error_history_model_results.json"
        error_predictions_path = analysis_dir / "error_test_predictions.jsonl.gz"
        audit_path = run_dir / "error_stream_audit.json"
        manifest = read_json(analysis_dir / "analysis_manifest.json")
        for path in (error_path, error_predictions_path, audit_path):
            expected = (
                manifest["artifacts"].get(path.name)
                if path.parent == analysis_dir
                else read_json(run_dir / "run_manifest.json")["artifacts"].get(path.name)
            )
            if expected is None:
                raise SynthesisError(f"error artifact not declared: {path}")
            verify_hash(path, expected, f"error artifact {path.name}", recorded, repo)

        error = read_json(error_path)
        require_equal(error.get("condition_held_fixed"), "D", "error model condition")
        base_models = evidence["models"]["combined_heterogeneous"][str(seed)]
        require_equal(error.get("evaluation_row_sha256"), base_models["evaluation_row_sha256"], "error/base row hash")
        error_predictions = read_jsonl_gz(error_predictions_path)
        base_predictions = evidence["predictions"]["combined_heterogeneous"][str(seed)]
        require_equal(prediction_identity(error_predictions), prediction_identity(base_predictions), "error prediction identities")
        require_equal(
            [int(row["correct"]) for row in error_predictions],
            [int(row["correct"]) for row in base_predictions],
            "error prediction outcomes",
        )
        require_equal(set(error.get("streams", {})), set(ERROR_STREAMS), "error stream set")
        for stream in ERROR_STREAMS:
            row = error["streams"][stream]
            require_equal(row.get("condition"), "D", f"error condition/{stream}")
            require_equal(row.get("evaluation_row_sha256"), error["evaluation_row_sha256"], f"error row hash/{stream}")
            require_equal(
                row.get("primary_seen_evaluation_row_sha256"),
                base_models["primary_seen_evaluation_row_sha256"],
                f"error primary seen row hash/{stream}",
            )
            metrics = {metric: float(row["metrics"][metric]) for metric in MODEL_METRICS}
            metrics.update({metric: float(row["state_recovery"][metric]) for metric in STATE_METRICS})
            stream_per_seed[stream][str(seed)] = metrics
            localisation_per_seed[stream][str(seed)] = {
                metric: float(error["failed_kc_localisation"][stream][metric])
                for metric in LOCALISATION_METRICS
            }
            target_semantics = error["failed_kc_localisation"][stream].get("target_semantics")
            require_equal(
                target_semantics,
                "post_outcome_deficit_proportional_attribution_not_causal_failure",
                f"failed-KC target semantics/{stream}",
            )
            localisation_support[stream][str(seed)] = int(
                error["failed_kc_localisation"][stream]["n"]
            )
            terminal_per_seed[stream][str(seed)] = {
                "rmse": float(error["terminal_kc_state_recovery_secondary"][stream]["rmse"]),
                "mae": float(error["terminal_kc_state_recovery_secondary"][stream]["mae"]),
            }
            terminal_row = error["terminal_kc_state_recovery_secondary"][stream]
            require_equal(terminal_row.get("estimator"), "beta_1_1_smoothed_attributed_kc_evidence", f"terminal estimator/{stream}")
            require_equal(terminal_row.get("learners"), 82, f"terminal learners/{stream}")
            require_equal(terminal_row.get("learner_kc_pairs"), 1476, f"terminal pairs/{stream}")
            terminal_support[stream][str(seed)] = int(terminal_row["learner_kc_pairs"])
        for contrast_id, row in error["paired_log_loss_intervals"].items():
            paired.setdefault(contrast_id, {})[str(seed)] = row
        audit = read_json(audit_path)
        shuffle_audit[str(seed)] = {
            "incorrect_events": int(audit["incorrect_events"]),
            "shuffle_blocks": int(audit["shuffle_blocks"]),
            "non_singleton_unchanged_permutations": int(audit["non_singleton_unchanged_permutations"]),
            "common_random_hashes": audit["common_random_hashes"],
        }

    return (
        {
            "analysis_status": "posthoc_descriptive_summary_of_preregistered_controls",
            "prediction_and_item_prerequisite_state": {
                stream: metric_bundle(per_seed, (*MODEL_METRICS, *STATE_METRICS))
                for stream, per_seed in stream_per_seed.items()
            },
            "paired_prediction_log_loss": {
                contrast_id: _paired_summary(rows) for contrast_id, rows in paired.items()
            },
            "failed_kc_localisation": {
                stream: {
                    **metric_bundle(per_seed, LOCALISATION_METRICS),
                    "support_n_by_seed": localisation_support[stream],
                    "support_scope": "all_500_learners_incorrect_multi_kc_probes",
                    "target_semantics": "post_outcome_deficit_proportional_attribution_not_causal_failure",
                }
                for stream, per_seed in localisation_per_seed.items()
            },
            "secondary_terminal_kc_evidence_diagnostic": {
                stream: {
                    **metric_bundle(per_seed, ("rmse", "mae")),
                    "support_learner_kc_pairs_by_seed": terminal_support[stream],
                    "support": "82 held-out test learners x 18 K* KCs per seed",
                    "estimator": "beta_1_1_smoothed_attributed_kc_evidence",
                }
                for stream, per_seed in terminal_per_seed.items()
            },
            "shuffle_audit": shuffle_audit,
            "interpretation": {
                "failed_kc_target": (
                    "The oracle failed-KC label is a post-outcome deficit-proportional "
                    "attribution, not a causal failure event or a human-error annotation."
                ),
                "linked_positive_control": (
                    "The linked stream reveals planted oracle-linked diagnostic information by "
                    "construction; localisation is an information-channel positive control, not "
                    "a learned human-error localiser."
                ),
                "linked_80_percent": (
                    "The 80% stream masks the remaining 20% as unresolved; it does not replace "
                    "them with incorrect categories and is therefore a thinning control, not a "
                    "general misclassification-noise experiment."
                ),
                "shuffled_control": (
                    "Within-item/phase shuffling breaks learner linkage but preserves item-level "
                    "category marginals and structural compatibility. It is not a fully random "
                    "label null."
                ),
                "localisation_log_loss": (
                    "The shuffled localisation log loss is dominated by the declared 1e-12 "
                    "probability floor for incompatible attributions and is not comparable with "
                    "next-response log loss."
                ),
                "terminal_kc": (
                    "The terminal-KC quantity is a Beta(1,1)-smoothed evidence-count attribution "
                    "diagnostic, not fitted A/B/C/D KC mastery. Shuffled categories also improve "
                    "this diagnostic over binary attribution, so its gains cannot by themselves "
                    "establish learner-specific diagnostic information."
                ),
                "cross_seed_prediction": (
                    "Linked prediction gains are small and their conditional intervals do not "
                    "exclude zero in every seed. No cross-seed error-history aggregate or "
                    "population-level uncertainty estimate is available."
                ),
            },
        },
        recorded,
    )


def _schedule_summary(diagnostics: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    metric_names = (
        "acquisition_accuracy",
        "probe_accuracy",
        "overall_accuracy",
        "item_exposure_gini",
        "kc_exposure_gini_design_linked",
        "median_repetition_gap",
        "median_cell_repetition_gap",
        "lag_one_correctness_correlation",
        "mean_adjacent_q_jaccard_design_linked",
        "q95_adjacent_q_jaccard_design_linked",
    )
    per_policy: dict[str, Any] = {}
    for policy in POLICIES:
        per_seed = {}
        for seed in SEEDS:
            row = diagnostics[policy][str(seed)]
            per_seed[str(seed)] = {
                "acquisition_accuracy": float(row["phase_accuracy"]["acquisition"]["accuracy"]),
                "probe_accuracy": float(row["phase_accuracy"]["probe"]["accuracy"]),
                "overall_accuracy": float(row["overall_accuracy"]),
                "item_exposure_gini": float(row["acquisition_item_exposure"]["gini"]),
                "kc_exposure_gini_design_linked": float(row["acquisition_kc_exposure"]["gini"]),
                "median_repetition_gap": float(row["repetition_gap"]["median"]),
                "median_cell_repetition_gap": float(row["cell_repetition_gap"]["median"]),
                "lag_one_correctness_correlation": float(row["lag_one_correctness_correlation"]),
                "mean_adjacent_q_jaccard_design_linked": float(row["adjacent_q_jaccard"]["mean"]),
                "q95_adjacent_q_jaccard_design_linked": float(row["adjacent_q_jaccard"]["q95"]),
            }
            if policy == "adaptive_weakness":
                per_seed[str(seed)]["selection_propensity_mean"] = float(row["selection_propensity"]["mean"])
        metrics = (*metric_names, *(("selection_propensity_mean",) if policy == "adaptive_weakness" else ()))
        per_policy[policy] = metric_bundle(per_seed, metrics)

    fixed_probe_equal = all(
        diagnostics["q_balanced_lab"][str(seed)]["phase_accuracy"]["probe"]["accuracy"]
        == diagnostics["curriculum"][str(seed)]["phase_accuracy"]["probe"]["accuracy"]
        == diagnostics["mixed_practice"][str(seed)]["phase_accuracy"]["probe"]["accuracy"]
        for seed in SEEDS
    )
    require_equal(fixed_probe_equal, True, "fixed-multiset policy probe equality")
    return {
        "analysis_status": "posthoc_descriptive_summary_of_preregistered_policy_diagnostics",
        "acquisition_budget_per_learner": 188,
        "efficacy_estimand_defined": False,
        "kt_models_fit_for_alternative_policies": False,
        "policy_ranking_permitted": False,
        "policies": per_policy,
        "fixed_multiset_probe_accuracy_identical_per_seed": fixed_probe_equal,
        "interpretation": (
            "These are descriptive schedule, exposure, and history-morphology diagnostics. "
            "q-balanced, curriculum, and mixed policies use the same acquisition occurrence "
            "multiset and have exactly equal terminal-probe accuracy within seed under the "
            "order-independent unconditional update rule. Adaptive selection changes exposure. "
            "No randomized policy comparison, paired policy interval, or causal learning-efficacy "
            "estimate is provided; overall accuracy also mixes acquisition and probe rows."
        ),
        "propensity_constraint": (
            "Adaptive propensities condition exploit mass on frozen keyed tie-breaking while "
            "burn-in is marginalized. They are retained as diagnostics and must not be used for "
            "off-policy evaluation without a separately specified conditioning convention."
        ),
    }


def build_synthesis(worlds_dir: Path) -> dict[str, Any]:
    worlds_dir = worlds_dir.resolve()
    evidence = _load_and_validate_frozen_evidence(worlds_dir)
    error, error_hashes = _error_summary(worlds_dir, evidence)
    all_hashes = dict(evidence["recorded_hashes"])
    all_hashes.update(error_hashes)
    return {
        "schema_version": "controlled_world_synthesis_v1",
        "synthesis_kind": "posthoc_controlled_structural_evidence_synthesis",
        "synthesis_timing": "post_response_derived_summary",
        "study_id": STUDY_ID,
        "scenario_kind": SCENARIO_KIND,
        "controlled_scenario": True,
        "release_eligible": False,
        "content_free_instrument": True,
        "claim_boundary": {
            "permitted": "controlled_structural_sensitivity_only",
            "learner_facing_measurement_validity": "NOT_ASSESSED",
            "platform_plausibility": "NOT_ASSESSED",
            "prohibited": [
                "validated_item_bank",
                "platform_plausible_dataset",
                "realistic_learner_opportunities",
                "release_dataset",
                "human_task_format_effect",
            ],
        },
        "verification": {
            "status": "PASS",
            "study_plan_sha256": evidence["plan_sha"],
            "aggregate_manifest_sha256": sha256_file(worlds_dir / "aggregate" / "manifest.json"),
            "aggregate_results_sha256": sha256_file(worlds_dir / "aggregate" / "results.json"),
            "planned_response_runs_verified": len(_expected_run_matrix()),
            "q_balanced_analysis_runs_verified": len(WORLDS) * len(SEEDS),
            "error_analysis_runs_verified": len(SEEDS),
            "declared_input_and_artifact_hashes_verified": len(all_hashes),
            "cross_world_evaluation_rows_aligned": True,
            "semantic_plan_replay": evidence["runtime_replay"],
            "row_hashes": evidence["row_hashes"],
            "input_sha256": dict(sorted(all_hashes.items())),
        },
        "model_conditions": {
            "A": {
                "feature_count": 20,
                "kc_representation": "shared_K_star",
                "nuisance": "none",
            },
            "B": {
                "feature_count": 74,
                "kc_representation": "false_format_split_K_star",
                "nuisance": "implicit_format_through_split_history_and_indicators",
            },
            "C": {
                "feature_count": 23,
                "kc_representation": "shared_K_star",
                "nuisance": "three_observed_format_contrasts",
            },
            "D": {
                "feature_count": 146,
                "kc_representation": "shared_K_star",
                "nuisance": (
                    "format contrasts plus 123-dimensional Q*/format-orthogonal residual "
                    "basis for 144 acquisition-seen item slots; eight probe-only items zero encoded"
                ),
                "role": "oracle_aligned_same_seen_item_positive_control",
            },
        },
        "abcd_seen_terminal_probe_summary": _model_summary(evidence["models"]),
        "contrasts": _contrast_summary(evidence["aggregate"], evidence["models"]),
        "error_history": error,
        "schedule_diagnostics": _schedule_summary(evidence["diagnostics"]),
        "uncertainty_and_generalisation_limits": [
            "All bootstrap intervals are conditional test-learner intervals around frozen fits; they do not include refitting or hyperparameter-selection uncertainty.",
            "Three simulator seeds are summarized by mean and range only and do not support population random-effects inference.",
            "Learners are resampled but the 18 selected seen cells, 144 seen structural item slots, and content-free instrument are fixed.",
            "No multiplicity-adjusted family of tests is reported; interpretation is restricted to preregistered directional controls and descriptive secondary diagnostics.",
            "Item-prerequisite state recovery is not individual-KC mastery recovery, and the retained terminal-KC evidence diagnostic is not fitted A/B/C/D state recovery.",
            "Planted item-effect orthogonality is exact for the equally weighted 144-item seen bank/probe design, not for the 188-event acquisition multiset that duplicates 44 items.",
        ],
        "uncertainty_contract": {
            "interval_type": "learner_cluster_percentile_bootstrap",
            "repeats_per_seed": 2000,
            "resampling_unit": "held_out_test_learner",
            "predictions_refit_within_bootstrap": False,
            "covered": "test-learner variability conditional on the retained fitted/tuned model and stream",
            "not_covered": [
                "training_or_dev_sampling",
                "hyperparameter_selection_or_refitting",
                "instrument_item_or_cell_sampling",
                "simulator_world_uncertainty",
                "between_seed_population_uncertainty",
            ],
            "across_seed_summary": "descriptive_unweighted_mean_minimum_maximum_not_confidence_interval",
        },
        "bottom_line": {
            "supported": [
                "Planted format nuisance can make a false format-split representation predictively attractive relative to shared K*.",
                "An explicit observed format covariate outperforms false format splitting in the strong planted-format control world.",
                "An oracle-aligned seen-item nuisance basis recovers deliberately spanned stable item effects.",
            ],
            "not_supported": [
                "learner-facing format validity or platform plausibility",
                "psychological truth of any KC ontology",
                "general item-difficulty deconfounding or unseen-item generalisation",
                "consistent explicit-format superiority under combined learner heterogeneity",
                "a claim that false format-split KCs absorb item difficulty",
                "causal or human-realistic learner-error localisation",
                "policy learning efficacy",
            ],
        },
    }


def _format_summary(summary: Mapping[str, Any], digits: int = 6) -> str:
    return f"{float(summary['mean']):.{digits}f} [{float(summary['minimum']):.{digits}f}, {float(summary['maximum']):.{digits}f}]"


def _intervals_text(per_seed: Mapping[str, Mapping[str, Any]]) -> str:
    return "; ".join(
        f"{seed}: {float(row['point_estimate']):+.6f} [{float(row['percentile_95'][0]):+.6f}, {float(row['percentile_95'][1]):+.6f}]"
        for seed, row in per_seed.items()
    )


def render_report(result: Mapping[str, Any]) -> str:
    lines = [
        "# Controlled-world evidence synthesis",
        "",
        "Status: **non-release, content-free controlled structural evidence only**. Learner-facing measurement validity and platform plausibility were not assessed.",
        "",
        "## Integrity",
        "",
        f"- Study plan SHA-256: `{result['verification']['study_plan_sha256']}`",
        f"- Aggregate results SHA-256: `{result['verification']['aggregate_results_sha256']}`",
        f"- Verified {result['verification']['planned_response_runs_verified']} response runs, {result['verification']['q_balanced_analysis_runs_verified']} A–D analyses, and {result['verification']['error_analysis_runs_verified']} error analyses.",
        "- All declared hashes passed and the full and seen terminal-probe row identities align across the six q-balanced worlds within seed.",
        "",
        "## Primary controlled contrasts",
        "",
        "| Contrast | Three-seed mean [range] | Conditional per-seed learner intervals |",
        "|---|---:|---|",
    ]
    for contrast_id, row in result["contrasts"]["primary_cross_world"].items():
        lines.append(
            f"| `{contrast_id}` | {_format_summary(row['across_seed_point_estimate'])} | {_intervals_text(row['per_seed'])} |"
        )
    did = result["contrasts"]["primary_cross_world"]["format_confounding_difference_in_differences"]
    lines.extend(
        [
            "",
            "Corrected DiD sign: " + did["corrected_sign_gloss"],
            "",
            "The frozen aggregate's generic sign string is retained for provenance but is wrong for the DiD and is not used here. The aggregate itself was not modified.",
            "",
            "D is an oracle-aligned same-seen-item positive control: planted seen-item effects are constructed in D's own Q*/format-orthogonal span, and probe-only items are zero encoded.",
            "",
            "Item-only B−A is mixed and near zero, with every conditional interval crossing zero: "
            + _intervals_text(result["contrasts"]["item_only_false_split_B_minus_A"]["per_seed"])
            + ". This does not support a claim that false format-split KCs absorb item difficulty.",
            "",
            "Under combined heterogeneity, C−B is mixed and every interval crosses zero, while D−C remains negative in all seeds. The explicit item positive control survives; explicit format superiority is not consistently demonstrated.",
            "",
            "## A–D prediction and item-prerequisite state summaries",
            "",
            "Values are three-seed means with `[minimum, maximum]` ranges on seen terminal probes.",
            "",
            "| World | Model | Log loss | Brier | ECE | State RMSE |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for world in WORLDS:
        for condition in CONDITIONS:
            row = result["abcd_seen_terminal_probe_summary"]["models"][world][condition]["across_seed"]
            lines.append(
                f"| `{world}` | {condition} | {_format_summary(row['log_loss'])} | {_format_summary(row['brier_score'])} | {_format_summary(row['ece_10_fixed_width'])} | {_format_summary(row['item_prerequisite_state_rmse'])} |"
            )

    lines.extend(
        [
            "",
            "Item-prerequisite state is a model-specific nuisance-removed item-level diagnostic, not individual-KC mastery recovery.",
            "",
            "## Structured-error controls",
            "",
            "All error-history models hold condition D fixed. The failed-KC target is a post-outcome deficit-proportional oracle attribution, not a causal human-error label.",
            "",
            "| Stream | Log loss | State RMSE | Localisation top-1 | Terminal-KC evidence RMSE |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    errors = result["error_history"]
    for stream in ERROR_STREAMS:
        prediction = errors["prediction_and_item_prerequisite_state"][stream]["across_seed"]
        localisation = errors["failed_kc_localisation"][stream]["across_seed"]
        terminal = errors["secondary_terminal_kc_evidence_diagnostic"][stream]["across_seed"]
        lines.append(
            f"| `{stream}` | {_format_summary(prediction['log_loss'])} | {_format_summary(prediction['item_prerequisite_state_rmse'])} | {_format_summary(localisation['compatible_top1'])} | {_format_summary(terminal['rmse'])} |"
        )
    lines.extend(
        [
            "",
            "Prediction contrasts against binary history:",
            "",
        ]
    )
    for contrast_id, row in errors["paired_prediction_log_loss"].items():
        lines.append(f"- `{contrast_id}` — {_intervals_text(row['per_seed'])}")
    lines.extend(
        [
            "",
            "Linked prediction gains are small and do not exclude zero in every seed. The 80% control masks rather than misclassifies 20%; within-item shuffling preserves item-level category marginals. Shuffled categories also improve the secondary evidence-count RMSE over binary attribution, so that diagnostic cannot alone establish learner-specific error information.",
            "",
            "Failed-KC localisation uses all learners' incorrect multi-KC probes (support by seed: 22,206; 22,131; 22,331), not only the held-out test learners. Its shuffled log loss is dominated by the 1e-12 incompatible-target floor and is not comparable with next-response log loss.",
            "",
            "## Schedule diagnostics",
            "",
            "These are descriptive history/exposure diagnostics, not efficacy estimates.",
            "",
            "| Policy | Acquisition accuracy | Probe accuracy | Item exposure Gini | Median repetition gap |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for policy in POLICIES:
        row = result["schedule_diagnostics"]["policies"][policy]["across_seed"]
        lines.append(
            f"| `{policy}` | {_format_summary(row['acquisition_accuracy'])} | {_format_summary(row['probe_accuracy'])} | {_format_summary(row['item_exposure_gini'])} | {_format_summary(row['median_repetition_gap'], digits=2)} |"
        )
    lines.extend(
        [
            "",
            "q-balanced, curriculum, and mixed schedules have exactly the same within-seed terminal-probe accuracy because they use the same occurrence multiset under an order-independent unconditional learning update. Adaptive selection changes exposure. Overall accuracy is not used as an efficacy endpoint because it mixes selected acquisition rows with probes.",
            "",
            "## Uncertainty and claim limits",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in result["uncertainty_and_generalisation_limits"])
    lines.extend(
        [
            "",
            "The supported claims concern planted nuisance sensitivity in a content-free controlled instrument. They do not establish deployable items, platform realism, human task-format effects, human error realism, psychological KC truth, or policy learning efficacy.",
            "",
        ]
    )
    return "\n".join(lines)


def _output_paths(worlds_dir: Path) -> dict[str, Path]:
    output_dir = worlds_dir / "synthesis"
    return {
        "results.json": output_dir / "results.json",
        "report.md": output_dir / "report.md",
        "manifest.json": output_dir / "manifest.json",
    }


def build_output_bytes(worlds_dir: Path) -> dict[str, bytes]:
    result = build_synthesis(worlds_dir)
    report = render_report(result).encode("utf-8")
    results = canonical_json_bytes(result)
    script_path = Path(__file__).resolve()
    test_path = script_path.with_name("test_build_synthesis.py")
    schema_path = script_path.with_name("synthesis.schema.json")
    if not test_path.is_file():
        raise SynthesisError(f"focused test is missing: {test_path}")
    if not schema_path.is_file():
        raise SynthesisError(f"synthesis schema is missing: {schema_path}")
    try:
        import jsonschema

        jsonschema.Draft202012Validator(read_json(schema_path)).validate(result)
    except ImportError as exc:
        raise SynthesisError("jsonschema is required to validate retained synthesis") from exc
    manifest = {
        "schema_version": "controlled_world_synthesis_manifest_v1",
        "synthesis_kind": "posthoc_controlled_structural_evidence_synthesis",
        "scenario_kind": SCENARIO_KIND,
        "controlled_scenario": True,
        "release_eligible": False,
        "content_free_instrument": True,
        "synthesis_timing": "post_response_derived_summary",
        "study_plan_sha256": result["verification"]["study_plan_sha256"],
        "aggregate_results_sha256": result["verification"]["aggregate_results_sha256"],
        "implementation": {
            "build_synthesis.py": sha256_file(script_path),
            "test_build_synthesis.py": sha256_file(test_path),
            "synthesis.schema.json": sha256_file(schema_path),
        },
        "artifacts": {
            "results.json": hashlib.sha256(results).hexdigest(),
            "report.md": hashlib.sha256(report).hexdigest(),
        },
    }
    return {"results.json": results, "report.md": report, "manifest.json": canonical_json_bytes(manifest)}


def write_outputs(worlds_dir: Path) -> None:
    paths = _output_paths(worlds_dir)
    payloads = build_output_bytes(worlds_dir)
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"refusing to overwrite retained synthesis output: {path}")
    paths["results.json"].parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for name in ("results.json", "report.md", "manifest.json"):
            path = paths[name]
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payloads[name])
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def check_outputs(worlds_dir: Path) -> None:
    paths = _output_paths(worlds_dir)
    payloads = build_output_bytes(worlds_dir)
    for name, expected in payloads.items():
        path = paths[name]
        if not path.is_file():
            raise SynthesisError(f"retained synthesis output is missing: {path}")
        actual = path.read_bytes()
        if actual != expected:
            raise SynthesisError(f"retained synthesis output changed: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worlds-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Frozen controlled-instrument world root",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Create the three synthesis outputs once")
    mode.add_argument("--check", action="store_true", help="Recompute and byte-check retained outputs")
    args = parser.parse_args()
    if args.write:
        write_outputs(args.worlds_dir)
    else:
        check_outputs(args.worlds_dir)


if __name__ == "__main__":
    main()
