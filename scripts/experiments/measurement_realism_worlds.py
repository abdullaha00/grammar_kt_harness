#!/usr/bin/env python3
"""Direct, auditable measurement-realism worlds over a frozen instrument.

The confirmatory runner has a strict two-stage gate:

1. ``plan`` validates and hashes the frozen config, selected cells, curated
   schema, curated bank, implementation, and fixed acquisition budget.
2. ``run`` refuses to generate a response if any planned byte has changed.

The production path accepts only a curated bank that replays through the
matched-bank freezer and its evidence chain.  A mechanically separate,
explicitly non-release controlled-instrument path can exercise structural
simulator assumptions without learner-facing content.  It requires
``--controlled-scenario`` at every post-freeze stage and supports no claim of
measurement validity or platform plausibility.

:func:`build_synthetic_bank_fixture` remains a visibly fixture-only contract
fixture for unit tests.  Fixture responses are never accepted as scientific
evidence on either path.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import math
import platform
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from importlib.metadata import version as package_version
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grammar_kt.baseline_simulation import build_acquisition_occurrences


DEFAULT_CONFIG = (
    ROOT / "experiments/measurement_realism/design/scenario_config_v1.yaml"
)
DEFAULT_CONTROLLED_CONFIG = (
    ROOT
    / "experiments/measurement_realism/design/controlled_instrument_v1/"
    "scenario_config.yaml"
)
DEFAULT_OUTPUT = ROOT / "experiments/measurement_realism/worlds"
STANDARD_CONFIG_STATUS = "FROZEN_BEFORE_RESPONSE_GENERATION"
CONTROLLED_CONFIG_STATUS = "FROZEN_CONTROLLED_INSTRUMENT_BEFORE_RESPONSES"
CANONICAL_FORMATS = (
    "constrained_cloze",
    "dialogue_completion",
    "multiple_choice",
    "sentence_transformation",
)
MODEL_CONDITIONS = ("A", "B", "C", "D")
OBSERVABLE_FIELDS = (
    "learner_id",
    "item_id",
    "sequence_index",
    "session_index",
    "phase",
    "correct",
    "format",
    "policy_id",
    "selection_propensity",
    "grammar_regime",
    "error_category",
)
ORACLE_ONLY_FIELDS = (
    "active_generator_kcs",
    "mastery_before",
    "mastery_after",
    "aggregated_mastery_before",
    "item_effect",
    "format_effect",
    "learner_ability",
    "learner_learning_rate",
    "learner_guess",
    "learner_slip",
    "response_probability",
    "response_draw",
    "failed_kc",
    "failed_kc_draw",
    "failed_kc_semantics",
    "policy_eligibility_audit",
)
FORBIDDEN_POLICY_FIELDS = frozenset(ORACLE_ONLY_FIELDS)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_hash(rows: Iterable[Any]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    handle_context = (
        gzip.open(source, "rt", encoding="utf-8")
        if source.suffix == ".gz"
        else source.open("r", encoding="utf-8")
    )
    with handle_context as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_frozen_json(path: Path, value: Any, label: str) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]], *, gzip_output: bool) -> None:
    """Write canonical JSONL, with byte-stable gzip when requested.

    ``gzip.open`` embeds the current wall-clock time and the output filename in
    the header.  Both are irrelevant to the scientific stream but make an
    otherwise exact replay hash differently.  An empty header filename and
    ``mtime=0`` make the compressed artifact content-addressable as well as
    semantically deterministic.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip_output:
        with path.open("wb") as raw_handle:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw_handle, mtime=0
            ) as compressed_handle:
                with io.TextIOWrapper(
                    compressed_handle, encoding="utf-8", newline="\n"
                ) as text_handle:
                    for row in rows:
                        text_handle.write(canonical_json(dict(row)) + "\n")
        return
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(dict(row)) + "\n")


def _resolve(root: Path, configured: str) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else root / path


def load_executable_config(
    path: str | Path = DEFAULT_CONFIG, *, root: Path = ROOT
) -> dict[str, Any]:
    """Load the frozen overlay and its content-addressed full proposal."""

    config_path = Path(path).resolve()
    overlay = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if overlay.get("status") == CONTROLLED_CONFIG_STATUS:
        base_path = _resolve(root, overlay["base_executable_config"]["path"])
        if sha256_file(base_path) != overlay["base_executable_config"]["sha256"]:
            raise ValueError("content-addressed base executable config changed")
        config = copy.deepcopy(load_executable_config(base_path, root=root))
        for key, hash_key in (
            ("rows_path", "rows_sha256"),
            ("schema_path", "schema_sha256"),
            ("manifest_path", "manifest_sha256"),
            ("builder_path", "builder_sha256"),
            ("protocol_path", "protocol_sha256"),
            ("execution_plan_path", "execution_plan_sha256"),
        ):
            declared = overlay["controlled_instrument"]
            source = _resolve(root, declared[key])
            if not source.is_file() or sha256_file(source) != declared[hash_key]:
                raise ValueError(f"content-addressed controlled instrument {key} changed")
        selected_path = _resolve(root, overlay["selected_cells"]["path"])
        if sha256_file(selected_path) != overlay["selected_cells"]["sha256"]:
            raise ValueError("controlled-scenario selected cells changed")
        failure_path = _resolve(
            root, overlay["failed_curated_bank_evidence"]["decision_ledger_path"]
        )
        if sha256_file(failure_path) != overlay["failed_curated_bank_evidence"][
            "decision_ledger_sha256"
        ]:
            raise ValueError("failed curated-bank evidence ledger changed")
        manifest = json.loads(
            _resolve(
                root, overlay["controlled_instrument"]["manifest_path"]
            ).read_text(encoding="utf-8")
        )
        if (
            manifest.get("scenario_status")
            != "FROZEN_STRUCTURE_ONLY_BEFORE_RESPONSES"
            or manifest.get("release_eligible") is not False
            or manifest.get("learner_facing_item_bank") is not False
            or manifest.get("measurement_validity_claimed") is not False
            or manifest.get("platform_plausibility_claimed") is not False
            or manifest.get("construction_uses_learner_outcomes") is not False
            or manifest.get("construction_uses_generated_candidate_content") is not False
        ):
            raise ValueError("controlled-instrument manifest claim boundary changed")
        config["design_id"] = overlay["design_id"]
        config["status"] = overlay["status"]
        config["scenario_kind"] = overlay["scenario_kind"]
        config["release_eligible"] = False
        config["controlled_scenario_overlay"] = overlay
        config["_paths"]["config"] = str(config_path)
        config["_paths"]["base_executable_config"] = str(base_path)
        config["_paths"]["selected_cells"] = str(selected_path)
        config["_paths"]["controlled_instrument"] = str(
            _resolve(root, overlay["controlled_instrument"]["rows_path"])
        )
        config["_paths"]["controlled_instrument_schema"] = str(
            _resolve(root, overlay["controlled_instrument"]["schema_path"])
        )
        config["_paths"]["controlled_instrument_manifest"] = str(
            _resolve(root, overlay["controlled_instrument"]["manifest_path"])
        )
        config["_paths"]["controlled_instrument_builder"] = str(
            _resolve(root, overlay["controlled_instrument"]["builder_path"])
        )
        config["_paths"]["controlled_instrument_protocol"] = str(
            _resolve(root, overlay["controlled_instrument"]["protocol_path"])
        )
        config["_paths"]["controlled_instrument_execution_plan"] = str(
            _resolve(root, overlay["controlled_instrument"]["execution_plan_path"])
        )
        config["_paths"]["failed_curated_decisions"] = str(failure_path)
        validate_executable_config(config)
        return config
    if overlay.get("status") != STANDARD_CONFIG_STATUS:
        raise ValueError("measurement-world config is not frozen")
    base_path = _resolve(root, overlay["base_config"]["path"])
    selected_path = _resolve(root, overlay["selected_cells"]["path"])
    if sha256_file(base_path) != overlay["base_config"]["sha256"]:
        raise ValueError("content-addressed scenario proposal changed")
    if sha256_file(selected_path) != overlay["selected_cells"]["sha256"]:
        raise ValueError("content-addressed selected_cells.json changed")
    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    config = copy.deepcopy(base)
    config["design_id"] = overlay["design_id"]
    config["status"] = overlay["status"]
    config["frozen_overlay"] = overlay
    config["_paths"] = {
        "config": str(config_path),
        "base": str(base_path),
        "selected_cells": str(selected_path),
    }
    validate_executable_config(config)
    return config


def validate_executable_config(config: Mapping[str, Any]) -> None:
    if config.get("status") not in {
        STANDARD_CONFIG_STATUS,
        CONTROLLED_CONFIG_STATUS,
    }:
        raise ValueError("config must be frozen before responses")
    if config.get("status") == CONTROLLED_CONFIG_STATUS:
        if (
            config.get("scenario_kind") != "controlled_instrument_scaffold"
            or config.get("release_eligible") is not False
        ):
            raise ValueError("controlled scenario lost its non-release status")
        if config.get("controlled_scenario_overlay", {}).get(
            "adaptive_policy_boundary"
        ) != {
            "policy_design_map": "frozen_oracle_aligned_instrument_kc_q",
            "policy_may_read_declared_item_kc_map": True,
            "policy_may_read_latent_learner_state": False,
            "policy_may_read_planted_nuisance_effects": False,
            "policy_may_read_future_outcomes": False,
            "interpretation": "controlled_favourable_policy_not_real_platform_claim",
        }:
            raise ValueError("controlled adaptive-policy claim boundary changed")
        if config["controlled_scenario_overlay"]["runner_gate"].get(
            "canonical_output_dir"
        ) != "experiments/measurement_realism/worlds/controlled_instrument_v1":
            raise ValueError("controlled output-directory boundary changed")
        expected_claim_boundary = {
            "learner_facing_item_bank": False,
            "measurement_validity_claimed": False,
            "platform_plausibility_claimed": False,
            "format_labels_instantiated_as_tasks": False,
            "response_space_defined": False,
            "permitted_claim": "controlled_structural_sensitivity_only",
            "prohibited_claims": [
                "validated_item_bank",
                "platform_plausible_dataset",
                "realistic_learner_opportunities",
                "release_dataset",
            ],
        }
        if config["controlled_scenario_overlay"].get(
            "claim_boundary"
        ) != expected_claim_boundary:
            raise ValueError("controlled scenario claim boundary changed")
        expected_runner_gate = {
            "explicit_cli_flag": "--controlled-scenario",
            "required_for": ["plan", "validate-plan", "run", "analyze", "aggregate"],
            "canonical_output_dir": "experiments/measurement_realism/worlds/controlled_instrument_v1",
            "production_curated_gate_retained": True,
            "plan_status": "PREREGISTERED_CONTROLLED_SCENARIO_BEFORE_RESPONSES",
            "external_approval_required_before_run": True,
            "external_approval_recorded_in_this_config": False,
        }
        if config["controlled_scenario_overlay"].get(
            "runner_gate"
        ) != expected_runner_gate:
            raise ValueError("controlled runner/approval gate changed")
    formats = tuple(config["bank"]["formats"]["canonical_order"])
    if formats != CANONICAL_FORMATS:
        raise ValueError(f"canonical format order drifted: {formats}")
    worlds = config["worlds"]
    world_ids = [row["world_id"] for row in worlds]
    if len(world_ids) != len(set(world_ids)) or "clean_zero" not in world_ids:
        raise ValueError("world IDs must be unique and include clean_zero")
    if config["simulation"]["aggregation"] != "minimum":
        raise ValueError("confirmatory aggregation must remain minimum")
    if config["simulation"]["learning"]["forgetting"] != "none":
        raise ValueError("confirmatory worlds prohibit forgetting")
    if config["schedule"]["terminal_probe"]["updates_mastery"] is not False:
        raise ValueError("terminal probes must be non-updating")
    if config["models"]["learner_split"]["train_fraction"] + config["models"][
        "learner_split"
    ]["dev_fraction"] + config["models"]["learner_split"]["test_fraction"] != 1.0:
        raise ValueError("learner split fractions must sum exactly to one")
    taxonomy = config["structured_errors"]["taxonomy"]
    if len(taxonomy) != config["bank"]["generator_kcs"]:
        raise ValueError("structured-error taxonomy must cover every KC")


def load_selected_cells(config: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(config["_paths"]["selected_cells"])
    selected = json.loads(path.read_text(encoding="utf-8"))
    if selected.get("selection_schema") != "matched_format_selected_cells_v1":
        raise ValueError("selected-cell schema changed")
    if len(selected["seen_cells"]) != 18 or len(selected["held_out_cells"]) != 2:
        raise ValueError("selected cells must contain 18 seen plus two probes")
    if selected["seen_rank_claim"] != {
        "cell_count": 18,
        "exact_determinant": -1,
        "exact_rank": 18,
        "held_out_cells_excluded": True,
    }:
        raise ValueError("selected seen-cell rank claim changed")
    if any(row["grammar_regime"] != "seen" for row in selected["seen_cells"]):
        raise ValueError("acquisition selection contains a held-out cell")
    if any(row["acquisition_updates"] for row in selected["held_out_cells"]):
        raise ValueError("held-out selected cells must be non-updating")
    return selected


def _exact_rank(rows: Sequence[Sequence[int]]) -> int:
    if not rows:
        return 0
    return int(np.linalg.matrix_rank(np.asarray(rows, dtype=float), tol=1e-10))


def _validate_schema_if_available(
    items: Sequence[Mapping[str, Any]], schema_path: Path | None
) -> None:
    if schema_path is None:
        return
    if not schema_path.is_file():
        raise FileNotFoundError(f"curated bank schema not found: {schema_path}")
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency error is explicit
        raise RuntimeError("jsonschema is required for curated-bank validation") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for index, item in enumerate(items):
        errors = sorted(validator.iter_errors(dict(item)), key=lambda error: list(error.path))
        if errors:
            first = errors[0]
            location = ".".join(str(value) for value in first.path)
            raise ValueError(
                f"curated item {index}/{item.get('item_id')} violates schema at "
                f"{location or '<root>'}: {first.message}"
            )


def validate_curated_bank(
    items: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    schema_path: Path | None = None,
    fixture: bool = False,
) -> dict[str, Any]:
    """Enforce the complete 152-item matched-bank contract."""

    _validate_schema_if_available(items, schema_path)
    expected_total = int(config["bank"]["expected_scale_if_minimum_design_passes"]["total_items"])
    if len(items) != expected_total:
        raise ValueError(f"curated bank needs exactly {expected_total} items")
    required = {
        "item_id",
        "family_id",
        "cell_id",
        "semantic_variant_index",
        "format",
        "grammar_regime",
        "acquisition_updates",
        "generator_kc_ids",
        "q_row",
        "canonical_target_sentence",
        "semantic_frame",
        "validation_status",
    }
    normalized: list[dict[str, Any]] = []
    seen_by_id = {row["cell_id"]: row for row in selected["seen_cells"]}
    held_by_id = {row["cell_id"]: row for row in selected["held_out_cells"]}
    selected_by_id = {**seen_by_id, **held_by_id}
    kc_order = list(selected["kc_order"])
    item_ids: set[str] = set()
    crossing: Counter[tuple[str, str, int]] = Counter()
    family_q: dict[tuple[str, int], tuple[int, ...]] = {}
    family_id_by_key: dict[tuple[str, int], str] = {}
    key_by_family_id: dict[str, tuple[str, int]] = {}
    family_target: dict[tuple[str, int], str] = {}
    family_semantics: dict[tuple[str, int], str] = {}
    family_formats: dict[tuple[str, int], set[str]] = defaultdict(set)
    for index, raw in enumerate(items):
        missing = required - set(raw)
        if missing:
            raise ValueError(f"bank row {index} missing {sorted(missing)}")
        item = dict(raw)
        item_id = item["item_id"]
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise ValueError(f"invalid or duplicate item_id: {item_id!r}")
        item_ids.add(item_id)
        cell_id = item["cell_id"]
        if cell_id not in selected_by_id:
            raise ValueError(f"bank item uses unselected cell: {cell_id}")
        selected_cell = selected_by_id[cell_id]
        regime = item["grammar_regime"]
        if regime != selected_cell["grammar_regime"]:
            raise ValueError(f"grammar regime disagrees for {item_id}")
        updating = item["acquisition_updates"]
        if not isinstance(updating, bool) or updating != (regime == "seen"):
            raise ValueError(f"acquisition_updates disagrees for {item_id}")
        item_format = item["format"]
        if item_format not in CANONICAL_FORMATS:
            raise ValueError(f"unknown format for {item_id}: {item_format}")
        variant = item["semantic_variant_index"]
        if isinstance(variant, bool) or not isinstance(variant, int):
            raise ValueError(f"semantic_variant_index must be integer: {item_id}")
        expected_variants = {1, 2} if regime == "seen" else {1}
        if variant not in expected_variants:
            raise ValueError(f"invalid variant for {regime}: {item_id}")
        active = list(item["generator_kc_ids"])
        row = list(item["q_row"])
        if active != selected_cell["generator_kc_ids"]:
            raise ValueError(f"active KCs disagree with selected cell: {item_id}")
        if row != selected_cell["q_row"] or len(row) != len(kc_order):
            raise ValueError(f"Q row disagrees with selected cell: {item_id}")
        if active != [kc for kc, value in zip(kc_order, row) if value == 1]:
            raise ValueError(f"active KC list/Q row mismatch: {item_id}")
        status = item["validation_status"]
        if fixture:
            if status not in {"fixture_only", "hard_gates_passed"}:
                raise ValueError(f"fixture has invalid validation status: {status}")
        elif status != "hard_gates_passed":
            raise ValueError(f"confirmatory item failed hard gates: {item_id}")
        if not fixture and (
            item_id.startswith("fixture::") or str(item["family_id"]).startswith("fixture::")
        ):
            raise ValueError("fixture-marked content cannot pass the confirmatory gate")
        key = (cell_id, item_format, variant)
        crossing[key] += 1
        family_key = (cell_id, variant)
        family_id = item["family_id"]
        if not isinstance(family_id, str) or not family_id:
            raise ValueError(f"invalid family_id: {item_id}")
        if family_key in family_id_by_key and family_id_by_key[family_key] != family_id:
            raise ValueError(f"matched family changes family_id: {family_key}")
        if family_id in key_by_family_id and key_by_family_id[family_id] != family_key:
            raise ValueError(f"family_id reused across cell/variant keys: {family_id}")
        family_id_by_key[family_key] = family_id
        key_by_family_id[family_id] = family_key
        current_q = tuple(row)
        if family_key in family_q and family_q[family_key] != current_q:
            raise ValueError(f"matched family changes Q: {family_key}")
        family_q[family_key] = current_q
        target = item["canonical_target_sentence"]
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"matched family has empty canonical target: {item_id}")
        semantics = canonical_json(item["semantic_frame"])
        if family_key in family_target and family_target[family_key] != target:
            raise ValueError(f"matched family changes canonical target: {family_key}")
        if family_key in family_semantics and family_semantics[family_key] != semantics:
            raise ValueError(f"matched family changes semantic frame: {family_key}")
        family_target[family_key] = target
        family_semantics[family_key] = semantics
        family_formats[family_key].add(item_format)
        normalized.append(item)

    seen_items = [row for row in normalized if row["grammar_regime"] == "seen"]
    held_items = [row for row in normalized if row["grammar_regime"] != "seen"]
    if len(seen_items) != 144 or len(held_items) != 8:
        raise ValueError("bank must contain 144 seen and eight held-out items")
    expected_crossing = {
        (cell_id, item_format, variant)
        for cell_id in seen_by_id
        for item_format in CANONICAL_FORMATS
        for variant in (1, 2)
    } | {
        (cell_id, item_format, 1)
        for cell_id in held_by_id
        for item_format in CANONICAL_FORMATS
    }
    if set(crossing) != expected_crossing or any(value != 1 for value in crossing.values()):
        missing = sorted(expected_crossing - set(crossing))
        extra = sorted(set(crossing) - expected_crossing)
        raise ValueError(f"bank crossing mismatch: missing={missing}, extra={extra}")
    expected_family_count = 18 * 2 + 2
    if len(family_id_by_key) != expected_family_count:
        raise ValueError(
            f"bank needs exactly {expected_family_count} matched semantic families"
        )
    incomplete_families = {
        family_id_by_key[key]: sorted(set(CANONICAL_FORMATS) - formats)
        for key, formats in family_formats.items()
        if formats != set(CANONICAL_FORMATS)
    }
    if incomplete_families:
        raise ValueError(f"matched families lack formats: {incomplete_families}")
    seen_cell_rows = [seen_by_id[cell_id]["q_row"] for cell_id in sorted(seen_by_id)]
    rank = _exact_rank(seen_cell_rows)
    if rank != 18:
        raise ValueError(f"seen cell-level Q rank is {rank}, not 18")
    per_format = Counter(row["format"] for row in normalized)
    return {
        "items": sorted(normalized, key=lambda row: row["item_id"]),
        "item_count": len(normalized),
        "seen_items": len(seen_items),
        "probe_only_items": len(held_items),
        "seen_cells": len(seen_by_id),
        "seen_cell_q_rank": rank,
        "formats": dict(sorted(per_format.items())),
        "complete_crossing": True,
        "matched_semantic_families": len(family_id_by_key),
        "family_invariants": [
            "cell_id",
            "semantic_variant_index",
            "family_id",
            "q_row",
            "canonical_target_sentence",
            "semantic_frame",
        ],
        "fixture": fixture,
        "semantic_sha256": semantic_hash(sorted(normalized, key=lambda row: row["item_id"])),
    }


def is_controlled_config(config: Mapping[str, Any]) -> bool:
    return config.get("status") == CONTROLLED_CONFIG_STATUS


def controlled_output_dir(config: Mapping[str, Any]) -> Path:
    if not is_controlled_config(config):
        raise ValueError("canonical controlled output requested for production config")
    return _resolve(
        ROOT,
        config["controlled_scenario_overlay"]["runner_gate"][
            "canonical_output_dir"
        ],
    ).resolve()


def require_canonical_controlled_output(
    output_dir: Path, config: Mapping[str, Any]
) -> None:
    if output_dir.resolve() != controlled_output_dir(config):
        raise ValueError(
            "controlled scientific responses require the isolated canonical "
            f"output directory: {controlled_output_dir(config)}"
        )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_plan_output_path(
    output_dir: Path, config: Mapping[str, Any]
) -> None:
    """Protect reference/design trees before a plan writes its first byte.

    External temporary directories remain available for unit tests, but a
    controlled plan anywhere inside the repository must use its isolated
    canonical output directory. Scientific response generation is stricter
    still and always requires that canonical directory.
    """

    resolved = output_dir.resolve()
    protected_subtrees = {
        (ROOT / "data").resolve(),
        (ROOT / "modules").resolve(),
        (ROOT / "experiments/measurement_realism/design").resolve(),
    }
    if resolved == ROOT.resolve() or any(
        resolved == path or _is_within(resolved, path)
        for path in protected_subtrees
    ):
        raise ValueError(f"output directory is inside a protected tree: {resolved}")
    if is_controlled_config(config) and _is_within(resolved, ROOT):
        require_canonical_controlled_output(resolved, config)


def validate_controlled_instrument(
    rows: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    schema_path: Path,
) -> dict[str, Any]:
    """Validate and normalize the content-free structural scaffold.

    Normalization supplies the internal field names used by the simulator. It
    does not add learner-facing content and must never be passed through the
    curated-bank validator.
    """

    if not is_controlled_config(config):
        raise ValueError("controlled instrument requires the controlled config")
    _validate_schema_if_available(rows, schema_path)
    if len(rows) != 152:
        raise ValueError("controlled instrument requires exactly 152 slots")
    selected_by_id = {
        row["cell_id"]: row
        for row in [*selected["seen_cells"], *selected["held_out_cells"]]
    }
    kc_order = list(selected["kc_order"])
    slot_ids: set[str] = set()
    family_key_by_id: dict[str, tuple[str, int]] = {}
    formats_by_family: dict[str, set[str]] = defaultdict(set)
    crossing: Counter[tuple[str, int, str]] = Counter()
    normalized = []
    for index, raw in enumerate(rows):
        row = dict(raw)
        slot_id = row["slot_id"]
        if slot_id in slot_ids:
            raise ValueError(f"duplicate controlled slot: {slot_id}")
        slot_ids.add(slot_id)
        cell_id = row["cell_id"]
        if cell_id not in selected_by_id:
            raise ValueError(f"controlled slot uses unselected cell: {cell_id}")
        cell = selected_by_id[cell_id]
        replicate = int(row["replicate_index"])
        expected_replicates = {1, 2} if cell["grammar_regime"] == "seen" else {1}
        if replicate not in expected_replicates:
            raise ValueError(f"invalid structural replicate: {slot_id}")
        if (
            row["grammar_regime"] != cell["grammar_regime"]
            or row["acquisition_updates"] != (cell["grammar_regime"] == "seen")
            or row["generator_kc_ids"] != cell["generator_kc_ids"]
            or row["q_row"] != cell["q_row"]
        ):
            raise ValueError(f"controlled slot changed selected-cell truth: {slot_id}")
        if row["generator_kc_ids"] != [
            kc for kc, value in zip(kc_order, row["q_row"]) if value
        ]:
            raise ValueError(f"controlled active KCs/Q disagree: {slot_id}")
        if (
            row["instrument_status"] != "STRUCTURAL_PLACEHOLDER_ONLY"
            or row["release_eligible"] is not False
            or row["placeholder_metadata"]["format_is_label_only"] is not True
            or row["placeholder_metadata"]["learner_prompt_present"] is not False
            or row["placeholder_metadata"]["target_answer_present"] is not False
            or row["placeholder_metadata"]["accepted_response_space_present"]
            is not False
            or row["provenance"]["candidate_item_content_used"] is not False
            or row["provenance"]["learner_outcomes_used"] is not False
        ):
            raise ValueError(f"controlled slot crossed the claim boundary: {slot_id}")
        family_id = row["family_id"]
        family_key = (cell_id, replicate)
        if family_id in family_key_by_id and family_key_by_id[family_id] != family_key:
            raise ValueError(f"controlled family ID reused: {family_id}")
        family_key_by_id[family_id] = family_key
        formats_by_family[family_id].add(row["format_label"])
        crossing[(cell_id, replicate, row["format_label"])] += 1
        normalized.append(
            {
                "item_id": slot_id,
                "family_id": family_id,
                "cell_id": cell_id,
                "semantic_variant_index": replicate,
                "format": row["format_label"],
                "grammar_regime": row["grammar_regime"],
                "acquisition_updates": row["acquisition_updates"],
                "generator_kc_ids": list(row["generator_kc_ids"]),
                "q_row": list(row["q_row"]),
                "instrument_status": row["instrument_status"],
                "release_eligible": False,
            }
        )
    if len(family_key_by_id) != 38:
        raise ValueError("controlled instrument requires exactly 38 families")
    if any(formats != set(CANONICAL_FORMATS) for formats in formats_by_family.values()):
        raise ValueError("controlled families do not cross four format labels")
    if len(crossing) != 152 or any(value != 1 for value in crossing.values()):
        raise ValueError("controlled cell/replicate/format crossing is incomplete")
    seen_rows = {
        row["cell_id"]: row["q_row"]
        for row in normalized
        if row["grammar_regime"] == "seen"
    }
    rank = _exact_rank(list(seen_rows.values()))
    if len(seen_rows) != 18 or rank != 18:
        raise ValueError("controlled seen-cell Q does not retain rank 18")
    raw_ordered = sorted((dict(row) for row in rows), key=lambda row: row["slot_id"])
    declared = config["controlled_scenario_overlay"]["controlled_instrument"]
    if semantic_hash(raw_ordered) != declared["semantic_sha256"]:
        raise ValueError("controlled instrument semantic hash changed")
    return {
        "items": sorted(normalized, key=lambda row: row["item_id"]),
        "scenario_kind": "controlled_instrument_scaffold",
        "release_eligible": False,
        "learner_facing_content_present": False,
        "item_count": len(normalized),
        "seen_items": sum(row["grammar_regime"] == "seen" for row in normalized),
        "probe_only_items": sum(
            row["grammar_regime"] != "seen" for row in normalized
        ),
        "families": len(family_key_by_id),
        "seen_cells": len(seen_rows),
        "seen_cell_q_rank": rank,
        "formats": dict(sorted(Counter(row["format"] for row in normalized).items())),
        "complete_crossing": True,
        "raw_semantic_sha256": semantic_hash(raw_ordered),
        "normalized_semantic_sha256": semantic_hash(
            sorted(normalized, key=lambda row: row["item_id"])
        ),
        "claim_boundary": (
            "structural simulator slots only; no learner-facing or platform validity"
        ),
    }


def build_synthetic_bank_fixture(
    selected: Mapping[str, Any], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return a deterministic, visibly non-linguistic contract fixture."""

    rows: list[dict[str, Any]] = []
    for selected_cell in [*selected["seen_cells"], *selected["held_out_cells"]]:
        seen = selected_cell["grammar_regime"] == "seen"
        variants = (1, 2) if seen else (1,)
        for variant in variants:
            family_id = f"fixture::{selected_cell['cell_id']}::v{variant}"
            for item_format in CANONICAL_FORMATS:
                item_id = f"fixture::{selected_cell['cell_id']}::{item_format}::v{variant}"
                rows.append(
                    {
                        "item_id": item_id,
                        "family_id": family_id,
                        "cell_id": selected_cell["cell_id"],
                        "semantic_variant_index": variant,
                        "format": item_format,
                        "response_mode": (
                            "single_choice"
                            if item_format == "multiple_choice"
                            else "full_sentence"
                            if item_format == "sentence_transformation"
                            else "short_text"
                        ),
                        "instruction": "FIXTURE ONLY: do not present to learners.",
                        "context": "",
                        "format_payload": {},
                        "scoring": {
                            "target_response": "FIXTURE",
                            "accepted_responses": ["FIXTURE"],
                            "completed_target": f"FIXTURE TARGET {family_id}",
                            "correct_choice_id": (
                                "A" if item_format == "multiple_choice" else None
                            ),
                        },
                        "canonical_target_sentence": f"FIXTURE TARGET {family_id}",
                        "semantic_frame": {
                            "situation_summary": "Fixture-only situation.",
                            "communicative_goal": "Exercise the data contract.",
                            "participants": ["fixture learner"],
                            "time_anchor": "fixture time",
                            "main_verb_lemma": "test",
                            "object_head": "contract",
                        },
                        "grammar_regime": selected_cell["grammar_regime"],
                        "acquisition_updates": seen,
                        "generator_kc_ids": selected_cell["generator_kc_ids"],
                        "q_row": selected_cell["q_row"],
                        "validation_status": "hard_gates_passed",
                        "provenance": {
                            "protocol_id": "measurement_realism_matched_bank_v0",
                            "source_candidate_id": f"fixture-candidate::{family_id}",
                            "source_candidate_item_id": selected_cell[
                                "reference_item_id"
                            ],
                            "selected_candidate_round": 1,
                            "selection_rule": "earliest_whole_family_passing_all_gates",
                        },
                    }
                )
    return sorted(rows, key=lambda row: row["item_id"])


def keyed_rng(seed: int, namespace: str, *keys: object) -> np.random.Generator:
    payload = canonical_json([int(seed), namespace, *keys]).encode("utf-8")
    words = np.frombuffer(hashlib.sha256(payload).digest(), dtype="<u4").tolist()
    return np.random.default_rng(np.random.SeedSequence(words))


def keyed_uniform(seed: int, namespace: str, *keys: object) -> float:
    return float(keyed_rng(seed, namespace, *keys).random())


def keyed_normal(seed: int, namespace: str, *keys: object) -> float:
    return float(keyed_rng(seed, namespace, *keys).standard_normal())


def keyed_beta(
    seed: int, namespace: str, alpha: float, beta: float, *keys: object
) -> float:
    return float(keyed_rng(seed, namespace, *keys).beta(alpha, beta))


def logistic(value: float | np.ndarray) -> float | np.ndarray:
    values = np.asarray(value, dtype=float)
    output = np.empty_like(values)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    output[~positive] = exponential / (1.0 + exponential)
    return float(output) if output.ndim == 0 else output


def logit(value: float, epsilon: float = 1e-12) -> float:
    clipped = min(1.0 - epsilon, max(epsilon, float(value)))
    return math.log(clipped / (1.0 - clipped))


def bounded_response_probability(
    prerequisite_mastery: float,
    *,
    guess: float,
    slip: float,
    learner_ability: float = 0.0,
    format_offset: float = 0.0,
    item_difficulty: float = 0.0,
    epsilon: float = 1e-12,
) -> float:
    if not 0.0 <= prerequisite_mastery <= 1.0:
        raise ValueError("mastery must lie in [0,1]")
    if guess < 0 or slip < 0 or guess + slip >= 1:
        raise ValueError("guess/slip bounds are invalid")
    offset = learner_ability + format_offset - item_difficulty
    if offset == 0.0:
        # Required exact clean-world equivalence, including ordinary interior values.
        return guess + (1.0 - guess - slip) * prerequisite_mastery
    latent = float(logistic(logit(prerequisite_mastery, epsilon) + offset))
    probability = guess + (1.0 - guess - slip) * latent
    return min(1.0, max(0.0, probability))


def format_scalar_offsets(formats: Sequence[str], scale: float) -> dict[str, float]:
    if tuple(formats) != CANONICAL_FORMATS:
        raise ValueError("format scalar contrast requires canonical order")
    numerators = (-3.0, -1.0, 1.0, 3.0)
    return {
        item_format: float(scale) * numerator / math.sqrt(5.0)
        for item_format, numerator in zip(formats, numerators)
    }


def helmert_contrasts(levels: Sequence[str]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Return deterministic orthonormal, sum-zero contrasts for ordered levels."""

    ordered = list(levels)
    if len(ordered) < 2 or len(ordered) != len(set(ordered)):
        raise ValueError("contrast levels must be at least two unique values")
    matrix = np.zeros((len(ordered), len(ordered) - 1), dtype=float)
    for column in range(len(ordered) - 1):
        denominator = math.sqrt((column + 1) * (column + 2))
        matrix[: column + 1, column] = 1.0 / denominator
        matrix[column + 1, column] = -(column + 1) / denominator
    if not np.allclose(matrix.sum(axis=0), 0.0, atol=1e-12):
        raise AssertionError("Helmert contrasts are not sum-zero")
    if not np.allclose(matrix.T @ matrix, np.eye(len(ordered) - 1), atol=1e-12):
        raise AssertionError("Helmert contrasts are not orthonormal")
    return {level: matrix[index].copy() for index, level in enumerate(ordered)}, matrix


def orthogonalized_item_effects(
    items: Sequence[Mapping[str, Any]],
    kc_order: Sequence[str],
    *,
    seed: int,
    scale: float,
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    """Construct seen-estimable item effects plus probe-only sensitivity effects.

    The 144 seen effects are projected into exactly the same residual subspace
    represented by model D: orthogonal to intercept, format, and Q*.  The eight
    held-out items have no acquisition outcomes from which item coefficients
    could be estimated; they are independently centered/scaled and explicitly
    remain out-of-sample nuisance.  Both groups use keyed raw draws.
    """

    ordered = sorted(items, key=lambda row: row["item_id"])
    seen = [row for row in ordered if row["acquisition_updates"]]
    held = [row for row in ordered if not row["acquisition_updates"]]
    if len(seen) != 144 or len(held) != 8:
        raise ValueError("item-effect construction requires the 144/8 bank contract")
    format_map, _ = helmert_contrasts(CANONICAL_FORMATS)
    raw_by_id = {
        row["item_id"]: keyed_normal(seed, "item_difficulty_z", row["item_id"])
        for row in ordered
    }
    raw_seen = np.asarray(
        [raw_by_id[row["item_id"]] for row in seen],
        dtype=float,
    )
    design = np.asarray(
        [
            [1.0, *format_map[row["format"]], *[float(value) for value in row["q_row"]]]
            for row in seen
        ],
        dtype=float,
    )
    if design.shape[1] != 1 + 3 + len(kc_order):
        raise ValueError("orthogonalization design has wrong width")
    projection = design @ np.linalg.pinv(design)
    residual = raw_seen - projection @ raw_seen
    population_sd = float(np.std(residual, ddof=0))
    if population_sd <= 1e-12:
        raise ValueError("item residual has no variation after orthogonalization")
    standardized = residual / population_sd
    effects_seen = float(scale) * standardized
    tolerance = float(np.max(np.abs(design.T @ standardized)))
    raw_held = np.asarray([raw_by_id[row["item_id"]] for row in held], dtype=float)
    held_sd = float(np.std(raw_held, ddof=0))
    if held_sd <= 1e-12:
        raise ValueError("held-out item draws have no variation")
    standardized_held = (raw_held - np.mean(raw_held)) / held_sd
    effects_held = float(scale) * standardized_held
    effect_by_id = {
        **{row["item_id"]: float(value) for row, value in zip(seen, effects_seen)},
        **{row["item_id"]: float(value) for row, value in zip(held, effects_held)},
    }
    effects_all = np.asarray([effect_by_id[row["item_id"]] for row in ordered])
    diagnostics = {
        "items": len(ordered),
        "seen_estimable_items": len(seen),
        "held_out_probe_only_items": len(held),
        "scope": "seen_residual_subspace_plus_independent_heldout_sensitivity",
        "design_columns": int(design.shape[1]),
        "design_rank": int(np.linalg.matrix_rank(design)),
        "raw_population_sd": float(np.std(list(raw_by_id.values()), ddof=0)),
        "residual_population_sd_before_standardization": population_sd,
        "standardized_mean": float(np.mean(standardized)),
        "standardized_population_sd": float(np.std(standardized, ddof=0)),
        "seen_effect_population_sd": float(np.std(effects_seen, ddof=0)),
        "heldout_effect_population_sd": float(np.std(effects_held, ddof=0)),
        "effect_population_sd": float(np.std(effects_all, ddof=0)),
        "maximum_absolute_design_inner_product": tolerance,
        "orthogonal_within_tolerance": tolerance < 1e-8,
        "heldout_effects_estimable_by_model_d": False,
    }
    if not diagnostics["orthogonal_within_tolerance"]:
        raise AssertionError("item effects are not orthogonal to design")
    return (
        raw_by_id,
        effect_by_id,
        diagnostics,
    )


def world_by_id(config: Mapping[str, Any], world_id: str) -> dict[str, Any]:
    matches = [dict(row) for row in config["worlds"] if row["world_id"] == world_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate world: {world_id}")
    return matches[0]


def build_balanced_multiset(
    items: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen = [row for row in items if row["acquisition_updates"]]
    active = {row["item_id"]: tuple(row["generator_kc_ids"]) for row in seen}
    occurrences, diagnostics = build_acquisition_occurrences(
        [{"item_id": row["item_id"], "cell_id": row["cell_id"]} for row in seen],
        active,
        target_opportunities_per_seen_kc=int(
            config["schedule"]["acquisition_target_opportunities_per_kc"]
        ),
    )
    resolution = config["frozen_overlay"]["execution_clarifications"][
        "acquisition_budget_resolution"
    ]
    selected_expected = int(resolution["selected_18_cell_crossed_bank_value"])
    if len(occurrences) != selected_expected:
        raise ValueError(
            "selected-bank acquisition budget changed: "
            f"expected {selected_expected}, observed {len(occurrences)}"
        )
    diagnostics["proposal_rank_witness_budget_nonbinding"] = int(
        resolution["base_proposal_rank_witness_value"]
    )
    diagnostics["frozen_selected_bank_budget"] = selected_expected
    diagnostics["budget_resolution"] = "selected_cell_q_geometry_replaces_rank_witness"
    return occurrences, diagnostics


def _occurrence_key(occurrence: Mapping[str, Any]) -> tuple[str, int]:
    return (
        str(occurrence["item"]["item_id"]),
        int(occurrence["item_exposure_index"]),
    )


def _item_lookup(items: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["item_id"]): dict(row) for row in items}


def _curriculum_stage(features: Mapping[str, Any]) -> int:
    complexity = sum(
        (
            features.get("aspect") not in {None, "none"},
            features.get("voice") == "passive",
            features.get("polarity") == "negative",
            features.get("clause") in {"polar_question", "non_subject_wh_question"},
        )
    )
    return min(4, 1 + int(complexity))


def order_fixed_occurrences(
    occurrences: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    learner_id: str,
    policy_id: str,
    cell_features_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Order one fixed multiset under lab, curriculum, or mixed practice."""

    if policy_id not in {"q_balanced_lab", "curriculum", "mixed_practice"}:
        raise ValueError(f"not a fixed-multiset policy: {policy_id}")
    item_by_id = _item_lookup(items)
    normalized = [copy.deepcopy(dict(row)) for row in occurrences]
    if policy_id == "q_balanced_lab":
        ordered = sorted(
            normalized,
            key=lambda row: (
                int(row["item_exposure_index"]),
                keyed_uniform(
                    seed,
                    "policy_tie_rank",
                    policy_id,
                    learner_id,
                    int(row["item_exposure_index"]),
                    row["item"]["item_id"],
                ),
                row["item"]["item_id"],
            ),
        )
    elif policy_id == "curriculum":
        if cell_features_by_id is None:
            raise ValueError("curriculum requires frozen GrammarCell features")
        ordered = sorted(
            normalized,
            key=lambda row: (
                _curriculum_stage(
                    cell_features_by_id[
                        item_by_id[row["item"]["item_id"]]["cell_id"]
                    ]
                ),
                int(row["item_exposure_index"]),
                keyed_uniform(
                    seed,
                    "policy_tie_rank",
                    policy_id,
                    learner_id,
                    int(row["item_exposure_index"]),
                    row["item"]["item_id"],
                ),
                row["item"]["item_id"],
            ),
        )
    else:
        remaining = {_occurrence_key(row): row for row in normalized}
        next_exposure: Counter[str] = Counter()
        last_item_step: dict[str, int] = {}
        last_cell_step: dict[str, int] = {}
        previous: dict[str, Any] | None = None
        ordered = []
        while remaining:
            eligible = [
                row
                for (item_id, exposure), row in remaining.items()
                if exposure == next_exposure[item_id] + 1
            ]
            if not eligible:
                raise AssertionError("mixed-practice exposure precedence deadlock")

            def mixed_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
                item = item_by_id[row["item"]["item_id"]]
                if previous is None:
                    repeats_cell = 0
                    repeats_format = 0
                else:
                    previous_item = item_by_id[previous["item"]["item_id"]]
                    repeats_cell = int(item["cell_id"] == previous_item["cell_id"])
                    repeats_format = int(item["format"] == previous_item["format"])
                step = len(ordered) + 1
                cell_gap = step - last_cell_step.get(item["cell_id"], -10**9)
                item_gap = step - last_item_step.get(item["item_id"], -10**9)
                return (
                    repeats_cell,
                    repeats_format,
                    -cell_gap,
                    -item_gap,
                    keyed_uniform(
                        seed,
                        "policy_tie_rank",
                        policy_id,
                        learner_id,
                        step,
                        item["item_id"],
                    ),
                    item["item_id"],
                )

            chosen = min(eligible, key=mixed_key)
            key = _occurrence_key(chosen)
            del remaining[key]
            item = item_by_id[chosen["item"]["item_id"]]
            step = len(ordered) + 1
            last_item_step[item["item_id"]] = step
            last_cell_step[item["cell_id"]] = step
            next_exposure[item["item_id"]] += 1
            ordered.append(chosen)
            previous = chosen
    return [
        {**row, "schedule_step": index, "selection_propensity": None}
        for index, row in enumerate(ordered, start=1)
    ]


@dataclass
class AdaptiveState:
    item_exposures: Counter[str]
    cell_attempts: Counter[str]
    cell_corrects: Counter[str]
    last_item_step: dict[str, int]


POLICY_ITEM_FIELDS = ("item_id", "cell_id", "format", "acquisition_updates")


def _policy_item_views(
    items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project bank rows to the fields the platform policy may observe."""

    return [
        {field: row[field] for field in POLICY_ITEM_FIELDS}
        for row in items
        if row["acquisition_updates"]
    ]


def adaptive_burn_in(
    items: Sequence[Mapping[str, Any]], *, seed: int, learner_id: str
) -> list[dict[str, Any]]:
    seen = _policy_item_views(items)
    by_cell_format: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in seen:
        by_cell_format[(item["cell_id"], item["format"])].append(item)
    if len(by_cell_format) != 72 or any(len(values) != 2 for values in by_cell_format.values()):
        raise ValueError("adaptive burn-in requires 18 cells x 4 formats x 2 variants")
    selected: list[dict[str, Any]] = []
    for key, candidates in sorted(by_cell_format.items()):
        ordered = sorted(candidates, key=lambda row: row["item_id"])
        choice = int(
            keyed_rng(seed, "policy_tie_rank", "adaptive_burn_in", learner_id, *key).integers(0, 2)
        )
        selected.append(ordered[choice])
    selected.sort(
        key=lambda item: (
            keyed_uniform(
                seed,
                "policy_tie_rank",
                "adaptive_weakness",
                learner_id,
                0,
                item["item_id"],
            ),
            item["item_id"],
        )
    )
    return selected


def adaptive_select_item(
    items: Sequence[Mapping[str, Any]],
    state: AdaptiveState,
    *,
    seed: int,
    learner_id: str,
    acquisition_step: int,
    exploration_probability: float = 0.20,
    cooldown: int = 8,
) -> tuple[dict[str, Any], float, dict[str, Any]]:
    """Select from observable history only and return the exact marginal propensity."""

    for value in vars(state).values():
        if isinstance(value, Mapping) and FORBIDDEN_POLICY_FIELDS & set(value):
            raise ValueError("adaptive policy state contains forbidden oracle fields")
    seen = _policy_item_views(items)
    eligible = [
        item
        for item in seen
        if acquisition_step - state.last_item_step.get(item["item_id"], -10**9) > cooldown
    ]
    if not eligible:
        eligible = seen
    # Cell IDs are frozen platform opportunity metadata. Generator K*/Q* are
    # intentionally not read by the selection policy.
    all_cells = sorted({str(item["cell_id"]) for item in seen})
    rates = {
        cell: (1 + state.cell_corrects[cell]) / (2 + state.cell_attempts[cell])
        for cell in all_cells
    }
    weakest = min(all_cells, key=lambda cell: (rates[cell], cell))
    focused = [item for item in eligible if item["cell_id"] == weakest]
    if not focused:
        focused = eligible

    def exploit_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
        gap = acquisition_step - state.last_item_step.get(item["item_id"], -10**9)
        return (
            state.item_exposures[item["item_id"]],
            -gap,
            keyed_uniform(
                seed,
                "policy_tie_rank",
                "adaptive_weakness",
                learner_id,
                acquisition_step,
                item["item_id"],
            ),
            item["item_id"],
        )

    exploit = min(focused, key=exploit_key)
    rng = keyed_rng(seed, "policy_exploration", learner_id, acquisition_step)
    exploration_draw = float(rng.random())
    exploring = exploration_draw < exploration_probability
    exploration_choice_index = None
    if exploring:
        ordered_eligible = sorted(eligible, key=lambda row: row["item_id"])
        exploration_choice_index = int(rng.integers(0, len(ordered_eligible)))
        chosen = ordered_eligible[exploration_choice_index]
    else:
        chosen = exploit
    propensity = exploration_probability / len(eligible)
    if chosen["item_id"] == exploit["item_id"]:
        propensity += 1.0 - exploration_probability
    all_propensities = {
        item["item_id"]: exploration_probability / len(eligible)
        + ((1.0 - exploration_probability) if item["item_id"] == exploit["item_id"] else 0.0)
        for item in eligible
    }
    if not math.isclose(sum(all_propensities.values()), 1.0, abs_tol=1e-12):
        raise AssertionError("adaptive propensities do not sum to one")
    audit = {
        "eligible_item_ids": sorted(all_propensities),
        "eligible_count": len(eligible),
        "weakest_observable_cell": weakest,
        "weakness_estimates": rates,
        "exploit_item_id": exploit["item_id"],
        "exploration_branch": exploring,
        "exploration_draw": exploration_draw,
        "exploration_choice_index": exploration_choice_index,
        "chosen_propensity": propensity,
        "propensity_sum": sum(all_propensities.values()),
    }
    return chosen, propensity, audit


def _learner_latents(
    learner_ids: Sequence[str], kc_order: Sequence[str], config: Mapping[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, str]]:
    sim = config["simulation"]
    initial = {
        learner_id: {
            kc: keyed_beta(
                seed,
                "initial_mastery",
                float(sim["initial_mastery"]["alpha"]),
                float(sim["initial_mastery"]["beta"]),
                learner_id,
                kc,
            )
            for kc in kc_order
        }
        for learner_id in learner_ids
    }
    raw_ability = np.asarray(
        [keyed_normal(seed, "learner_ability_z", learner_id) for learner_id in learner_ids]
    )
    standardized_ability = (raw_ability - np.mean(raw_ability)) / np.std(
        raw_ability, ddof=0
    )
    learning = sim["learning"]["heterogeneous_rate"]
    raw_learning = {
        learner_id: keyed_beta(
            seed,
            "learner_learning_rate",
            float(learning["alpha"]),
            float(learning["beta"]),
            learner_id,
        )
        for learner_id in learner_ids
    }
    noise = sim["heterogeneous_noise"]
    raw_guess = {
        learner_id: keyed_beta(
            seed,
            "learner_guess",
            float(noise["guess"]["alpha"]),
            float(noise["guess"]["beta"]),
            learner_id,
        )
        for learner_id in learner_ids
    }
    raw_slip = {
        learner_id: keyed_beta(
            seed,
            "learner_slip",
            float(noise["slip"]["alpha"]),
            float(noise["slip"]["beta"]),
            learner_id,
        )
        for learner_id in learner_ids
    }
    latents = {
        "initial_mastery": initial,
        "ability_raw_z": dict(zip(learner_ids, raw_ability.tolist())),
        "ability_z": dict(zip(learner_ids, standardized_ability.tolist())),
        "learning_rate": raw_learning,
        "guess_beta": raw_guess,
        "slip_beta": raw_slip,
    }
    hashes = {
        key: semantic_hash([value]) for key, value in latents.items()
    }
    return latents, hashes


def _scaled_beta_draw(raw: float, declaration: Mapping[str, Any]) -> float:
    return float(declaration["lower"]) + (
        float(declaration["upper"]) - float(declaration["lower"])
    ) * float(raw)


def _failed_kc(
    active: Sequence[str], mastery: Mapping[str, float], *, seed: int, learner_id: str, phase: str, sequence: int
) -> tuple[str, float, dict[str, float]]:
    deficits = np.asarray([1.0 - mastery[kc] for kc in active], dtype=float)
    if float(deficits.sum()) <= 0.0:
        probabilities = np.full(len(active), 1.0 / len(active))
    else:
        probabilities = deficits / deficits.sum()
    draw = keyed_uniform(seed, "failed_kc_draw", learner_id, phase, sequence)
    index = int(np.searchsorted(np.cumsum(probabilities), draw, side="right"))
    index = min(index, len(active) - 1)
    return active[index], draw, dict(zip(active, probabilities.tolist()))


def _session_index(sequence: int, acquisition_budget: int, phase: str) -> int:
    if phase == "probe":
        return 10
    return min(10, 1 + ((sequence - 1) * 10 // acquisition_budget))


def simulate_world(
    items: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    world_id: str,
    seed: int,
    policy_id: str = "q_balanced_lab",
    learner_count: int | None = None,
) -> dict[str, Any]:
    """Simulate one world/policy into disjoint observable and oracle streams."""

    world = world_by_id(config, world_id)
    if policy_id != "q_balanced_lab" and world_id != "combined_heterogeneous":
        raise ValueError("policy alternatives are preregistered only for combined_heterogeneous")
    configured_learners = int(config["simulation"]["learners_per_seed"])
    count = configured_learners if learner_count is None else int(learner_count)
    if count < 2 or count > configured_learners:
        raise ValueError("learner_count must be between 2 and configured learners")
    learner_ids = [f"learner_{index:04d}" for index in range(1, count + 1)]
    kc_order = list(selected["kc_order"])
    item_by_id = _item_lookup(items)
    occurrences, schedule_diagnostics = build_balanced_multiset(items, config)
    budget = len(occurrences)
    raw_item, item_effects, item_diagnostics = orthogonalized_item_effects(
        items, kc_order, seed=seed, scale=float(world["item_logit_sd"])
    )
    format_effects = format_scalar_offsets(
        CANONICAL_FORMATS, float(world["format_logit_sd"])
    )
    latents, crn_hashes = _learner_latents(learner_ids, kc_order, config, seed)
    crn_hashes["item_difficulty_z"] = semantic_hash([raw_item])
    crn_hashes["acquisition_response"] = semantic_hash(
        [
            [
                keyed_uniform(seed, "acquisition_response", learner_id, step)
                for step in range(1, budget + 1)
            ]
            for learner_id in learner_ids
        ]
    )
    crn_hashes["probe_response"] = semantic_hash(
        [
            [
                keyed_uniform(seed, "probe_response", learner_id, 1, item["item_id"])
                for item in sorted(items, key=lambda row: row["item_id"])
            ]
            for learner_id in learner_ids
        ]
    )
    crn_hashes["failed_kc_draw"] = semantic_hash(
        [
            [
                *[
                    keyed_uniform(
                        seed, "failed_kc_draw", learner_id, "acquisition", step
                    )
                    for step in range(1, budget + 1)
                ],
                *[
                    keyed_uniform(
                        seed,
                        "failed_kc_draw",
                        learner_id,
                        "probe",
                        budget + probe_offset,
                    )
                    for probe_offset in range(1, len(items) + 1)
                ],
            ]
            for learner_id in learner_ids
        ]
    )
    split_seed = int(
        config["common_random_numbers"]["namespaces"]["model_split"][0]
    )
    crn_hashes["model_split"] = semantic_hash(
        [
            {
                learner_id: keyed_uniform(split_seed, "model_split", learner_id)
                for learner_id in learner_ids
            }
        ]
    )
    crn_hashes["policy_exploration"] = semantic_hash(
        [
            [
                keyed_uniform(seed, "policy_exploration", learner_id, step)
                for step in range(1, budget + 1)
            ]
            for learner_id in learner_ids
        ]
    )
    crn_hashes["policy_tie_rank_keyspace"] = semantic_hash(
        [
            {
                "seed": seed,
                "namespace": "policy_tie_rank",
                "learner_ids": learner_ids,
                "item_ids": sorted(item_by_id),
                "acquisition_budget": budget,
            }
        ]
    )

    sim = config["simulation"]
    taxonomy = config["structured_errors"]["taxonomy"]
    observable: list[dict[str, Any]] = []
    oracle: list[dict[str, Any]] = []
    terminal_mastery: dict[str, dict[str, float]] = {}
    for learner_id in learner_ids:
        mastery = dict(latents["initial_mastery"][learner_id])
        ability = float(world["learner_ability_logit_sd"]) * float(
            latents["ability_z"][learner_id]
        )
        if float(world["learning_rate_cv"]) == 0.0:
            learning_rate = float(sim["learning"]["homogeneous_rate"])
        else:
            learning_rate = float(latents["learning_rate"][learner_id])
        if bool(world["learner_guess_slip_heterogeneous"]):
            guess = _scaled_beta_draw(
                latents["guess_beta"][learner_id], sim["heterogeneous_noise"]["guess"]
            )
            slip = _scaled_beta_draw(
                latents["slip_beta"][learner_id], sim["heterogeneous_noise"]["slip"]
            )
        else:
            guess = float(sim["homogeneous_noise"]["guess"])
            slip = float(sim["homogeneous_noise"]["slip"])

        adaptive_state = AdaptiveState(
            item_exposures=Counter(),
            cell_attempts=Counter(),
            cell_corrects=Counter(),
            last_item_step={},
        )
        if policy_id == "adaptive_weakness":
            burn_in = adaptive_burn_in(items, seed=seed, learner_id=learner_id)
            fixed_schedule: list[dict[str, Any]] | None = None
        else:
            burn_in = []
            fixed_schedule = order_fixed_occurrences(
                occurrences,
                items,
                seed=seed,
                learner_id=learner_id,
                policy_id=policy_id,
                cell_features_by_id={
                    row["cell_id"]: row["features"]
                    for row in selected["seen_cells"]
                },
            )

        for step in range(1, budget + 1):
            policy_audit: dict[str, Any] | None = None
            if policy_id == "adaptive_weakness":
                if step <= len(burn_in):
                    policy_item = burn_in[step - 1]
                    item = item_by_id[policy_item["item_id"]]
                    remaining_cell_format_groups = len(burn_in) - step + 1
                    # Burn-in is a random permutation of the 72 groups and a
                    # uniform choice between the two variants in each group.
                    # Conditional on prior burn-in history, each still-valid
                    # item therefore has this exact marginal propensity.
                    propensity = 1.0 / (2.0 * remaining_cell_format_groups)
                    remaining_groups = {
                        (row["cell_id"], row["format"])
                        for row in burn_in[step - 1 :]
                    }
                    burn_in_eligible_ids = sorted(
                        row["item_id"]
                        for row in items
                        if row["acquisition_updates"]
                        and (row["cell_id"], row["format"]) in remaining_groups
                    )
                    policy_audit = {
                        "burn_in": True,
                        "eligible_item_ids": burn_in_eligible_ids,
                        "eligible_count": 2 * remaining_cell_format_groups,
                        "chosen_propensity": propensity,
                        "propensity_sum": 1.0,
                        "propensity_interpretation": (
                            "marginal_over_random_group_order_and_variant_choice"
                        ),
                    }
                else:
                    policy_item, propensity, policy_audit = adaptive_select_item(
                        items,
                        adaptive_state,
                        seed=seed,
                        learner_id=learner_id,
                        acquisition_step=step,
                        exploration_probability=float(
                            next(
                                row
                                for row in config["schedule"]["policies"]
                                if row["policy_id"] == "adaptive_weakness"
                            )["exploration_probability"]
                        ),
                        cooldown=int(
                            next(
                                row
                                for row in config["schedule"]["policies"]
                                if row["policy_id"] == "adaptive_weakness"
                            )["same_item_cooldown_events"]
                        ),
                    )
                    item = item_by_id[policy_item["item_id"]]
            else:
                assert fixed_schedule is not None
                schedule_row = fixed_schedule[step - 1]
                item = item_by_id[schedule_row["item"]["item_id"]]
                propensity = None

            active = list(item["generator_kc_ids"])
            before = {kc: mastery[kc] for kc in active}
            prerequisite = min(before.values())
            probability = bounded_response_probability(
                prerequisite,
                guess=guess,
                slip=slip,
                learner_ability=ability,
                format_offset=format_effects[item["format"]],
                item_difficulty=item_effects[item["item_id"]],
                epsilon=float(sim["response_link"]["epsilon"]),
            )
            response_draw = keyed_uniform(
                seed, "acquisition_response", learner_id, step
            )
            correct = int(response_draw < probability)
            failed_kc = None
            failed_draw = None
            failed_probabilities = None
            linked_category = None
            if not correct:
                failed_kc, failed_draw, failed_probabilities = _failed_kc(
                    active,
                    mastery,
                    seed=seed,
                    learner_id=learner_id,
                    phase="acquisition",
                    sequence=step,
                )
                linked_category = taxonomy[failed_kc]
            for kc in active:
                mastery[kc] += learning_rate * (1.0 - mastery[kc])
            after = {kc: mastery[kc] for kc in active}
            observable.append(
                {
                    "learner_id": learner_id,
                    "item_id": item["item_id"],
                    "sequence_index": step,
                    "session_index": _session_index(step, budget, "acquisition"),
                    "phase": "acquisition",
                    "correct": correct,
                    "format": item["format"],
                    "policy_id": policy_id,
                    "selection_propensity": propensity,
                    "grammar_regime": item["grammar_regime"],
                    # Primary response-world export is binary-only. Structured
                    # observable variants are derived later from the private
                    # linked category under explicit positive/noisy controls.
                    "error_category": None,
                }
            )
            oracle.append(
                {
                    "learner_id": learner_id,
                    "item_id": item["item_id"],
                    "sequence_index": step,
                    "phase": "acquisition",
                    "active_generator_kcs": active,
                    "mastery_before": before,
                    "mastery_after": after,
                    "aggregated_mastery_before": prerequisite,
                    "item_effect": item_effects[item["item_id"]],
                    "format_effect": format_effects[item["format"]],
                    "learner_ability": ability,
                    "learner_learning_rate": learning_rate,
                    "learner_guess": guess,
                    "learner_slip": slip,
                    "response_probability": probability,
                    "response_draw": response_draw,
                    "failed_kc": failed_kc,
                    "failed_kc_draw": failed_draw,
                    "failed_kc_semantics": (
                        "post_outcome_deficit_proportional_attribution_not_causal"
                        if failed_kc is not None
                        else None
                    ),
                    "failed_kc_probabilities": failed_probabilities,
                    "linked_error_category": linked_category,
                    "policy_eligibility_audit": policy_audit,
                }
            )
            adaptive_state.item_exposures[item["item_id"]] += 1
            adaptive_state.last_item_step[item["item_id"]] = step
            adaptive_state.cell_attempts[item["cell_id"]] += 1
            adaptive_state.cell_corrects[item["cell_id"]] += correct

        terminal_mastery[learner_id] = dict(mastery)
        for probe_offset, item in enumerate(
            sorted(items, key=lambda row: row["item_id"]), start=1
        ):
            sequence = budget + probe_offset
            active = list(item["generator_kc_ids"])
            before = {kc: mastery[kc] for kc in active}
            prerequisite = min(before.values())
            probability = bounded_response_probability(
                prerequisite,
                guess=guess,
                slip=slip,
                learner_ability=ability,
                format_offset=format_effects[item["format"]],
                item_difficulty=item_effects[item["item_id"]],
                epsilon=float(sim["response_link"]["epsilon"]),
            )
            response_draw = keyed_uniform(
                seed, "probe_response", learner_id, 1, item["item_id"]
            )
            correct = int(response_draw < probability)
            failed_kc = None
            failed_draw = None
            failed_probabilities = None
            linked_category = None
            if not correct:
                failed_kc, failed_draw, failed_probabilities = _failed_kc(
                    active,
                    mastery,
                    seed=seed,
                    learner_id=learner_id,
                    phase="probe",
                    sequence=sequence,
                )
                linked_category = taxonomy[failed_kc]
            observable.append(
                {
                    "learner_id": learner_id,
                    "item_id": item["item_id"],
                    "sequence_index": sequence,
                    "session_index": 10,
                    "phase": "probe",
                    "correct": correct,
                    "format": item["format"],
                    "policy_id": policy_id,
                    "selection_propensity": None,
                    "grammar_regime": item["grammar_regime"],
                    "error_category": None,
                }
            )
            oracle.append(
                {
                    "learner_id": learner_id,
                    "item_id": item["item_id"],
                    "sequence_index": sequence,
                    "phase": "probe",
                    "active_generator_kcs": active,
                    "mastery_before": before,
                    "mastery_after": before,
                    "aggregated_mastery_before": prerequisite,
                    "item_effect": item_effects[item["item_id"]],
                    "format_effect": format_effects[item["format"]],
                    "learner_ability": ability,
                    "learner_learning_rate": learning_rate,
                    "learner_guess": guess,
                    "learner_slip": slip,
                    "response_probability": probability,
                    "response_draw": response_draw,
                    "failed_kc": failed_kc,
                    "failed_kc_draw": failed_draw,
                    "failed_kc_semantics": (
                        "post_outcome_deficit_proportional_attribution_not_causal"
                        if failed_kc is not None
                        else None
                    ),
                    "failed_kc_probabilities": failed_probabilities,
                    "linked_error_category": linked_category,
                    "policy_eligibility_audit": None,
                }
            )

    validate_stream_separation(observable, oracle)
    schedule_assignment_hash = semantic_hash(
        [
            {
                "learner_id": row["learner_id"],
                "sequence_index": row["sequence_index"],
                "item_id": row["item_id"],
                "selection_propensity": row["selection_propensity"],
            }
            for row in observable
            if row["phase"] == "acquisition"
        ]
    )
    policy_randomness_hash = semantic_hash(
        [
            {
                "learner_id": row["learner_id"],
                "sequence_index": row["sequence_index"],
                "exploration_draw": (
                    row["policy_eligibility_audit"].get("exploration_draw")
                    if row["policy_eligibility_audit"]
                    else None
                ),
                "exploration_choice_index": (
                    row["policy_eligibility_audit"].get("exploration_choice_index")
                    if row["policy_eligibility_audit"]
                    else None
                ),
            }
            for row in oracle
            if row["phase"] == "acquisition"
        ]
    )
    return {
        "observable": observable,
        "oracle": oracle,
        "terminal_mastery": terminal_mastery,
        "manifest": {
            "world_id": world_id,
            "policy_id": policy_id,
            "seed": seed,
            "learners": count,
            "acquisition_budget": budget,
            "events": len(observable),
            "common_random_hashes": crn_hashes,
            "item_effect_diagnostics": item_diagnostics,
            "format_effects": format_effects,
            "schedule_diagnostics": schedule_diagnostics,
            "schedule_assignment_semantic_sha256": schedule_assignment_hash,
            "policy_randomness_semantic_sha256": policy_randomness_hash,
            "observable_semantic_sha256": semantic_hash(observable),
            "oracle_semantic_sha256": semantic_hash(oracle),
        },
    }


def validate_stream_separation(
    observable: Sequence[Mapping[str, Any]], oracle: Sequence[Mapping[str, Any]]
) -> None:
    if len(observable) != len(oracle):
        raise ValueError("observable/oracle streams do not pair")
    oracle_forbidden = set(ORACLE_ONLY_FIELDS) | {
        "failed_kc_probabilities",
        "linked_error_category",
    }
    keys: set[tuple[str, int]] = set()
    for public, private in zip(observable, oracle):
        if set(public) != set(OBSERVABLE_FIELDS):
            raise ValueError(
                f"observable schema drift: missing={sorted(set(OBSERVABLE_FIELDS)-set(public))}, "
                f"extra={sorted(set(public)-set(OBSERVABLE_FIELDS))}"
            )
        leaked = set(public) & oracle_forbidden
        if leaked:
            raise ValueError(f"oracle fields leaked into observable stream: {sorted(leaked)}")
        key = (str(public["learner_id"]), int(public["sequence_index"]))
        if key in keys:
            raise ValueError(f"duplicate observable event key: {key}")
        keys.add(key)
        if key != (str(private["learner_id"]), int(private["sequence_index"])):
            raise ValueError("observable/oracle event keys do not align")
        if public["item_id"] != private["item_id"] or public["phase"] != private["phase"]:
            raise ValueError("observable/oracle event metadata does not align")


def make_error_streams(
    observable: Sequence[Mapping[str, Any]],
    oracle: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Create binary, linked, 80%-linked, and within-item shuffled controls."""

    validate_stream_separation(observable, oracle)
    streams = {
        "binary_only": [dict(row, error_category=None) for row in observable],
        "linked_positive_control": [],
        "linked_80_percent": [],
        "within_item_shuffled_negative_control": [],
    }
    linked: list[dict[str, Any]] = []
    noisy: list[dict[str, Any]] = []
    observation_draw_audit = []
    for public, private in zip(observable, oracle):
        category = private["linked_error_category"] if not public["correct"] else None
        linked.append(dict(public, error_category=category))
        if category is None:
            observed_category = None
        elif keyed_uniform(
            seed,
            "error_observation",
            public["learner_id"],
            public["phase"],
            public["sequence_index"],
        ) < 0.80:
            observed_category = category
        else:
            observed_category = "non_target_or_unresolved"
        noisy.append(dict(public, error_category=observed_category))
        if category is not None:
            observation_draw_audit.append(
                {
                    "learner_id": public["learner_id"],
                    "phase": public["phase"],
                    "sequence_index": public["sequence_index"],
                    "draw": keyed_uniform(
                        seed,
                        "error_observation",
                        public["learner_id"],
                        public["phase"],
                        public["sequence_index"],
                    ),
                }
            )
    streams["linked_positive_control"] = linked
    streams["linked_80_percent"] = noisy

    shuffled = [dict(row) for row in linked]
    blocks: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(linked):
        if not row["correct"]:
            blocks[(row["item_id"], row["phase"])].append(index)
    singleton_blocks = 0
    unchanged_blocks = 0
    shuffle_permutation_audit = []
    for (item_id, phase), indices in sorted(blocks.items()):
        labels = [linked[index]["error_category"] for index in indices]
        if len(indices) == 1:
            singleton_blocks += 1
            continue
        permutation = keyed_rng(seed, "error_shuffle", item_id, phase).permutation(
            len(indices)
        )
        shuffle_permutation_audit.append(
            {
                "item_id": item_id,
                "phase": phase,
                "block_size": len(indices),
                "permutation": permutation.tolist(),
            }
        )
        permuted = [labels[int(position)] for position in permutation]
        if permuted == labels:
            unchanged_blocks += 1
        for index, category in zip(indices, permuted):
            shuffled[index]["error_category"] = category
        if Counter(labels) != Counter(permuted):
            raise AssertionError("error shuffle changed block marginals")
    streams["within_item_shuffled_negative_control"] = shuffled
    base_non_error = [
        {key: value for key, value in row.items() if key != "error_category"}
        for row in streams["binary_only"]
    ]
    for stream_id, rows in streams.items():
        if [
            {key: value for key, value in row.items() if key != "error_category"}
            for row in rows
        ] != base_non_error:
            raise AssertionError(f"error stream {stream_id} changed a non-error field")
    return streams, {
        "incorrect_events": sum(not row["correct"] for row in observable),
        "shuffle_blocks": len(blocks),
        "singleton_shuffle_blocks": singleton_blocks,
        "non_singleton_unchanged_permutations": unchanged_blocks,
        "common_random_hashes": {
            "error_observation": semantic_hash(observation_draw_audit),
            "error_shuffle": semantic_hash(shuffle_permutation_audit),
        },
        "stream_hashes": {key: semantic_hash(value) for key, value in streams.items()},
    }


def _numeric_summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {key: None for key in ("min", "q05", "q25", "median", "mean", "q75", "q95", "max", "population_sd")}
    array = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(array)),
        "q05": float(np.quantile(array, 0.05)),
        "q25": float(np.quantile(array, 0.25)),
        "median": float(np.quantile(array, 0.50)),
        "mean": float(np.mean(array)),
        "q75": float(np.quantile(array, 0.75)),
        "q95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
        "population_sd": float(np.std(array, ddof=0)),
    }


def _gini(values: Sequence[float]) -> float | None:
    if not values:
        return None
    array = np.sort(np.asarray(values, dtype=float))
    if np.sum(array) == 0:
        return 0.0
    count = len(array)
    return float((2 * np.sum(np.arange(1, count + 1) * array) / (count * np.sum(array))) - (count + 1) / count)


def observable_distribution_diagnostics(
    events: Sequence[Mapping[str, Any]], items: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Compute distribution warnings without reading any learner-state oracle.

    Accuracy, item exposure, format, spacing, and propensity summaries use the
    observable stream.  KC exposure and per-history Q rank additionally use
    the frozen *design* annotations from the bank; this distinction is made
    explicit in the returned provenance block.
    """

    item_by_id = _item_lookup(items)
    learner_correct: dict[str, list[int]] = defaultdict(list)
    item_correct: dict[str, list[int]] = defaultdict(list)
    format_correct: dict[str, list[int]] = defaultdict(list)
    phase_correct: dict[str, list[int]] = defaultdict(list)
    seen_items = sorted(
        str(row["item_id"]) for row in items if row["acquisition_updates"]
    )
    all_kcs = sorted(
        {kc for row in items if row["acquisition_updates"] for kc in row["generator_kc_ids"]}
    )
    # Explicit zeros matter under adaptive assignment: omitting never-selected
    # items would make the exposure tail look artificially healthy.
    kc_exposure: Counter[str] = Counter({kc: 0 for kc in all_kcs})
    item_exposure: Counter[str] = Counter({item_id: 0 for item_id in seen_items})
    lag_pairs: list[tuple[int, int]] = []
    by_learner_ordered: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    propensities: list[float] = []
    for row in events:
        learner = str(row["learner_id"])
        correct = int(row["correct"])
        learner_correct[learner].append(correct)
        item_correct[str(row["item_id"])].append(correct)
        format_correct[str(row["format"])].append(correct)
        phase_correct[str(row["phase"])].append(correct)
        by_learner_ordered[learner].append(row)
        if row["phase"] == "acquisition":
            item_exposure[str(row["item_id"])] += 1
            kc_exposure.update(item_by_id[str(row["item_id"])]["generator_kc_ids"])
        if row["selection_propensity"] is not None:
            propensities.append(float(row["selection_propensity"]))
    session_accuracy: dict[int, list[int]] = defaultdict(list)
    repetition_gaps: list[int] = []
    cell_repetition_gaps: list[int] = []
    adjacent_q_jaccards: list[float] = []
    format_run_lengths: list[int] = []
    learner_unique_items: list[int] = []
    learner_unique_cells: list[int] = []
    learner_unique_q_rows: list[int] = []
    learner_q_ranks: list[int] = []
    for rows in by_learner_ordered.values():
        ordered = sorted(rows, key=lambda row: int(row["sequence_index"]))
        last_item: dict[str, int] = {}
        last_cell: dict[str, int] = {}
        acquisition_correct = []
        acquisition_rows = [row for row in ordered if row["phase"] == "acquisition"]
        q_rows: list[tuple[int, ...]] = []
        prior_q: set[str] | None = None
        prior_format: str | None = None
        current_format_run = 0
        for row in acquisition_rows:
            acquisition_correct.append(int(row["correct"]))
            session_accuracy[int(row["session_index"])].append(int(row["correct"]))
            item = item_by_id[str(row["item_id"])]
            item_id = str(item["item_id"])
            cell_id = str(item["cell_id"])
            sequence = int(row["sequence_index"])
            if item_id in last_item:
                repetition_gaps.append(sequence - last_item[item_id])
            if cell_id in last_cell:
                cell_repetition_gaps.append(sequence - last_cell[cell_id])
            last_item[item_id] = sequence
            last_cell[cell_id] = sequence
            q_tuple = tuple(int(value) for value in item["q_row"])
            q_rows.append(q_tuple)
            current_q = {str(index) for index, value in enumerate(q_tuple) if value}
            if prior_q is not None:
                adjacent_q_jaccards.append(
                    len(current_q & prior_q) / len(current_q | prior_q)
                )
            prior_q = current_q
            item_format = str(item["format"])
            if item_format == prior_format:
                current_format_run += 1
            else:
                if current_format_run:
                    format_run_lengths.append(current_format_run)
                current_format_run = 1
                prior_format = item_format
        if current_format_run:
            format_run_lengths.append(current_format_run)
        learner_unique_items.append(len({str(row["item_id"]) for row in acquisition_rows}))
        learner_unique_cells.append(
            len({str(item_by_id[str(row["item_id"])]["cell_id"]) for row in acquisition_rows})
        )
        learner_unique_q_rows.append(len(set(q_rows)))
        learner_q_ranks.append(_exact_rank(q_rows))
        lag_pairs.extend(zip(acquisition_correct[:-1], acquisition_correct[1:]))
    if lag_pairs and np.std(np.asarray(lag_pairs)[:, 0]) > 0 and np.std(np.asarray(lag_pairs)[:, 1]) > 0:
        lag_one = float(np.corrcoef(np.asarray(lag_pairs).T)[0, 1])
    else:
        lag_one = None
    error_counts = Counter(
        str(row["error_category"])
        for row in events
        if row["error_category"] is not None
    )
    return {
        "rows": len(events),
        "learners": len(learner_correct),
        "overall_accuracy": float(np.mean([row["correct"] for row in events])),
        "learner_accuracy": _numeric_summary([fmean(values) for values in learner_correct.values()]),
        "item_accuracy": _numeric_summary([fmean(values) for values in item_correct.values()]),
        "format_accuracy": {
            key: {"attempts": len(values), "accuracy": fmean(values)}
            for key, values in sorted(format_correct.items())
        },
        "phase_accuracy": {
            key: {"attempts": len(values), "accuracy": fmean(values)}
            for key, values in sorted(phase_correct.items())
        },
        "session_accuracy": {
            str(key): {"attempts": len(values), "accuracy": fmean(values)}
            for key, values in sorted(session_accuracy.items())
        },
        "lag_one_correctness_correlation": lag_one,
        "acquisition_item_exposure": {
            "counts": dict(sorted(item_exposure.items())),
            "zero_exposure_items": sum(value == 0 for value in item_exposure.values()),
            "summary": _numeric_summary(list(item_exposure.values())),
            "cv": (
                pstdev(item_exposure.values()) / fmean(item_exposure.values())
                if item_exposure and fmean(item_exposure.values())
                else None
            ),
            "gini": _gini(list(item_exposure.values())),
        },
        "acquisition_kc_exposure": {
            "counts": dict(sorted(kc_exposure.items())),
            "summary": _numeric_summary(list(kc_exposure.values())),
            "cv": pstdev(kc_exposure.values()) / fmean(kc_exposure.values()),
            "gini": _gini(list(kc_exposure.values())),
        },
        "acquisition_history_coverage_per_learner": {
            "unique_items": _numeric_summary(learner_unique_items),
            "unique_cells": _numeric_summary(learner_unique_cells),
            "unique_q_rows": _numeric_summary(learner_unique_q_rows),
            "q_rank": _numeric_summary(learner_q_ranks),
        },
        "repetition_gap": _numeric_summary(repetition_gaps),
        "cell_repetition_gap": _numeric_summary(cell_repetition_gaps),
        "adjacent_q_jaccard": _numeric_summary(adjacent_q_jaccards),
        "format_run_length": _numeric_summary(format_run_lengths),
        "selection_propensity": _numeric_summary(propensities),
        "error_categories": dict(sorted(error_counts.items())),
        "provenance_scope": {
            "observable_stream_fields_used": sorted(
                {
                    "learner_id",
                    "item_id",
                    "sequence_index",
                    "session_index",
                    "phase",
                    "correct",
                    "format",
                    "selection_propensity",
                    "error_category",
                }
            ),
            "frozen_bank_design_fields_used": [
                "item_id",
                "cell_id",
                "format",
                "acquisition_updates",
                "generator_kc_ids",
                "q_row",
            ],
            "learner_oracle_fields_used": [],
            "design_linked_sections": [
                "acquisition_kc_exposure",
                "acquisition_history_coverage_per_learner.unique_q_rows",
                "acquisition_history_coverage_per_learner.q_rank",
                "adjacent_q_jaccard",
            ],
        },
    }


def learner_split(learner_id: str, config: Mapping[str, Any]) -> str:
    declaration = config["models"]["learner_split"]
    split_seed = int(config["common_random_numbers"]["namespaces"]["model_split"][0])
    draw = keyed_uniform(split_seed, "model_split", learner_id)
    train = float(declaration["train_fraction"])
    dev = train + float(declaration["dev_fraction"])
    if draw < train:
        return "train"
    if draw < dev:
        return "dev"
    return "test"


def within_format_item_contrasts(
    items: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, np.ndarray], list[str], dict[str, Any]]:
    """Orthonormal seen-item nuisance basis orthogonal to format and Q*.

    Orthogonality to intercept and format contrasts implies sum-zero item
    effects overall and within every format.  Orthogonality to Q* removes the
    exact collinearity that a saturated raw item basis would otherwise create
    with shared-K* indicators, while retaining the complete planted item-effect
    subspace.
    """

    seen = sorted(
        [dict(row) for row in items if row["acquisition_updates"]],
        key=lambda row: row["item_id"],
    )
    held = [dict(row) for row in items if not row["acquisition_updates"]]
    format_map, _ = helmert_contrasts(CANONICAL_FORMATS)
    nuisance_controls = np.asarray(
        [
            [1.0, *format_map[item["format"]], *item["q_row"]]
            for item in seen
        ],
        dtype=float,
    )
    control_rank = int(np.linalg.matrix_rank(nuisance_controls, tol=1e-10))
    _, singular_values, right_vectors = np.linalg.svd(
        nuisance_controls.T, full_matrices=True
    )
    svd_rank = int(np.sum(singular_values > 1e-10))
    if svd_rank != control_rank:
        raise AssertionError("item-control rank methods disagree")
    basis = right_vectors[control_rank:].T
    # Canonicalise arbitrary SVD signs for stable hashes.
    for column in range(basis.shape[1]):
        pivot = int(np.argmax(np.abs(basis[:, column])))
        if basis[pivot, column] < 0:
            basis[:, column] *= -1
    total_width = basis.shape[1]
    names = [f"item_residual_contrast::{index + 1:03d}" for index in range(total_width)]
    encodings = {
        item["item_id"]: basis[index].copy() for index, item in enumerate(seen)
    }
    for item in held:
        encodings[item["item_id"]] = np.zeros(total_width, dtype=float)
    if len(encodings) != len(items):
        raise ValueError("item contrast encoding does not cover bank")
    within_format_sums = {
        item_format: np.sum(
            [
                encodings[item["item_id"]]
                for item in seen
                if item["format"] == item_format
            ],
            axis=0,
        )
        for item_format in CANONICAL_FORMATS
    }
    diagnostics = {
        "seen_items": len(seen),
        "held_out_zero_encoded_items": len(held),
        "control_columns": nuisance_controls.shape[1],
        "control_rank": control_rank,
        "contrast_columns": total_width,
        "orthonormal": bool(
            np.allclose(basis.T @ basis, np.eye(total_width), atol=1e-10)
        ),
        "maximum_absolute_control_inner_product": float(
            np.max(np.abs(nuisance_controls.T @ basis))
        ),
        "maximum_absolute_within_format_sum": float(
            max(np.max(np.abs(values)) for values in within_format_sums.values())
        ),
    }
    if not diagnostics["orthonormal"] or diagnostics[
        "maximum_absolute_control_inner_product"
    ] > 1e-8 or diagnostics["maximum_absolute_within_format_sum"] > 1e-8:
        raise AssertionError("item nuisance basis violates orthogonality constraints")
    return encodings, names, diagnostics


@dataclass
class ModelDesign:
    matrix: np.ndarray
    feature_names: list[str]
    continuous_columns: list[int]
    history_width: int
    active_count_diagnostic: np.ndarray


def build_model_design(
    events: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    condition: str,
    error_history: str = "binary",
) -> ModelDesign:
    """Build causal A--D features before reading each current outcome."""

    if condition not in MODEL_CONDITIONS:
        raise ValueError(f"unknown model condition: {condition}")
    if error_history not in {
        "binary",
        "linked_positive_control",
        "linked_80_percent",
        "within_item_shuffled_negative_control",
    }:
        raise ValueError(f"unknown error-history mode: {error_history}")
    item_by_id = _item_lookup(items)
    taxonomy = config["structured_errors"]["taxonomy"]
    representation = "format_split" if condition == "B" else "shared"
    all_labels = sorted(
        {
            (
                f"{kc}@@{item['format']}" if representation == "format_split" else kc
            )
            for item in items
            for kc in item["generator_kc_ids"]
        }
    )
    reference = (
        config["frozen_overlay"]["execution_clarifications"][
            "model_history_correction"
        ]["indicator_reference_coding"]["format_split_reference"]
        if representation == "format_split"
        else config["frozen_overlay"]["execution_clarifications"][
            "model_history_correction"
        ]["indicator_reference_coding"]["shared_kstar_reference"]
    )
    if reference not in all_labels:
        raise ValueError(f"declared reference indicator is absent: {reference}")
    indicator_labels = [label for label in all_labels if label != reference]
    indicator_index = {label: index for index, label in enumerate(indicator_labels)}
    base_width = 3 + len(indicator_labels)
    base = np.zeros((len(events), base_width), dtype=float)
    active_counts = np.zeros(len(events), dtype=float)
    overall_attempts: Counter[str] = Counter()
    overall_correct: Counter[str] = Counter()
    evidence_success: Counter[tuple[str, str]] = Counter()
    evidence_failure: Counter[tuple[str, str]] = Counter()
    opportunities: Counter[tuple[str, str]] = Counter()

    ordered_indices = sorted(
        range(len(events)),
        key=lambda index: (
            str(events[index]["learner_id"]),
            int(events[index]["sequence_index"]),
        ),
    )
    for index in ordered_indices:
        event = events[index]
        learner_id = str(event["learner_id"])
        item = item_by_id[str(event["item_id"])]
        base_kcs = list(item["generator_kc_ids"])
        labels = [
            f"{kc}@@{item['format']}" if representation == "format_split" else kc
            for kc in base_kcs
        ]
        overall_rate = (1 + overall_correct[learner_id]) / (
            2 + overall_attempts[learner_id]
        )
        evidence_rates = [
            (1 + evidence_success[(learner_id, label)])
            / (
                2
                + evidence_success[(learner_id, label)]
                + evidence_failure[(learner_id, label)]
            )
            for label in labels
        ]
        log_opportunities = [
            math.log1p(opportunities[(learner_id, label)]) for label in labels
        ]
        base[index, :3] = (
            overall_rate,
            fmean(evidence_rates),
            fmean(log_opportunities),
        )
        active_counts[index] = len(labels)
        for label in labels:
            if label != reference:
                base[index, 3 + indicator_index[label]] = 1.0

        # Current-row outcome/category is used only after features are frozen.
        if event["phase"] != "acquisition":
            continue
        correct = int(event["correct"])
        overall_attempts[learner_id] += 1
        overall_correct[learner_id] += correct
        for label in labels:
            opportunities[(learner_id, label)] += 1
        if correct:
            for label in labels:
                evidence_success[(learner_id, label)] += 1
        elif error_history == "binary" or event["error_category"] in {
            None,
            "non_target_or_unresolved",
        }:
            for label in labels:
                evidence_failure[(learner_id, label)] += 1
        else:
            category = str(event["error_category"])
            compatible = [
                label
                for label, kc in zip(labels, base_kcs)
                if taxonomy[kc] == category
            ]
            # A category that cannot implicate an active KC is unresolved in
            # this item and executes the preregistered binary fallback.
            if not compatible:
                compatible = labels
            for label in compatible:
                evidence_failure[(learner_id, label)] += 1

    feature_names = [
        "learner_smoothed_correctness",
        "mean_active_kc_evidence_rate",
        "mean_active_kc_log1p_opportunities",
        *[f"active::{label}" for label in indicator_labels],
    ]
    pieces = [base]
    if condition in {"C", "D"}:
        format_map, _ = helmert_contrasts(CANONICAL_FORMATS)
        format_matrix = np.asarray(
            [format_map[item_by_id[str(event["item_id"])]["format"]] for event in events]
        )
        pieces.append(format_matrix)
        feature_names.extend([f"format_contrast::{index}" for index in range(1, 4)])
    if condition == "D":
        item_map, item_names, _ = within_format_item_contrasts(items)
        item_matrix = np.asarray(
            [item_map[str(event["item_id"])] for event in events], dtype=float
        )
        pieces.append(item_matrix)
        feature_names.extend(item_names)
    matrix = np.column_stack(pieces)
    if matrix.shape[1] != len(feature_names):
        raise AssertionError("model feature names/matrix width mismatch")
    return ModelDesign(
        matrix=matrix,
        feature_names=feature_names,
        continuous_columns=[0, 1, 2],
        history_width=base_width,
        active_count_diagnostic=active_counts,
    )


@dataclass
class Standardization:
    means: np.ndarray
    scales: np.ndarray
    columns: list[int]


def fit_standardization(
    matrix: np.ndarray, mask: np.ndarray, columns: Sequence[int]
) -> Standardization:
    if not np.any(mask):
        raise ValueError("standardization requires training rows")
    selected = matrix[mask][:, list(columns)]
    means = np.mean(selected, axis=0)
    scales = np.std(selected, axis=0, ddof=0)
    scales[scales < 1e-12] = 1.0
    return Standardization(means=means, scales=scales, columns=list(columns))


def apply_standardization(
    matrix: np.ndarray, standardization: Standardization
) -> np.ndarray:
    output = np.asarray(matrix, dtype=float).copy()
    output[:, standardization.columns] = (
        output[:, standardization.columns] - standardization.means
    ) / standardization.scales
    return output


@dataclass
class BoundedLogitFit:
    intercept: float
    coefficients: np.ndarray
    converged: bool
    iterations: int
    objective: float
    inverse_l2: float
    optimizer_status: int
    optimizer_message: str
    gradient_infinity_norm: float
    function_evaluations: int

    def latent(self, matrix: np.ndarray) -> np.ndarray:
        return self.intercept + np.asarray(matrix, dtype=float) @ self.coefficients

    def predict(self, matrix: np.ndarray) -> np.ndarray:
        return np.clip(0.10 + 0.80 * logistic(self.latent(matrix)), 1e-9, 1 - 1e-9)


def fit_bounded_logistic(
    matrix: np.ndarray,
    targets: Sequence[int] | np.ndarray,
    *,
    inverse_l2: float,
    maximum_iterations: int = 500,
) -> BoundedLogitFit:
    """Fit p=.10+.80*logistic(eta) by analytic-gradient L-BFGS-B."""

    x = np.asarray(matrix, dtype=float)
    y = np.asarray(targets, dtype=float)
    if x.ndim != 2 or len(y) != len(x) or not len(y):
        raise ValueError("bounded logistic needs a non-empty paired 2D design")
    if set(np.unique(y)) - {0.0, 1.0} or len(np.unique(y)) < 2:
        raise ValueError("bounded logistic training targets need both binary classes")
    if inverse_l2 <= 0:
        raise ValueError("inverse_l2 must be positive")
    rows = len(y)

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        intercept = parameters[0]
        coefficients = parameters[1:]
        eta = intercept + x @ coefficients
        latent = np.asarray(logistic(eta), dtype=float)
        probability = np.clip(0.10 + 0.80 * latent, 1e-12, 1 - 1e-12)
        nll = -np.mean(y * np.log(probability) + (1 - y) * np.log(1 - probability))
        penalty = 0.5 * float(np.dot(coefficients, coefficients)) / (
            inverse_l2 * rows
        )
        d_probability = 0.80 * latent * (1.0 - latent)
        d_loss_d_eta = (
            (probability - y) / (probability * (1.0 - probability))
        ) * d_probability / rows
        gradient = np.empty_like(parameters)
        gradient[0] = np.sum(d_loss_d_eta)
        gradient[1:] = x.T @ d_loss_d_eta + coefficients / (
            inverse_l2 * rows
        )
        return float(nll + penalty), gradient

    result = minimize(
        objective,
        np.zeros(x.shape[1] + 1, dtype=float),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": maximum_iterations, "gtol": 1e-7, "ftol": 1e-12},
    )
    finite = bool(
        np.all(np.isfinite(result.x))
        and math.isfinite(float(result.fun))
        and np.all(np.isfinite(result.jac))
    )
    if not bool(result.success) or not finite:
        raise RuntimeError(
            "bounded logistic optimizer failed: "
            f"status={result.status}, success={result.success}, "
            f"finite={finite}, message={result.message}"
        )
    return BoundedLogitFit(
        intercept=float(result.x[0]),
        coefficients=np.asarray(result.x[1:], dtype=float),
        converged=bool(result.success),
        iterations=int(result.nit),
        objective=float(result.fun),
        inverse_l2=float(inverse_l2),
        optimizer_status=int(result.status),
        optimizer_message=str(result.message),
        gradient_infinity_norm=float(np.max(np.abs(result.jac))),
        function_evaluations=int(result.nfev),
    )


def prediction_metrics(
    targets: Sequence[int] | np.ndarray,
    probabilities: Sequence[float] | np.ndarray,
    *,
    bins: int = 10,
) -> dict[str, Any]:
    y = np.asarray(targets, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1 - 1e-9)
    if len(y) != len(p) or not len(y):
        raise ValueError("metrics require non-empty paired targets/probabilities")
    losses = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    edges = np.linspace(0.0, 1.0, bins + 1)
    table = []
    ece = 0.0
    for index in range(bins):
        mask = (p >= edges[index]) & (
            p <= edges[index + 1] if index == bins - 1 else p < edges[index + 1]
        )
        count = int(np.sum(mask))
        mean_probability = float(np.mean(p[mask])) if count else None
        accuracy = float(np.mean(y[mask])) if count else None
        gap = abs(mean_probability - accuracy) if count else None
        if count:
            ece += count / len(y) * float(gap)
        table.append(
            {
                "bin": index + 1,
                "left": float(edges[index]),
                "right": float(edges[index + 1]),
                "count": count,
                "mean_probability": mean_probability,
                "accuracy": accuracy,
                "absolute_gap": gap,
            }
        )
    return {
        "n": len(y),
        "log_loss": float(np.mean(losses)),
        "brier_score": float(np.mean((p - y) ** 2)),
        "ece_10_fixed_width": float(ece),
        "ece_table": table,
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None,
        "accuracy_at_0_5": float(np.mean((p >= 0.5) == y)),
    }


def paired_learner_interval(
    events: Sequence[Mapping[str, Any]],
    reference_probabilities: Sequence[float],
    candidate_probabilities: Sequence[float],
    *,
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    y = np.asarray([int(row["correct"]) for row in events], dtype=float)
    reference = np.clip(np.asarray(reference_probabilities, dtype=float), 1e-9, 1 - 1e-9)
    candidate = np.clip(np.asarray(candidate_probabilities, dtype=float), 1e-9, 1 - 1e-9)
    if len(y) != len(reference) or len(y) != len(candidate) or repeats < 1:
        raise ValueError("paired interval inputs are invalid")
    loss_reference = -(y * np.log(reference) + (1 - y) * np.log(1 - reference))
    loss_candidate = -(y * np.log(candidate) + (1 - y) * np.log(1 - candidate))
    by_learner: dict[str, list[int]] = defaultdict(list)
    for index, event in enumerate(events):
        by_learner[str(event["learner_id"])].append(index)
    learners = sorted(by_learner)
    learner_deltas = np.asarray(
        [
            float(np.mean(loss_candidate[by_learner[learner]]) - np.mean(loss_reference[by_learner[learner]]))
            for learner in learners
        ]
    )
    rng = np.random.default_rng(seed)
    draws = np.empty(repeats, dtype=float)
    for repeat in range(repeats):
        sampled = rng.integers(0, len(learners), size=len(learners))
        draws[repeat] = float(np.mean(learner_deltas[sampled]))
    return {
        "learners": len(learners),
        "repeats": repeats,
        "delta_sign": "candidate_minus_reference; negative favours candidate",
        "point_estimate": float(np.mean(learner_deltas)),
        "percentile_95": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
    }


def fit_model_condition(
    events: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    condition: str,
    error_history: str = "binary",
) -> dict[str, Any]:
    design = build_model_design(
        events, items, config, condition=condition, error_history=error_history
    )
    splits = np.asarray([learner_split(str(row["learner_id"]), config) for row in events])
    phases = np.asarray([row["phase"] for row in events])
    regimes = np.asarray([row["grammar_regime"] for row in events])
    y = np.asarray([int(row["correct"]) for row in events], dtype=int)
    train_acquisition = (splits == "train") & (phases == "acquisition")
    dev_probe = (splits == "dev") & (phases == "probe") & (regimes == "seen")
    refit_acquisition = np.isin(splits, ["train", "dev"]) & (phases == "acquisition")
    test_probe = (splits == "test") & (phases == "probe")
    if not all(np.any(mask) for mask in (train_acquisition, dev_probe, refit_acquisition, test_probe)):
        raise ValueError("learner split produced an empty required model partition")
    standardization = fit_standardization(
        design.matrix, train_acquisition, design.continuous_columns
    )
    x = apply_standardization(design.matrix, standardization)
    grid = [float(value) for value in config["models"]["inverse_l2_grid"]]
    candidates = []
    for inverse_l2 in grid:
        fitted = fit_bounded_logistic(
            x[train_acquisition],
            y[train_acquisition],
            inverse_l2=inverse_l2,
        )
        dev_probability = fitted.predict(x[dev_probe])
        dev_metrics = prediction_metrics(y[dev_probe], dev_probability)
        candidates.append(
            {
                "inverse_l2": inverse_l2,
                "dev_probe_log_loss": dev_metrics["log_loss"],
                "fit": fitted,
            }
        )
    selected_candidate = min(
        candidates, key=lambda row: (row["dev_probe_log_loss"], row["inverse_l2"])
    )
    final_fit = fit_bounded_logistic(
        x[refit_acquisition],
        y[refit_acquisition],
        inverse_l2=float(selected_candidate["inverse_l2"]),
    )
    test_probability = final_fit.predict(x[test_probe])
    test_targets = y[test_probe]
    # Nuisance-removed state uses the fitted history part only and unbounded
    # latent logistic, exactly as preregistered.
    state_eta = final_fit.intercept + x[test_probe, : design.history_width] @ final_fit.coefficients[
        : design.history_width
    ]
    state_probability = np.asarray(logistic(state_eta), dtype=float)
    training_rank = int(
        np.linalg.matrix_rank(
            np.column_stack([np.ones(int(np.sum(refit_acquisition))), x[refit_acquisition]]),
            tol=1e-10,
        )
    )
    test_indices = np.flatnonzero(test_probe)
    test_events = [dict(events[index]) for index in test_indices]
    test_regimes = np.asarray([row["grammar_regime"] for row in test_events])
    regime_metrics = {
        regime: prediction_metrics(
            test_targets[test_regimes == regime],
            test_probability[test_regimes == regime],
        )
        for regime in ("seen", "unseen_combination", "unseen_value")
        if np.any(test_regimes == regime)
    }
    primary_seen = test_regimes == "seen"
    if not np.any(primary_seen):
        raise ValueError("primary seen-item probe estimand is empty")
    return {
        "condition": condition,
        "error_history": error_history,
        "feature_names": design.feature_names,
        "features": x.shape[1],
        "training_design_rank_with_intercept": training_rank,
        "training_design_full_rank": training_rank == x.shape[1] + 1,
        "reference_indicator": (
            config["frozen_overlay"]["execution_clarifications"][
                "model_history_correction"
            ]["indicator_reference_coding"]["format_split_reference"]
            if condition == "B"
            else config["frozen_overlay"]["execution_clarifications"][
                "model_history_correction"
            ]["indicator_reference_coding"]["shared_kstar_reference"]
        ),
        "split_counts": dict(sorted(Counter(splits).items())),
        "selected_inverse_l2": float(selected_candidate["inverse_l2"]),
        "candidate_dev_log_loss": {
            str(row["inverse_l2"]): row["dev_probe_log_loss"] for row in candidates
        },
        "final_fit": final_fit,
        "fitted_parameters": {
            "intercept": final_fit.intercept,
            "coefficients": {
                name: float(value)
                for name, value in zip(design.feature_names, final_fit.coefficients)
            },
            "optimizer": {
                "converged": final_fit.converged,
                "iterations": final_fit.iterations,
                "function_evaluations": final_fit.function_evaluations,
                "objective": final_fit.objective,
                "inverse_l2": final_fit.inverse_l2,
                "status": final_fit.optimizer_status,
                "message": final_fit.optimizer_message,
                "gradient_infinity_norm": final_fit.gradient_infinity_norm,
            },
        },
        "training_standardization": {
            "columns": standardization.columns,
            "feature_names": [
                design.feature_names[index] for index in standardization.columns
            ],
            "means": standardization.means.tolist(),
            "scales": standardization.scales.tolist(),
        },
        "test_indices": test_indices,
        "test_events": test_events,
        "test_probabilities": test_probability,
        "test_state_probabilities": state_probability,
        "metrics": regime_metrics["seen"],
        "primary_evaluation_scope": "seen_terminal_probes",
        "metrics_all_terminal_probes": prediction_metrics(
            test_targets, test_probability
        ),
        "metrics_by_grammar_regime": regime_metrics,
        "evaluation_row_sha256": semantic_hash(
            [
                [events[index]["learner_id"], events[index]["sequence_index"], events[index]["item_id"]]
                for index in test_indices
            ]
        ),
        "primary_seen_evaluation_row_sha256": semantic_hash(
            [
                [event["learner_id"], event["sequence_index"], event["item_id"]]
                for event in test_events
                if event["grammar_regime"] == "seen"
            ]
        ),
    }


def fit_abcd_models(
    events: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    bootstrap_repeats: int | None = None,
) -> dict[str, Any]:
    results = {
        condition: fit_model_condition(events, items, config, condition=condition)
        for condition in MODEL_CONDITIONS
    }
    hashes = {row["evaluation_row_sha256"] for row in results.values()}
    if len(hashes) != 1:
        raise AssertionError("A--D models consumed different evaluation rows")
    primary_hashes = {
        row["primary_seen_evaluation_row_sha256"] for row in results.values()
    }
    if len(primary_hashes) != 1:
        raise AssertionError("A--D models consumed different primary seen rows")
    repeats = (
        int(config["evaluation"]["bootstrap"]["repeats"])
        if bootstrap_repeats is None
        else int(bootstrap_repeats)
    )
    comparisons = {}
    primary_positions = np.asarray(
        [
            index
            for index, event in enumerate(results["A"]["test_events"])
            if event["grammar_regime"] == "seen"
        ],
        dtype=int,
    )
    primary_events = [results["A"]["test_events"][index] for index in primary_positions]
    for reference, candidate in (("A", "B"), ("B", "C"), ("C", "D")):
        comparisons[f"{candidate}_minus_{reference}"] = paired_learner_interval(
            primary_events,
            results[reference]["test_probabilities"][primary_positions],
            results[candidate]["test_probabilities"][primary_positions],
            repeats=repeats,
            seed=20260830 + ord(candidate),
        )
    return {
        "conditions": results,
        "paired_log_loss_intervals": comparisons,
        "evaluation_row_sha256": next(iter(hashes)),
        "primary_seen_evaluation_row_sha256": next(iter(primary_hashes)),
        "primary_evaluation_scope": "seen_terminal_probes",
    }


def fit_error_history_models(
    streams: Mapping[str, Sequence[Mapping[str, Any]]],
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    condition: str | None = None,
    bootstrap_repeats: int | None = None,
) -> dict[str, Any]:
    """Fit one fixed nuisance model while varying only prior-error evidence.

    The four streams must have identical event order, outcomes, and all other
    observable fields.  Current error labels remain unavailable to the current
    prediction because :func:`build_model_design` freezes each row before it
    updates the learner history.
    """

    expected = {
        "binary_only",
        "linked_positive_control",
        "linked_80_percent",
        "within_item_shuffled_negative_control",
    }
    if set(streams) != expected:
        raise ValueError(f"error-history streams changed: {sorted(streams)}")
    base_rows = [
        {key: value for key, value in row.items() if key != "error_category"}
        for row in streams["binary_only"]
    ]
    for stream_id, rows in streams.items():
        if [
            {key: value for key, value in row.items() if key != "error_category"}
            for row in rows
        ] != base_rows:
            raise ValueError(f"error stream {stream_id} changes non-error data")
    declared = config["frozen_overlay"]["execution_clarifications"][
        "error_history_analysis"
    ]
    fitted_condition = str(declared["fitted_condition"] if condition is None else condition)
    if fitted_condition not in MODEL_CONDITIONS:
        raise ValueError(f"invalid error-history model condition: {fitted_condition}")
    results = {
        stream_id: fit_model_condition(
            streams[stream_id],
            items,
            config,
            condition=fitted_condition,
            error_history=("binary" if stream_id == "binary_only" else stream_id),
        )
        for stream_id in (
            "binary_only",
            "linked_positive_control",
            "linked_80_percent",
            "within_item_shuffled_negative_control",
        )
    }
    evaluation_hashes = {row["evaluation_row_sha256"] for row in results.values()}
    if len(evaluation_hashes) != 1:
        raise AssertionError("error-history models consumed different evaluation rows")
    repeats = (
        int(config["evaluation"]["bootstrap"]["repeats"])
        if bootstrap_repeats is None
        else int(bootstrap_repeats)
    )
    reference = results["binary_only"]
    primary_positions = np.asarray(
        [
            index
            for index, event in enumerate(reference["test_events"])
            if event["grammar_regime"] == "seen"
        ],
        dtype=int,
    )
    primary_events = [reference["test_events"][index] for index in primary_positions]
    comparisons = {
        f"{stream_id}_minus_binary_only": paired_learner_interval(
            primary_events,
            reference["test_probabilities"][primary_positions],
            results[stream_id]["test_probabilities"][primary_positions],
            repeats=repeats,
            seed=20260830 + index,
        )
        for index, stream_id in enumerate(declared["compared_streams"], start=1)
    }
    return {
        "condition_held_fixed": fitted_condition,
        "streams": results,
        "paired_log_loss_intervals": comparisons,
        "evaluation_row_sha256": next(iter(evaluation_hashes)),
    }


def evaluate_item_state_recovery(
    model_result: Mapping[str, Any], oracle: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    oracle_by_key = {
        (str(row["learner_id"]), int(row["sequence_index"])): row for row in oracle
    }
    targets = np.asarray(
        [
            oracle_by_key[(str(event["learner_id"]), int(event["sequence_index"]))][
                "aggregated_mastery_before"
            ]
            for event in model_result["test_events"]
        ],
        dtype=float,
    )
    estimates = np.asarray(model_result["test_state_probabilities"], dtype=float)
    regimes = np.asarray(
        [event["grammar_regime"] for event in model_result["test_events"]]
    )

    def summarize(mask: np.ndarray) -> dict[str, float]:
        selected_estimates = estimates[mask]
        selected_targets = targets[mask]
        return {
            "n": int(np.sum(mask)),
            "rmse": float(
                np.sqrt(np.mean((selected_estimates - selected_targets) ** 2))
            ),
            "mae": float(np.mean(np.abs(selected_estimates - selected_targets))),
            "correlation": (
                float(np.corrcoef(selected_estimates, selected_targets)[0, 1])
                if np.std(selected_estimates) > 0 and np.std(selected_targets) > 0
                else float("nan")
            ),
        }

    by_regime = {
        regime: summarize(regimes == regime)
        for regime in ("seen", "unseen_combination", "unseen_value")
        if np.any(regimes == regime)
    }
    seen = by_regime["seen"]
    return {
        "primary_scope": "seen_terminal_probes",
        "item_prerequisite_state_rmse": seen["rmse"],
        "item_prerequisite_state_mae": seen["mae"],
        "item_prerequisite_state_correlation": seen["correlation"],
        "all_terminal_probes": summarize(np.ones(len(targets), dtype=bool)),
        "by_grammar_regime": by_regime,
    }


def terminal_kc_state_recovery(
    events: Sequence[Mapping[str, Any]],
    terminal_mastery: Mapping[str, Mapping[str, float]],
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    error_history: str,
) -> dict[str, Any]:
    """Secondary Beta-smoothed terminal K* evidence diagnostic.

    This is deliberately named a diagnostic rather than fitted KT mastery: it
    estimates each K* from the same transparent success/failure attribution
    counts used by the causal history model, then compares those estimates with
    otherwise unavailable terminal oracle mastery for test learners.
    """

    if error_history not in {
        "binary",
        "linked_positive_control",
        "linked_80_percent",
        "within_item_shuffled_negative_control",
    }:
        raise ValueError(f"unknown terminal-state error history: {error_history}")
    item_by_id = _item_lookup(items)
    taxonomy = config["structured_errors"]["taxonomy"]
    successes: Counter[tuple[str, str]] = Counter()
    failures: Counter[tuple[str, str]] = Counter()
    for event in sorted(
        events,
        key=lambda row: (str(row["learner_id"]), int(row["sequence_index"])),
    ):
        if event["phase"] != "acquisition":
            continue
        learner = str(event["learner_id"])
        active = list(item_by_id[str(event["item_id"])]["generator_kc_ids"])
        if event["correct"]:
            for kc in active:
                successes[(learner, kc)] += 1
            continue
        category = event["error_category"]
        if error_history == "binary" or category in {
            None,
            "non_target_or_unresolved",
        }:
            implicated = active
        else:
            implicated = [kc for kc in active if taxonomy[kc] == category]
            if not implicated:
                implicated = active
        for kc in implicated:
            failures[(learner, kc)] += 1
    test_learners = sorted(
        learner
        for learner in terminal_mastery
        if learner_split(learner, config) == "test"
    )
    kc_order = sorted(next(iter(terminal_mastery.values())))
    rows = []
    for learner in test_learners:
        for kc in kc_order:
            success = successes[(learner, kc)]
            failure = failures[(learner, kc)]
            estimate = (1.0 + success) / (2.0 + success + failure)
            target = float(terminal_mastery[learner][kc])
            rows.append(
                {
                    "learner_id": learner,
                    "kc_id": kc,
                    "estimate": estimate,
                    "target": target,
                    "error": estimate - target,
                }
            )
    if not rows:
        raise ValueError("terminal state recovery has no test learners")
    by_kc = {
        kc: {
            "n": len(selected_rows),
            "rmse": float(
                np.sqrt(np.mean([row["error"] ** 2 for row in selected_rows]))
            ),
            "mae": float(np.mean([abs(row["error"]) for row in selected_rows])),
        }
        for kc in kc_order
        for selected_rows in [[row for row in rows if row["kc_id"] == kc]]
    }
    return {
        "estimator": "beta_1_1_smoothed_attributed_kc_evidence",
        "error_history": error_history,
        "learners": len(test_learners),
        "learner_kc_pairs": len(rows),
        "rmse": float(np.sqrt(np.mean([row["error"] ** 2 for row in rows]))),
        "mae": float(np.mean([abs(row["error"]) for row in rows])),
        "by_kc": by_kc,
        "interpretation": "secondary transparent evidence diagnostic, not fitted human mastery",
    }


def error_localisation_metrics(
    observable: Sequence[Mapping[str, Any]],
    oracle: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    taxonomy: Mapping[str, str],
) -> dict[str, Any]:
    """Evaluate diagnostic categories only on incorrect multi-KC probes."""

    item_by_id = _item_lookup(items)
    rows = []
    for public, private in zip(observable, oracle):
        active = list(item_by_id[public["item_id"]]["generator_kc_ids"])
        if public["phase"] != "probe" or public["correct"] or len(active) < 2:
            continue
        failed = private["failed_kc"]
        category = public["error_category"]
        compatible = (
            [kc for kc in active if taxonomy[kc] == category]
            if category not in {None, "non_target_or_unresolved"}
            else active
        )
        if not compatible:
            compatible = active
        uniform_probability = 1.0 / len(active)
        compatible_probability = (1.0 / len(compatible)) if failed in compatible else 1e-12
        deficit = np.asarray([1.0 - private["mastery_before"][kc] for kc in compatible])
        deficit = deficit / deficit.sum() if deficit.sum() else np.full(len(compatible), 1 / len(compatible))
        deficit_probability = (
            float(deficit[compatible.index(failed)]) if failed in compatible else 1e-12
        )
        if failed in compatible:
            failed_probability = float(deficit[compatible.index(failed)])
            better = int(np.sum(deficit > failed_probability + 1e-12))
            tied = int(np.sum(np.isclose(deficit, failed_probability, atol=1e-12)))
            tied_ranks = range(better + 1, better + tied + 1)
            deficit_mrr = fmean(1.0 / rank for rank in tied_ranks)
            deficit_top1 = (1.0 / tied) if better == 0 else 0.0
        else:
            deficit_mrr = 0.0
            deficit_top1 = 0.0
        rows.append(
            {
                "uniform_top1": 1.0 / len(active),
                "uniform_mrr": _random_tie_mrr(len(active)),
                "uniform_log_loss": -math.log(uniform_probability),
                "compatible_top1": (1.0 / len(compatible)) if failed in compatible else 0.0,
                "compatible_mrr": (
                    _random_tie_mrr(len(compatible)) if failed in compatible else 0.0
                ),
                "compatible_log_loss": -math.log(max(compatible_probability, 1e-12)),
                "deficit_top1": deficit_top1,
                "deficit_mrr": deficit_mrr,
                "deficit_log_loss": -math.log(max(deficit_probability, 1e-12)),
                "candidate_set_size": len(compatible),
            }
        )
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "target_semantics": (
            "post_outcome_deficit_proportional_attribution_not_causal_failure"
        ),
        **{
            key: fmean(float(row[key]) for row in rows)
            for key in rows[0]
        },
    }


def _random_tie_mrr(size: int) -> float:
    """Expected reciprocal rank under a uniform random ordering of a tie."""

    if size < 1:
        raise ValueError("tie size must be positive")
    return float(sum(1.0 / rank for rank in range(1, size + 1)) / size)


def _portable_file_record(path: Path) -> dict[str, Any]:
    """Return the byte identity of one planned input without weakening paths."""

    resolved = path.resolve()
    try:
        portable = str(resolved.relative_to(ROOT))
    except ValueError:
        portable = str(resolved)
    return {
        "path": portable,
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _resolve_planned_path(declaration: Mapping[str, Any]) -> Path:
    path = Path(str(declaration["path"]))
    return path if path.is_absolute() else ROOT / path


def _directory_evidence_identity(run_root: Path) -> dict[str, Any]:
    """Content-address the complete matched-bank run evidence tree.

    The bank verifier checks the meaning of every accepted family.  This tree
    identity additionally prevents a post-plan substitution that happens to
    continue passing those gates.  The digest covers relative names, file
    sizes, and byte hashes, while keeping the study plan compact.
    """

    records = []
    total_bytes = 0
    for path in sorted(candidate for candidate in run_root.rglob("*") if candidate.is_file()):
        size = path.stat().st_size
        total_bytes += size
        records.append(
            {
                "path": str(path.relative_to(run_root)),
                "bytes": size,
                "sha256": sha256_file(path),
            }
        )
    if not records:
        raise ValueError("curated-bank evidence tree is empty")
    return {
        "run_root": _display_path(run_root.resolve()),
        "file_count": len(records),
        "bytes": total_bytes,
        "semantic_sha256": semantic_hash(records),
    }


def validate_frozen_curated_bank_evidence(
    bank_path: Path,
    *,
    expected_schema_path: Path,
) -> dict[str, Any]:
    """Require a genuine, replayable output of the matched-bank freezer.

    Row-level validation alone is intentionally insufficient: renaming the
    synthetic fixture could otherwise impersonate a production bank.  The
    production gate therefore requires the canonical ``bank/items.jsonl``
    location, sibling frozen artifacts, the curation ledger, and successful
    replay of the bank protocol's verifier.
    """

    resolved = bank_path.resolve()
    if resolved.name != "items.jsonl" or resolved.parent.name != "bank":
        raise ValueError(
            "production curated bank must be a matched-bank freeze at "
            "RUN_ROOT/bank/items.jsonl"
        )
    run_root = resolved.parent.parent
    required = {
        "bank_manifest": run_root / "bank/manifest.json",
        "bank_families": run_root / "bank/families.jsonl",
        "bank_q_matrix": run_root / "bank/q_matrix.csv",
        "bank_protocol_plan": run_root / "plan.json",
        "bank_protocol_input_hashes": run_root / "frozen/input_hashes.json",
        "bank_protocol_selected_cells": run_root / "frozen/selected_cells.json",
        "bank_protocol_curated_schema": (
            run_root / "frozen/schemas/curated_item.schema.json"
        ),
        "bank_protocol_curation_ledger": (
            run_root / "curation/family_decisions.jsonl"
        ),
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(
            "production curated-bank evidence chain is incomplete: "
            + ", ".join(sorted(missing))
        )
    if sha256_file(required["bank_protocol_curated_schema"]) != sha256_file(
        expected_schema_path
    ):
        raise ValueError("frozen bank used a different curated-item schema")
    manifest = json.loads(required["bank_manifest"].read_text(encoding="utf-8"))
    if (
        manifest.get("status")
        != "FROZEN_AUTOMATED_VALIDATION_COMPLETE_HUMAN_VALIDATION_PENDING"
        or manifest.get("counts")
        != {"families": 38, "items": 152, "formats": 4, "generator_kcs": 18}
        or manifest.get("scientific_boundary", {}).get(
            "learner_outcomes_used_in_construction"
        )
        is not False
    ):
        raise ValueError("curated-bank freeze manifest is not production eligible")
    if manifest.get("artifacts", {}).get("items.jsonl", {}).get(
        "sha256"
    ) != sha256_file(resolved):
        raise ValueError("curated bank is not the item artifact named by its manifest")

    # Import lazily so fixture-only simulation helpers do not acquire a bank
    # construction dependency.  This is a local, deterministic verifier; it
    # makes no model or network calls.
    from scripts.experiments.measurement_realism_bank import verify_bank

    replay = verify_bank(run_root)
    if replay.get("verified") is not True or replay.get("items") != 152:
        raise ValueError("matched-bank verifier did not replay the curated freeze")
    return {
        "evidence_gate": "matched_bank_freeze_and_full_verifier_replay",
        "run_id": replay["run_id"],
        "verified": True,
        "families": replay["families"],
        "items": replay["items"],
        "seen_q_rank": replay["seen_q_rank"],
        "manifest_sha256": replay["manifest_sha256"],
        "v1_manifest_sha256": replay["v1_manifest_sha256"],
        "required_artifacts": {
            name: _portable_file_record(path) for name, path in required.items()
        },
        "complete_evidence_tree": _directory_evidence_identity(run_root),
    }


def _plan_inputs(
    config_path: Path,
    config: Mapping[str, Any],
    bank_path: Path,
    schema_path: Path,
) -> dict[str, dict[str, Any]]:
    paths: dict[str, Path] = {
        "executable_config": config_path,
        "selected_cells": Path(config["_paths"]["selected_cells"]),
        "implementation_script": Path(__file__).resolve(),
        "schedule_dependency": ROOT / "src/grammar_kt/baseline_simulation.py",
        "dependency_declaration": ROOT / "pyproject.toml",
    }
    if is_controlled_config(config):
        paths.update(
            {
                "base_executable_config": Path(
                    config["_paths"]["base_executable_config"]
                ),
                "controlled_instrument_schema": schema_path,
                "controlled_instrument": bank_path,
                "controlled_instrument_manifest": Path(
                    config["_paths"]["controlled_instrument_manifest"]
                ),
                "controlled_instrument_builder": Path(
                    config["_paths"]["controlled_instrument_builder"]
                ),
                "controlled_instrument_protocol": Path(
                    config["_paths"]["controlled_instrument_protocol"]
                ),
                "controlled_instrument_execution_plan": Path(
                    config["_paths"]["controlled_instrument_execution_plan"]
                ),
                "failed_curated_decision_ledger": Path(
                    config["_paths"]["failed_curated_decisions"]
                ),
            }
        )
    else:
        paths.update(
            {
                "base_config": Path(config["_paths"]["base"]),
                "curated_item_schema": schema_path,
                "curated_bank": bank_path,
                "bank_protocol_implementation": (
                    ROOT / "scripts/experiments/measurement_realism_bank.py"
                ),
            }
        )
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    return {key: _portable_file_record(path) for key, path in paths.items()}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _planned_run_matrix(config: Mapping[str, Any]) -> tuple[list[str], list[int], list[str], list[dict[str, Any]]]:
    world_ids = [row["world_id"] for row in config["worlds"]]
    seeds = list(config["simulation"]["seeds"])
    policies = [row["policy_id"] for row in config["schedule"]["policies"]]
    matrix = [
        {"world_id": world_id, "policy_id": "q_balanced_lab", "seed": seed}
        for world_id in world_ids
        for seed in seeds
    ] + [
        {
            "world_id": "combined_heterogeneous",
            "policy_id": policy_id,
            "seed": seed,
        }
        for policy_id in policies
        if policy_id != "q_balanced_lab"
        for seed in seeds
    ]
    return world_ids, seeds, policies, matrix


def _planned_commands(
    *,
    config_path: Path,
    bank_path: Path,
    output_dir: Path,
    controlled: bool,
) -> dict[str, str]:
    script = Path(__file__).resolve().relative_to(ROOT)
    flag = " --controlled-scenario" if controlled else ""
    config_arg = f" --config {_display_path(config_path)}"
    bank_arg = f" --bank {_display_path(bank_path)}"
    common = f"python {script}"
    return {
        "plan": (
            f"{common} --stage plan{flag}{config_arg}{bank_arg} "
            f"--output-dir {_display_path(output_dir)}"
        ),
        "run_after_explicit_approval_only": (
            f"{common} --stage run{flag}{config_arg} "
            f"--output-dir {_display_path(output_dir)} --world clean_zero "
            "--seed 20260829 --policy q_balanced_lab"
        ),
        "validate_plan": (
            f"{common} --stage validate-plan{flag}{config_arg} "
            f"--output-dir {_display_path(output_dir)}"
        ),
        "analyze": (
            f"{common} --stage analyze{flag}{config_arg} "
            f"--output-dir {_display_path(output_dir)} --world clean_zero "
            "--seed 20260829 --policy q_balanced_lab"
        ),
        "aggregate": (
            f"{common} --stage aggregate{flag}{config_arg} "
            f"--output-dir {_display_path(output_dir)}"
        ),
    }


def _planned_runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy": package_version("numpy"),
        "scipy": package_version("scipy"),
        "scikit_learn": package_version("scikit-learn"),
        "pyyaml": package_version("PyYAML"),
        "jsonschema": package_version("jsonschema"),
    }


def create_run_plan(
    *,
    config_path: Path,
    bank_path: Path,
    output_dir: Path,
    controlled_scenario: bool = False,
) -> dict[str, Any]:
    config = load_executable_config(config_path)
    controlled = is_controlled_config(config)
    if controlled != bool(controlled_scenario):
        required = "with" if controlled else "without"
        raise ValueError(
            f"config/runner mode mismatch: this config must be planned {required} "
            "the explicit --controlled-scenario gate"
        )
    validate_plan_output_path(output_dir, config)
    selected = load_selected_cells(config)
    if controlled:
        expected_bank_path = Path(config["_paths"]["controlled_instrument"]).resolve()
        if bank_path.resolve() != expected_bank_path:
            raise ValueError(
                "controlled plan must use the exact content-addressed instrument.jsonl"
            )
        schema_path = Path(config["_paths"]["controlled_instrument_schema"])
        instrument_audit = validate_controlled_instrument(
            read_jsonl(bank_path), selected, config, schema_path=schema_path
        )
        items = instrument_audit["items"]
        evidence_audit = None
        plan_status = config["controlled_scenario_overlay"]["runner_gate"][
            "plan_status"
        ]
        scenario_kind = "controlled_instrument_scaffold"
    else:
        schema_path = _resolve(
            ROOT,
            config["frozen_overlay"]["curated_bank_contract"]["schema_path"],
        )
        raw_items = read_jsonl(bank_path)
        instrument_audit = validate_curated_bank(
            raw_items, selected, config, schema_path=schema_path, fixture=False
        )
        items = instrument_audit["items"]
        evidence_audit = validate_frozen_curated_bank_evidence(
            bank_path, expected_schema_path=schema_path
        )
        plan_status = config["frozen_overlay"]["response_generation_gate"][
            "plan_status"
        ]
        scenario_kind = "curated_measurement_bank"
    if (output_dir / "runs").exists() or (output_dir / "aggregate").exists():
        raise FileExistsError(
            "response/analysis artifacts already exist; cannot truthfully create a "
            "before-response study plan"
        )
    occurrences, schedule = build_balanced_multiset(items, config)
    world_ids, seeds, policies, run_matrix = _planned_run_matrix(config)
    plan = {
        "study_id": config["design_id"],
        "status": plan_status,
        "scenario_kind": scenario_kind,
        "controlled_scenario": controlled,
        "release_eligible": False if controlled else None,
        "claim_boundary": (
            config["controlled_scenario_overlay"]["claim_boundary"]
            if controlled
            else {
                "automated_validation_complete": True,
                "human_validation_pending": True,
                "platform_deployment_validated": False,
            }
        ),
        "created_before_response_generation": True,
        "runtime_versions": _planned_runtime_versions(),
        "inputs": _plan_inputs(config_path, config, bank_path, schema_path),
        "instrument_audit": {
            key: value for key, value in instrument_audit.items() if key != "items"
        },
        "production_curated_bank_evidence": evidence_audit,
        "frozen_acquisition_budget": len(occurrences),
        "acquisition_occurrence_semantic_sha256": semantic_hash(occurrences),
        "schedule_diagnostics": schedule,
        "world_ids": world_ids,
        "seeds": seeds,
        "policies": policies,
        "run_matrix": run_matrix,
        "response_generation_authority": {
            "external_approval_required": controlled,
            "external_approval_recorded_in_plan": False,
            "runner_flag_required": controlled,
            "runner_flag": "--controlled-scenario" if controlled else None,
            "canonical_output_dir": (
                _display_path(controlled_output_dir(config)) if controlled else None
            ),
            "planned_output_is_canonical": (
                output_dir.resolve() == controlled_output_dir(config)
                if controlled
                else None
            ),
        },
        "commands": _planned_commands(
            config_path=config_path,
            bank_path=bank_path,
            output_dir=output_dir,
            controlled=controlled,
        ),
    }
    write_frozen_json(output_dir / "study_plan.json", plan, "measurement-world plan")
    return plan


def validate_run_plan(
    output_dir: Path, *, controlled_scenario: bool = False
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    plan_path = output_dir / "study_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run requires a frozen study_plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for name, declaration in plan["inputs"].items():
        path = _resolve_planned_path(declaration)
        if (
            not path.is_file()
            or sha256_file(path) != declaration["sha256"]
            or path.stat().st_size != declaration["bytes"]
        ):
            raise ValueError(f"planned input changed: {name}")
    config_path = _resolve_planned_path(plan["inputs"]["executable_config"])
    config = load_executable_config(config_path)
    validate_plan_output_path(output_dir, config)
    controlled = is_controlled_config(config)
    if controlled != bool(controlled_scenario) or plan.get(
        "controlled_scenario"
    ) != controlled:
        raise ValueError(
            "study-plan mode mismatch; controlled plans require the explicit "
            "--controlled-scenario gate"
        )
    expected_status = (
        config["controlled_scenario_overlay"]["runner_gate"]["plan_status"]
        if controlled
        else config["frozen_overlay"]["response_generation_gate"]["plan_status"]
    )
    if plan.get("status") != expected_status or plan.get(
        "created_before_response_generation"
    ) is not True:
        raise ValueError("study plan does not predate responses")
    selected = load_selected_cells(config)
    if controlled:
        if (
            plan.get("scenario_kind") != "controlled_instrument_scaffold"
            or plan.get("release_eligible") is not False
            or plan.get("production_curated_bank_evidence") is not None
        ):
            raise ValueError("controlled study plan crossed its claim boundary")
        bank_path = _resolve_planned_path(plan["inputs"]["controlled_instrument"])
        schema_path = _resolve_planned_path(
            plan["inputs"]["controlled_instrument_schema"]
        )
        audit = validate_controlled_instrument(
            read_jsonl(bank_path), selected, config, schema_path=schema_path
        )
    else:
        if plan.get("scenario_kind") != "curated_measurement_bank":
            raise ValueError("production plan scenario kind changed")
        bank_path = _resolve_planned_path(plan["inputs"]["curated_bank"])
        schema_path = _resolve_planned_path(plan["inputs"]["curated_item_schema"])
        audit = validate_curated_bank(
            read_jsonl(bank_path),
            selected,
            config,
            schema_path=schema_path,
            fixture=False,
        )
        replay = validate_frozen_curated_bank_evidence(
            bank_path, expected_schema_path=schema_path
        )
        if replay != plan.get("production_curated_bank_evidence"):
            raise ValueError("production curated-bank evidence changed after planning")
    planned_audit = {
        key: value for key, value in audit.items() if key != "items"
    }
    if planned_audit != plan.get("instrument_audit"):
        raise ValueError("planned instrument audit changed")
    items = audit["items"]
    occurrences, schedule = build_balanced_multiset(items, config)
    if len(occurrences) != plan["frozen_acquisition_budget"]:
        raise ValueError("acquisition budget changed after preregistration")
    if semantic_hash(occurrences) != plan["acquisition_occurrence_semantic_sha256"]:
        raise ValueError("acquisition occurrence multiset changed after preregistration")
    world_ids, seeds, policies, run_matrix = _planned_run_matrix(config)
    expected_claim_boundary = (
        config["controlled_scenario_overlay"]["claim_boundary"]
        if controlled
        else {
            "automated_validation_complete": True,
            "human_validation_pending": True,
            "platform_deployment_validated": False,
        }
    )
    expected_authority = {
        "external_approval_required": controlled,
        "external_approval_recorded_in_plan": False,
        "runner_flag_required": controlled,
        "runner_flag": "--controlled-scenario" if controlled else None,
        "canonical_output_dir": (
            _display_path(controlled_output_dir(config)) if controlled else None
        ),
        "planned_output_is_canonical": (
            output_dir.resolve() == controlled_output_dir(config)
            if controlled
            else None
        ),
    }
    expected_inputs = _plan_inputs(config_path, config, bank_path, schema_path)
    exact_fields = {
        "study_id": config["design_id"],
        "status": expected_status,
        "scenario_kind": (
            "controlled_instrument_scaffold"
            if controlled
            else "curated_measurement_bank"
        ),
        "controlled_scenario": controlled,
        "release_eligible": False if controlled else None,
        "claim_boundary": expected_claim_boundary,
        "created_before_response_generation": True,
        "runtime_versions": _planned_runtime_versions(),
        "inputs": expected_inputs,
        "instrument_audit": planned_audit,
        "production_curated_bank_evidence": (
            None if controlled else replay
        ),
        "frozen_acquisition_budget": len(occurrences),
        "acquisition_occurrence_semantic_sha256": semantic_hash(occurrences),
        "schedule_diagnostics": schedule,
        "world_ids": world_ids,
        "seeds": seeds,
        "policies": policies,
        "run_matrix": run_matrix,
        "response_generation_authority": expected_authority,
        "commands": _planned_commands(
            config_path=config_path,
            bank_path=bank_path,
            output_dir=output_dir,
            controlled=controlled,
        ),
    }
    if set(plan) != set(exact_fields):
        raise ValueError("study-plan field set changed after preregistration")
    for field, expected in exact_fields.items():
        if plan.get(field) != expected:
            raise ValueError(f"study-plan field changed after preregistration: {field}")
    return plan, config, selected, items


def _jsonable_model_results(results: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        "evaluation_row_sha256": results["evaluation_row_sha256"],
        "primary_seen_evaluation_row_sha256": results[
            "primary_seen_evaluation_row_sha256"
        ],
        "primary_evaluation_scope": results["primary_evaluation_scope"],
        "paired_log_loss_intervals": results["paired_log_loss_intervals"],
        "conditions": {},
    }
    for condition, row in results["conditions"].items():
        output["conditions"][condition] = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "final_fit",
                "test_indices",
                "test_events",
                "test_probabilities",
                "test_state_probabilities",
            }
        }
        output["conditions"][condition]["test_probability_sha256"] = semantic_hash(
            [row["test_probabilities"].tolist()]
        )
        output["conditions"][condition]["test_state_probability_sha256"] = semantic_hash(
            [row["test_state_probabilities"].tolist()]
        )
    return output


def _jsonable_error_history_results(results: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        "condition_held_fixed": results["condition_held_fixed"],
        "evaluation_row_sha256": results["evaluation_row_sha256"],
        "paired_log_loss_intervals": results["paired_log_loss_intervals"],
        "streams": {},
    }
    omitted = {
        "final_fit",
        "test_indices",
        "test_events",
        "test_probabilities",
        "test_state_probabilities",
    }
    for stream_id, row in results["streams"].items():
        output["streams"][stream_id] = {
            key: value for key, value in row.items() if key not in omitted
        }
        output["streams"][stream_id]["test_probability_sha256"] = semantic_hash(
            [row["test_probabilities"].tolist()]
        )
        output["streams"][stream_id][
            "test_state_probability_sha256"
        ] = semantic_hash([row["test_state_probabilities"].tolist()])
    return output


def _artifact_hashes(directory: Path, *, excluded: set[str]) -> dict[str, str]:
    output = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(directory))
        if any(relative == name or relative.startswith(f"{name}/") for name in excluded):
            continue
        output[relative] = sha256_file(path)
    return output


def _response_artifact_hashes(run_dir: Path) -> dict[str, str]:
    excluded = {
        "run_manifest.json",
        "analysis",
        *{
            path.name
            for path in run_dir.glob(".analysis.incomplete.*")
            if path.is_dir()
        },
    }
    return _artifact_hashes(run_dir, excluded=excluded)


def _run_name(world_id: str, policy_id: str, seed: int) -> str:
    return f"{world_id}__{policy_id}__seed_{seed}"


def _validate_retained_claim_boundary(
    manifest: Mapping[str, Any], *, controlled_scenario: bool, artifact: str
) -> None:
    if controlled_scenario:
        required = {
            "controlled_scenario": True,
            "release_eligible": False,
        }
        if artifact == "response":
            required.update(
                {
                    "learner_facing_measurement_validity": "NOT_ASSESSED",
                    "platform_plausibility": "NOT_ASSESSED",
                }
            )
        if any(manifest.get(key) != value for key, value in required.items()):
            raise ValueError(f"{artifact} manifest crossed controlled claim boundary")


def _prediction_rows(
    results: Mapping[str, Any], *, result_key: str
) -> list[dict[str, Any]]:
    fitted = results[result_key]
    labels = list(fitted)
    reference = fitted[labels[0]]
    rows = []
    for index, event in enumerate(reference["test_events"]):
        row = {
            "learner_id": event["learner_id"],
            "sequence_index": event["sequence_index"],
            "item_id": event["item_id"],
            "grammar_regime": event["grammar_regime"],
            "correct": event["correct"],
        }
        for label in labels:
            candidate = fitted[label]
            if candidate["test_events"][index]["item_id"] != event["item_id"]:
                raise AssertionError("prediction rows do not align")
            row[f"probability_{label}"] = float(candidate["test_probabilities"][index])
            row[f"state_probability_{label}"] = float(
                candidate["test_state_probabilities"][index]
            )
        rows.append(row)
    return rows


def _terminal_mastery_from_oracle(
    oracle: Sequence[Mapping[str, Any]], kc_order: Sequence[str]
) -> dict[str, dict[str, float]]:
    terminal: dict[str, dict[str, float]] = defaultdict(dict)
    for row in sorted(
        (row for row in oracle if row["phase"] == "acquisition"),
        key=lambda row: (str(row["learner_id"]), int(row["sequence_index"])),
    ):
        terminal[str(row["learner_id"])].update(
            {kc: float(value) for kc, value in row["mastery_after"].items()}
        )
    incomplete = {
        learner: sorted(set(kc_order) - set(values))
        for learner, values in terminal.items()
        if set(values) != set(kc_order)
    }
    if incomplete:
        raise ValueError(f"oracle acquisition does not cover terminal K*: {incomplete}")
    return dict(terminal)


def run_planned_world(
    output_dir: Path,
    *,
    world_id: str,
    seed: int,
    policy_id: str,
    learner_count: int | None,
    controlled_scenario: bool = False,
) -> dict[str, Any]:
    """Generate an immutable response run; fitted analysis is a separate stage."""

    plan, config, selected, items = validate_run_plan(
        output_dir, controlled_scenario=controlled_scenario
    )
    if controlled_scenario:
        require_canonical_controlled_output(output_dir, config)
    configured_learners = int(config["simulation"]["learners_per_seed"])
    if learner_count is not None and int(learner_count) != configured_learners:
        raise ValueError(
            "planned response runs require the preregistered learner count "
            f"({configured_learners}); reduced counts are fixture/test-only"
        )
    requested = {"world_id": world_id, "policy_id": policy_id, "seed": seed}
    if requested not in plan["run_matrix"]:
        raise ValueError("requested run is outside the preregistered matrix")
    result = simulate_world(
        items,
        selected,
        config,
        world_id=world_id,
        seed=seed,
        policy_id=policy_id,
        learner_count=learner_count,
    )
    run_dir = output_dir / "runs" / _run_name(world_id, policy_id, seed)
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite response run: {run_dir}")
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{run_dir.name}.incomplete.", dir=run_dir.parent)
    )
    write_jsonl(staging / "observable.jsonl.gz", result["observable"], gzip_output=True)
    write_jsonl(staging / "oracle.jsonl.gz", result["oracle"], gzip_output=True)
    diagnostics = observable_distribution_diagnostics(result["observable"], items)
    write_frozen_json(staging / "observable_diagnostics.json", diagnostics, "diagnostics")
    error_audit: dict[str, Any] | None = None
    if world_id == "combined_heterogeneous" and policy_id == "q_balanced_lab":
        error_streams, error_audit = make_error_streams(
            result["observable"], result["oracle"], seed=seed
        )
        for stream_id, rows in error_streams.items():
            write_jsonl(staging / f"errors_{stream_id}.jsonl.gz", rows, gzip_output=True)
        write_frozen_json(staging / "error_stream_audit.json", error_audit, "error audit")
    artifact_hashes = _artifact_hashes(staging, excluded={"run_manifest.json"})
    crn_namespace_evidence = {
        "initial_mastery": "common_random_hashes.initial_mastery",
        "learner_ability_z": [
            "common_random_hashes.ability_raw_z",
            "common_random_hashes.ability_z",
        ],
        "learner_learning_rate": "common_random_hashes.learning_rate",
        "learner_guess": "common_random_hashes.guess_beta",
        "learner_slip": "common_random_hashes.slip_beta",
        "item_difficulty_z": "common_random_hashes.item_difficulty_z",
        "acquisition_response": "common_random_hashes.acquisition_response",
        "probe_response": "common_random_hashes.probe_response",
        "failed_kc_draw": "common_random_hashes.failed_kc_draw",
        "policy_exploration": [
            "common_random_hashes.policy_exploration",
            "policy_randomness_semantic_sha256",
            "schedule_assignment_semantic_sha256",
        ],
        "policy_tie_rank": [
            "common_random_hashes.policy_tie_rank_keyspace",
            "schedule_assignment_semantic_sha256",
        ],
        "model_split": "common_random_hashes.model_split",
        "error_observation": (
            "error_stream_audit.common_random_hashes.error_observation"
            if error_audit is not None
            else "not_applicable_outside_combined_q_balanced_error_run"
        ),
        "error_shuffle": (
            "error_stream_audit.common_random_hashes.error_shuffle"
            if error_audit is not None
            else "not_applicable_outside_combined_q_balanced_error_run"
        ),
    }
    run_manifest = {
        **result["manifest"],
        "run_kind": (
            "controlled_instrument_response_only"
            if controlled_scenario
            else "confirmatory_curated_response_only"
        ),
        "scenario_kind": plan["scenario_kind"],
        "controlled_scenario": controlled_scenario,
        "release_eligible": False if controlled_scenario else None,
        "learner_facing_measurement_validity": (
            "NOT_ASSESSED" if controlled_scenario else "AUTOMATED_VALIDATION_ONLY"
        ),
        "platform_plausibility": (
            "NOT_ASSESSED" if controlled_scenario else "NOT_DEPLOYMENT_VALIDATED"
        ),
        "analysis_is_separate_stage": True,
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": package_version("numpy"),
            "scipy": package_version("scipy"),
            "scikit_learn": package_version("scikit-learn"),
        },
        "crn_namespace_evidence": crn_namespace_evidence,
        "study_plan_sha256": sha256_file(output_dir / "study_plan.json"),
        "artifacts": artifact_hashes,
    }
    write_frozen_json(staging / "run_manifest.json", run_manifest, "run manifest")
    staging.rename(run_dir)
    return run_manifest


def _load_response_run(
    output_dir: Path,
    *,
    world_id: str,
    seed: int,
    policy_id: str,
    controlled_scenario: bool = False,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    Path,
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    plan, config, selected, items = validate_run_plan(
        output_dir, controlled_scenario=controlled_scenario
    )
    if controlled_scenario:
        require_canonical_controlled_output(output_dir, config)
    run_dir = output_dir / "runs" / _run_name(world_id, policy_id, seed)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"response run is incomplete or absent: {run_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_kind = (
        "controlled_instrument_response_only"
        if controlled_scenario
        else "confirmatory_curated_response_only"
    )
    if (
        manifest.get("run_kind") != expected_kind
        or manifest.get("controlled_scenario") is not controlled_scenario
        or manifest.get("world_id") != world_id
        or manifest.get("policy_id") != policy_id
        or manifest.get("seed") != seed
    ):
        raise ValueError("response-run identity does not match request")
    _validate_retained_claim_boundary(
        manifest, controlled_scenario=controlled_scenario, artifact="response"
    )
    if manifest.get("study_plan_sha256") != sha256_file(output_dir / "study_plan.json"):
        raise ValueError("response run references a different study plan")
    actual_hashes = _response_artifact_hashes(run_dir)
    if actual_hashes != manifest.get("artifacts"):
        raise ValueError("response-run artifact hash mismatch")
    observable = read_jsonl(run_dir / "observable.jsonl.gz")
    oracle = read_jsonl(run_dir / "oracle.jsonl.gz")
    validate_stream_separation(observable, oracle)
    if semantic_hash(observable) != manifest["observable_semantic_sha256"]:
        raise ValueError("observable response semantic hash mismatch")
    if semantic_hash(oracle) != manifest["oracle_semantic_sha256"]:
        raise ValueError("oracle response semantic hash mismatch")
    return plan, config, selected, items, run_dir, manifest, observable, oracle


def analyze_planned_world(
    output_dir: Path,
    *,
    world_id: str,
    seed: int,
    policy_id: str,
    controlled_scenario: bool = False,
) -> dict[str, Any]:
    """Fit the fully frozen analysis without modifying response artifacts."""

    (
        _,
        config,
        selected,
        items,
        run_dir,
        response_manifest,
        observable,
        oracle,
    ) = _load_response_run(
        output_dir,
        world_id=world_id,
        seed=seed,
        policy_id=policy_id,
        controlled_scenario=controlled_scenario,
    )
    analysis_dir = run_dir / "analysis"
    if analysis_dir.exists():
        raise FileExistsError(f"refusing to overwrite analysis: {analysis_dir}")
    models = fit_abcd_models(observable, items, config)
    for row in models["conditions"].values():
        row["state_recovery"] = evaluate_item_state_recovery(row, oracle)
    terminal_mastery = _terminal_mastery_from_oracle(oracle, selected["kc_order"])
    model_output = _jsonable_model_results(models)
    model_output["terminal_kc_state_recovery_secondary"] = terminal_kc_state_recovery(
        observable,
        terminal_mastery,
        items,
        config,
        error_history="binary",
    )
    staging = Path(
        tempfile.mkdtemp(prefix=".analysis.incomplete.", dir=run_dir)
    )
    write_frozen_json(staging / "model_results.json", model_output, "model results")
    write_jsonl(
        staging / "test_predictions.jsonl.gz",
        _prediction_rows(models, result_key="conditions"),
        gzip_output=True,
    )
    error_files = sorted(run_dir.glob("errors_*.jsonl.gz"))
    if error_files:
        error_streams = {
            path.name.removeprefix("errors_").removesuffix(".jsonl.gz"): read_jsonl(path)
            for path in error_files
        }
        error_models = fit_error_history_models(error_streams, items, config)
        localisation = {}
        terminal_error_recovery = {}
        for stream_id, row in error_models["streams"].items():
            row["state_recovery"] = evaluate_item_state_recovery(row, oracle)
            localisation[stream_id] = error_localisation_metrics(
                error_streams[stream_id],
                oracle,
                items,
                config["structured_errors"]["taxonomy"],
            )
            terminal_error_recovery[stream_id] = terminal_kc_state_recovery(
                error_streams[stream_id],
                terminal_mastery,
                items,
                config,
                error_history=("binary" if stream_id == "binary_only" else stream_id),
            )
        error_output = _jsonable_error_history_results(error_models)
        error_output["failed_kc_localisation"] = localisation
        error_output["terminal_kc_state_recovery_secondary"] = terminal_error_recovery
        write_frozen_json(
            staging / "error_history_model_results.json",
            error_output,
            "error-history model results",
        )
        write_jsonl(
            staging / "error_test_predictions.jsonl.gz",
            _prediction_rows(error_models, result_key="streams"),
            gzip_output=True,
        )
    artifact_hashes = _artifact_hashes(staging, excluded={"analysis_manifest.json"})
    analysis_manifest = {
        "analysis_kind": (
            "controlled_instrument_analysis_v1"
            if controlled_scenario
            else "frozen_curated_measurement_world_analysis_v1"
        ),
        "scenario_kind": response_manifest["scenario_kind"],
        "controlled_scenario": controlled_scenario,
        "release_eligible": False if controlled_scenario else None,
        "world_id": world_id,
        "policy_id": policy_id,
        "seed": seed,
        "response_run_manifest_sha256": sha256_file(run_dir / "run_manifest.json"),
        "implementation_sha256": sha256_file(Path(__file__).resolve()),
        "artifacts": artifact_hashes,
    }
    write_frozen_json(
        staging / "analysis_manifest.json", analysis_manifest, "analysis manifest"
    )
    staging.rename(analysis_dir)
    return analysis_manifest


def _validated_analysis_bundle(
    output_dir: Path,
    *,
    world_id: str,
    policy_id: str,
    seed: int,
    controlled_scenario: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = json.loads((output_dir / "study_plan.json").read_text(encoding="utf-8"))
    run_dir = output_dir / "runs" / _run_name(world_id, policy_id, seed)
    response_manifest_path = run_dir / "run_manifest.json"
    analysis_dir = run_dir / "analysis"
    analysis_manifest_path = analysis_dir / "analysis_manifest.json"
    if not response_manifest_path.is_file() or not analysis_manifest_path.is_file():
        raise FileNotFoundError(f"complete response+analysis required: {run_dir}")
    response_manifest = json.loads(response_manifest_path.read_text(encoding="utf-8"))
    expected_response_kind = (
        "controlled_instrument_response_only"
        if controlled_scenario
        else "confirmatory_curated_response_only"
    )
    if (
        response_manifest.get("run_kind") != expected_response_kind
        or response_manifest.get("controlled_scenario") is not controlled_scenario
        or response_manifest.get("scenario_kind") != plan["scenario_kind"]
        or response_manifest.get("world_id") != world_id
        or response_manifest.get("policy_id") != policy_id
        or response_manifest.get("seed") != seed
        or response_manifest.get("study_plan_sha256")
        != sha256_file(output_dir / "study_plan.json")
    ):
        raise ValueError(f"response scenario mode mismatch: {run_dir}")
    _validate_retained_claim_boundary(
        response_manifest,
        controlled_scenario=controlled_scenario,
        artifact="response",
    )
    if _response_artifact_hashes(run_dir) != response_manifest[
        "artifacts"
    ]:
        raise ValueError(f"response artifact hash mismatch: {run_dir}")
    analysis_manifest = json.loads(
        analysis_manifest_path.read_text(encoding="utf-8")
    )
    expected_analysis_kind = (
        "controlled_instrument_analysis_v1"
        if controlled_scenario
        else "frozen_curated_measurement_world_analysis_v1"
    )
    if (
        analysis_manifest.get("analysis_kind") != expected_analysis_kind
        or analysis_manifest.get("controlled_scenario") is not controlled_scenario
        or analysis_manifest.get("scenario_kind") != plan["scenario_kind"]
        or analysis_manifest.get("world_id") != world_id
        or analysis_manifest.get("policy_id") != policy_id
        or analysis_manifest.get("seed") != seed
    ):
        raise ValueError(f"analysis scenario mode mismatch: {run_dir}")
    _validate_retained_claim_boundary(
        analysis_manifest,
        controlled_scenario=controlled_scenario,
        artifact="analysis",
    )
    if analysis_manifest["response_run_manifest_sha256"] != sha256_file(
        response_manifest_path
    ):
        raise ValueError(f"analysis references changed response run: {run_dir}")
    if _artifact_hashes(
        analysis_dir, excluded={"analysis_manifest.json"}
    ) != analysis_manifest["artifacts"]:
        raise ValueError(f"analysis artifact hash mismatch: {analysis_dir}")
    models = json.loads(
        (analysis_dir / "model_results.json").read_text(encoding="utf-8")
    )
    predictions = read_jsonl(analysis_dir / "test_predictions.jsonl.gz")
    return models, predictions


def _mean_min_max(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        raise ValueError("seed summary cannot be empty")
    return {
        "n_seeds": len(values),
        "mean": float(np.mean(values)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "values": [float(value) for value in values],
    }


def _learner_log_losses(
    rows: Sequence[Mapping[str, Any]], condition: str
) -> dict[str, float]:
    by_learner: dict[str, list[float]] = defaultdict(list)
    field = f"probability_{condition}"
    for row in rows:
        if row["grammar_regime"] != "seen":
            continue
        probability = min(1 - 1e-9, max(1e-9, float(row[field])))
        target = int(row["correct"])
        loss = -(target * math.log(probability) + (1 - target) * math.log(1 - probability))
        by_learner[str(row["learner_id"])].append(loss)
    return {learner: fmean(values) for learner, values in by_learner.items()}


def _bootstrap_scalar_by_learner(
    values: Mapping[str, float], *, repeats: int, seed: int
) -> dict[str, Any]:
    learners = sorted(values)
    vector = np.asarray([values[learner] for learner in learners], dtype=float)
    if not learners or repeats < 1:
        raise ValueError("cross-world bootstrap needs learners and repeats")
    rng = np.random.default_rng(seed)
    draws = np.asarray(
        [
            float(np.mean(vector[rng.integers(0, len(vector), size=len(vector))]))
            for _ in range(repeats)
        ]
    )
    return {
        "learners": len(learners),
        "repeats": repeats,
        "point_estimate": float(np.mean(vector)),
        "percentile_95": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
    }


def aggregate_planned_results(
    output_dir: Path, *, controlled_scenario: bool = False
) -> dict[str, Any]:
    """Aggregate frozen seed/world evidence and primary cross-world contrasts."""

    plan, config, _, _ = validate_run_plan(
        output_dir, controlled_scenario=controlled_scenario
    )
    if controlled_scenario:
        require_canonical_controlled_output(output_dir, config)
    aggregate_dir = output_dir / "aggregate"
    if aggregate_dir.exists():
        raise FileExistsError(f"refusing to overwrite aggregate: {aggregate_dir}")
    seeds = [int(seed) for seed in plan["seeds"]]
    worlds = list(plan["world_ids"])
    policies = list(plan["policies"])
    cache: dict[tuple[str, int], tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for world_id in worlds:
        for seed in seeds:
            cache[(world_id, seed)] = _validated_analysis_bundle(
                output_dir,
                world_id=world_id,
                policy_id="q_balanced_lab",
                seed=seed,
                controlled_scenario=controlled_scenario,
            )

    condition_world_seed = {
        world_id: {
            str(seed): {
                condition: cache[(world_id, seed)][0]["conditions"][condition][
                    "metrics"
                ]["log_loss"]
                for condition in MODEL_CONDITIONS
            }
            for seed in seeds
        }
        for world_id in worlds
    }
    condition_world_summary = {
        world_id: {
            condition: _mean_min_max(
                [
                    condition_world_seed[world_id][str(seed)][condition]
                    for seed in seeds
                ]
            )
            for condition in MODEL_CONDITIONS
        }
        for world_id in worlds
    }
    contrast_terms = {
        "format_confounding_difference_in_differences": [
            ("format_strong_control", "B", 1.0),
            ("format_strong_control", "A", -1.0),
            ("clean_zero", "B", -1.0),
            ("clean_zero", "A", 1.0),
        ],
        "explicit_format_remedy": [
            ("format_strong_control", "C", 1.0),
            ("format_strong_control", "B", -1.0),
        ],
        "explicit_item_remedy_item_only": [
            ("item_moderate", "D", 1.0),
            ("item_moderate", "C", -1.0),
        ],
        "explicit_item_remedy_combined": [
            ("item_format_moderate", "D", 1.0),
            ("item_format_moderate", "C", -1.0),
        ],
    }
    repeats = int(config["evaluation"]["bootstrap"]["repeats"])
    contrasts: dict[str, Any] = {}
    for contrast_index, (contrast_id, terms) in enumerate(contrast_terms.items(), start=1):
        per_seed = {}
        for seed in seeds:
            term_losses = [
                (
                    coefficient,
                    _learner_log_losses(cache[(world_id, seed)][1], condition),
                )
                for world_id, condition, coefficient in terms
            ]
            learner_sets = [set(values) for _, values in term_losses]
            if any(values != learner_sets[0] for values in learner_sets[1:]):
                raise ValueError(f"cross-world learner split drift for {contrast_id}/{seed}")
            learner_values = {
                learner: sum(
                    coefficient * values[learner]
                    for coefficient, values in term_losses
                )
                for learner in sorted(learner_sets[0])
            }
            per_seed[str(seed)] = _bootstrap_scalar_by_learner(
                learner_values,
                repeats=repeats,
                seed=20260830 + contrast_index * 100 + seed % 100,
            )
        contrasts[contrast_id] = {
            "terms": [
                {"world_id": world, "condition": condition, "coefficient": coefficient}
                for world, condition, coefficient in terms
            ],
            "delta_sign": "negative favours the explicitly corrected candidate where applicable",
            "per_seed": per_seed,
            "across_seed_point_estimate": _mean_min_max(
                [per_seed[str(seed)]["point_estimate"] for seed in seeds]
            ),
        }

    terminal_state = {
        world_id: {
            "per_seed_rmse": {
                str(seed): cache[(world_id, seed)][0][
                    "terminal_kc_state_recovery_secondary"
                ]["rmse"]
                for seed in seeds
            },
            "summary": _mean_min_max(
                [
                    cache[(world_id, seed)][0][
                        "terminal_kc_state_recovery_secondary"
                    ]["rmse"]
                    for seed in seeds
                ]
            ),
        }
        for world_id in worlds
    }

    schedule_rows = []
    for policy_id in policies:
        for seed in seeds:
            run_dir = output_dir / "runs" / _run_name(
                "combined_heterogeneous", policy_id, seed
            )
            manifest_path = run_dir / "run_manifest.json"
            diagnostic_path = run_dir / "observable_diagnostics.json"
            if not manifest_path.is_file() or not diagnostic_path.is_file():
                raise FileNotFoundError(
                    f"planned schedule response/diagnostic missing: {run_dir}"
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_kind = (
                "controlled_instrument_response_only"
                if controlled_scenario
                else "confirmatory_curated_response_only"
            )
            if (
                manifest.get("run_kind") != expected_kind
                or manifest.get("controlled_scenario") is not controlled_scenario
                or manifest.get("scenario_kind") != plan["scenario_kind"]
                or manifest.get("world_id") != "combined_heterogeneous"
                or manifest.get("policy_id") != policy_id
                or manifest.get("seed") != seed
                or manifest.get("study_plan_sha256")
                != sha256_file(output_dir / "study_plan.json")
            ):
                raise ValueError(f"schedule response scenario identity mismatch: {run_dir}")
            _validate_retained_claim_boundary(
                manifest,
                controlled_scenario=controlled_scenario,
                artifact="response",
            )
            if _response_artifact_hashes(run_dir) != manifest[
                "artifacts"
            ]:
                raise ValueError(f"schedule response hash mismatch: {run_dir}")
            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            schedule_rows.append(
                {
                    "policy_id": policy_id,
                    "seed": seed,
                    "overall_accuracy": diagnostic["overall_accuracy"],
                    "item_exposure_gini": diagnostic["acquisition_item_exposure"]["gini"],
                    "zero_exposure_items": diagnostic["acquisition_item_exposure"][
                        "zero_exposure_items"
                    ],
                    "kc_exposure_gini_design_linked": diagnostic[
                        "acquisition_kc_exposure"
                    ]["gini"],
                    "median_repetition_gap": diagnostic["repetition_gap"]["median"],
                    "median_adjacent_q_jaccard_design_linked": diagnostic[
                        "adjacent_q_jaccard"
                    ]["median"],
                }
            )
    schedule_summary = {
        policy_id: {
            metric: _mean_min_max(
                [
                    float(row[metric])
                    for row in schedule_rows
                    if row["policy_id"] == policy_id and row[metric] is not None
                ]
            )
            for metric in (
                "overall_accuracy",
                "item_exposure_gini",
                "zero_exposure_items",
                "kc_exposure_gini_design_linked",
                "median_repetition_gap",
                "median_adjacent_q_jaccard_design_linked",
            )
        }
        for policy_id in policies
    }
    result = {
        "study_id": plan["study_id"],
        "scenario_kind": plan["scenario_kind"],
        "controlled_scenario": controlled_scenario,
        "release_eligible": False if controlled_scenario else None,
        "primary_scope": "seen_terminal_probes",
        "policy_for_model_contrasts": "q_balanced_lab",
        "seeds": seeds,
        "condition_world_seed_log_loss": condition_world_seed,
        "condition_world_summary": condition_world_summary,
        "primary_cross_world_contrasts": contrasts,
        "terminal_kc_state_recovery_secondary": terminal_state,
        "schedule_diagnostics_per_seed": schedule_rows,
        "schedule_diagnostics_summary": schedule_summary,
    }
    staging = Path(tempfile.mkdtemp(prefix=".aggregate.incomplete.", dir=output_dir))
    write_frozen_json(staging / "results.json", result, "aggregate results")
    aggregate_manifest = {
        "aggregate_kind": (
            "controlled_instrument_cross_scenario_v1"
            if controlled_scenario
            else "curated_measurement_world_cross_scenario_v1"
        ),
        "scenario_kind": plan["scenario_kind"],
        "controlled_scenario": controlled_scenario,
        "release_eligible": False if controlled_scenario else None,
        "study_plan_sha256": sha256_file(output_dir / "study_plan.json"),
        "artifacts": _artifact_hashes(staging, excluded={"manifest.json"}),
    }
    write_frozen_json(staging / "manifest.json", aggregate_manifest, "aggregate manifest")
    staging.rename(aggregate_dir)
    return aggregate_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        required=True,
        choices=(
            "validate-config",
            "make-fixture",
            "validate-bank",
            "validate-instrument",
            "plan",
            "validate-plan",
            "run",
            "analyze",
            "aggregate",
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--world", default="clean_zero")
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--policy", default="q_balanced_lab")
    parser.add_argument("--learner-count", type=int)
    parser.add_argument(
        "--controlled-scenario",
        action="store_true",
        help=(
            "required for the non-release, content-free controlled-instrument "
            "path; prohibited for the production curated-bank path"
        ),
    )
    args = parser.parse_args()

    config = load_executable_config(args.config)
    controlled = is_controlled_config(config)
    if controlled != args.controlled_scenario:
        parser.error(
            "config/runner mode mismatch: controlled config requires, and the "
            "production config prohibits, --controlled-scenario"
        )
    if controlled and args.stage in {
        "plan",
        "validate-plan",
        "run",
        "analyze",
        "aggregate",
    }:
        if args.output_dir.resolve() != controlled_output_dir(config):
            parser.error(
                "controlled plan/response/analysis stages require the isolated "
                f"output directory {controlled_output_dir(config)}"
            )
    selected = load_selected_cells(config)
    if args.stage == "validate-config":
        print(canonical_json({"design_id": config["design_id"], "status": config["status"]}))
        return
    if args.stage == "make-fixture":
        if controlled:
            parser.error("fixture creation belongs only to the production contract tests")
        target = args.bank or args.output_dir / "synthetic_fixture_items.jsonl"
        fixture = build_synthetic_bank_fixture(selected, config)
        validate_curated_bank(fixture, selected, config, fixture=True)
        if target.exists():
            raise FileExistsError(f"refusing to overwrite fixture: {target}")
        write_jsonl(target, fixture, gzip_output=False)
        print(target)
        return
    if args.bank is None and args.stage in {
        "validate-bank",
        "validate-instrument",
        "plan",
    }:
        parser.error(f"--bank is required for --stage {args.stage}")
    if args.stage == "validate-bank":
        if controlled:
            parser.error("controlled slots cannot pass the production curated-bank gate")
        schema_path = _resolve(
            ROOT, config["frozen_overlay"]["curated_bank_contract"]["schema_path"]
        )
        audit = validate_curated_bank(
            read_jsonl(args.bank), selected, config, schema_path=schema_path, fixture=False
        )
        evidence = validate_frozen_curated_bank_evidence(
            args.bank, expected_schema_path=schema_path
        )
        print(
            canonical_json(
                {
                    "row_contract": {
                        key: value for key, value in audit.items() if key != "items"
                    },
                    "freeze_evidence": evidence,
                }
            )
        )
        return
    if args.stage == "validate-instrument":
        if not controlled:
            parser.error("validate-instrument requires the controlled-scenario config")
        expected = Path(config["_paths"]["controlled_instrument"]).resolve()
        if args.bank.resolve() != expected:
            parser.error("validate-instrument requires the frozen instrument path")
        audit = validate_controlled_instrument(
            read_jsonl(args.bank),
            selected,
            config,
            schema_path=Path(config["_paths"]["controlled_instrument_schema"]),
        )
        print(canonical_json({key: value for key, value in audit.items() if key != "items"}))
        return
    if args.stage == "plan":
        plan = create_run_plan(
            config_path=args.config.resolve(),
            bank_path=args.bank.resolve(),
            output_dir=args.output_dir.resolve(),
            controlled_scenario=args.controlled_scenario,
        )
        print(canonical_json({"status": plan["status"], "budget": plan["frozen_acquisition_budget"]}))
        return
    if args.stage == "validate-plan":
        plan, _, _, _ = validate_run_plan(
            args.output_dir.resolve(),
            controlled_scenario=args.controlled_scenario,
        )
        print(
            canonical_json(
                {
                    "status": plan["status"],
                    "study_id": plan["study_id"],
                    "budget": plan["frozen_acquisition_budget"],
                    "study_plan_sha256": sha256_file(
                        args.output_dir.resolve() / "study_plan.json"
                    ),
                }
            )
        )
        return
    if args.stage == "run":
        manifest = run_planned_world(
            args.output_dir.resolve(),
            world_id=args.world,
            seed=args.seed,
            policy_id=args.policy,
            learner_count=args.learner_count,
            controlled_scenario=args.controlled_scenario,
        )
    elif args.stage == "analyze":
        if args.learner_count is not None:
            parser.error("--learner-count is not valid for the frozen analysis stage")
        manifest = analyze_planned_world(
            args.output_dir.resolve(),
            world_id=args.world,
            seed=args.seed,
            policy_id=args.policy,
            controlled_scenario=args.controlled_scenario,
        )
    else:
        manifest = aggregate_planned_results(
            args.output_dir.resolve(),
            controlled_scenario=args.controlled_scenario,
        )
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
