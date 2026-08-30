"""Streaming and tamper-evident freezing for a baseline Grammar-KT dataset.

The mechanisms here are deliberately schema-driven.  They know the frozen
observable and private-oracle row contracts, but they do not inspect English
grammar values, discovered KCs, KT predictions, or learner outcomes from any
other source.  Observable and oracle rows are consumed as aligned pairs and
written directly to deterministic gzip streams.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from errno import EEXIST
from pathlib import Path
from typing import Any

from .baseline_simulation import OBSERVABLE_FIELDS, ORACLE_FIELDS


SHARED_STREAM_FIELDS = (
    "learner_id",
    "item_id",
    "sequence_index",
    "phase",
    "pass_index",
    "grammar_regime",
    "correct",
)


def file_sha256(path: str | Path) -> str:
    """Hash one retained file without loading it into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def semantic_sha256(value: Any) -> str:
    """Hash JSON semantics independently of incidental formatting."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Render a small inspectable JSON artifact deterministically."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_row_bytes(row: Mapping[str, Any], fields: Sequence[str]) -> bytes:
    if tuple(row) != tuple(fields):
        raise ValueError(
            "row fields differ from the frozen schema: "
            f"expected={list(fields)}, actual={list(row)}"
        )
    ordered = {field: row[field] for field in fields}
    return (
        json.dumps(
            ordered,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_new_bytes(path: Path, payload: bytes, label: str) -> None:
    """Create one immutable small artifact, refusing changed retained bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite changed frozen {label}: {path}")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        try:
            # The hard-link install is atomic and, unlike os.replace(), can
            # never overwrite a target created by another process after the
            # existence check above.  Temporary and target are deliberately
            # in the same directory/filesystem.
            os.link(temporary, path)
        except OSError as error:
            if error.errno != EEXIST:
                raise
            if (
                not path.is_file()
                or path.is_symlink()
                or path.read_bytes() != payload
            ):
                raise ValueError(
                    f"refusing to overwrite changed frozen {label}: {path}"
                ) from error
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def freeze_json(path: str | Path, value: Any, label: str) -> None:
    _atomic_new_bytes(Path(path), canonical_json_bytes(value), label)


def freeze_text(path: str | Path, value: str, label: str) -> None:
    payload = value.encode("utf-8")
    _atomic_new_bytes(Path(path), payload, label)


def freeze_copy(source: str | Path, target: str | Path, label: str) -> None:
    _atomic_new_bytes(Path(target), Path(source).read_bytes(), label)


def _fsync_directory(path: Path) -> None:
    """Make a completed same-directory link/unlink durable where supported."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stream_contract(
    items: Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    item_cell: dict[str, str] = {}
    for index, item in enumerate(items):
        item_id = item.get("item_id")
        cell_id = item.get("cell_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"item row {index} has an invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"item {item_id} has an invalid cell_id")
        if item_id in item_cell:
            raise ValueError(f"duplicate fixed item ID: {item_id}")
        item_cell[item_id] = cell_id

    active_by_item: dict[str, tuple[str, ...]] = {}
    for index, row in enumerate(q_rows):
        item_id = row.get("item_id")
        active = row.get("generator_kc_ids")
        if item_id not in item_cell:
            raise ValueError(f"Q* row {index} refers to an unknown item: {item_id}")
        if item_id in active_by_item:
            raise ValueError(f"duplicate Q* row for item: {item_id}")
        if (
            not isinstance(active, Sequence)
            or isinstance(active, (str, bytes))
            or not active
            or any(not isinstance(kc_id, str) or not kc_id for kc_id in active)
            or len(active) != len(set(active))
        ):
            raise ValueError(f"Q* item {item_id} has invalid generator KC edges")
        active_by_item[str(item_id)] = tuple(sorted(active))
    if set(active_by_item) != set(item_cell):
        raise ValueError("Q* rows must cover exactly the fixed item bank")

    missing_regimes = set(item_cell.values()) - set(grammar_regime_by_cell)
    if missing_regimes:
        raise ValueError(
            f"item cells are missing grammar regimes: {sorted(missing_regimes)}"
        )
    regime_by_item = {
        item_id: grammar_regime_by_cell[cell_id]
        for item_id, cell_id in item_cell.items()
    }
    acquisition_regime = config["schedule"]["acquisition_regime"]
    seen_item_ids = {
        item_id
        for item_id, regime in regime_by_item.items()
        if regime == acquisition_regime
    }
    seen_kc_ids = {
        kc_id
        for item_id in seen_item_ids
        for kc_id in active_by_item[item_id]
    }
    if not seen_item_ids or not seen_kc_ids:
        raise ValueError("baseline stream contract needs seen items and seen KCs")
    return {
        "item_ids": set(item_cell),
        "active_by_item": active_by_item,
        "regime_by_item": regime_by_item,
        "acquisition_regime": acquisition_regime,
        "seen_item_ids": seen_item_ids,
        "seen_kc_ids": seen_kc_ids,
        "learners": int(config["learners"]),
        "learner_prefix": config["learner_ids"]["prefix"],
        "learner_width": int(config["learner_ids"]["zero_pad_width"]),
        "probe_repeats": int(config["schedule"]["probe"]["repeats"]),
        "target_seen_kc_opportunities": int(
            config["schedule"]["acquisition"][
                "target_opportunities_per_seen_kc"
            ]
        ),
        "guess": float(config["response"]["guess"]),
        "slip": float(config["response"]["slip"]),
        "learning_rate": float(config["learning"]["rate"]),
    }


def _new_integrity_state(contract: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract": contract,
        "current_learner": None,
        "current_sequence": 0,
        "current_acquisition_items": Counter(),
        "current_acquisition_kcs": Counter(),
        "current_probes": Counter(),
        "current_mastery": {},
        "current_probe_started": False,
        "reference_acquisition_items": None,
        "reference_acquisition_kcs": None,
        "reference_rows_per_learner": None,
        "learners": 0,
        "rows": 0,
        "phase_counts": Counter(),
        "grammar_regime_counts": Counter(),
        "phase_regime_counts": Counter(),
        "correct_counts": Counter(),
        "pair_link_digest": hashlib.sha256(),
    }


def _numeric_probability(value: Any, label: str, *, upper_inclusive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    upper_ok = result <= 1.0 if upper_inclusive else result < 1.0
    if not math.isfinite(result) or result < 0.0 or not upper_ok:
        boundary = "[0, 1]" if upper_inclusive else "[0, 1)"
        raise ValueError(f"{label} must lie in {boundary}")
    return result


def _finish_current_learner(state: dict[str, Any]) -> None:
    learner_id = state["current_learner"]
    if learner_id is None:
        return
    contract = state["contract"]
    acquisition_items: Counter[str] = state["current_acquisition_items"]
    acquisition_kcs: Counter[str] = state["current_acquisition_kcs"]
    probes: Counter[tuple[int, str]] = state["current_probes"]

    missing_seen_items = contract["seen_item_ids"] - set(acquisition_items)
    if missing_seen_items or min(acquisition_items.values(), default=0) < 1:
        raise ValueError(
            f"learner {learner_id} lacks exhaustive seen-item coverage: "
            f"{sorted(missing_seen_items)}"
        )
    below_target = sorted(
        kc_id
        for kc_id in contract["seen_kc_ids"]
        if acquisition_kcs[kc_id] < contract["target_seen_kc_opportunities"]
    )
    if below_target:
        raise ValueError(
            f"learner {learner_id} has seen KCs below the acquisition target: "
            f"{below_target}"
        )
    expected_probes = Counter(
        (repeat, item_id)
        for repeat in range(1, contract["probe_repeats"] + 1)
        for item_id in contract["item_ids"]
    )
    if probes != expected_probes:
        raise ValueError(f"learner {learner_id} probe coverage differs from the bank")

    if state["reference_acquisition_items"] is None:
        state["reference_acquisition_items"] = acquisition_items.copy()
        state["reference_acquisition_kcs"] = acquisition_kcs.copy()
        state["reference_rows_per_learner"] = state["current_sequence"]
    elif (
        acquisition_items != state["reference_acquisition_items"]
        or acquisition_kcs != state["reference_acquisition_kcs"]
        or state["current_sequence"] != state["reference_rows_per_learner"]
    ):
        raise ValueError("learners do not share identical item/KC opportunity counts")


def _start_learner(state: dict[str, Any], learner_id: str) -> None:
    _finish_current_learner(state)
    contract = state["contract"]
    state["learners"] += 1
    expected = (
        f"{contract['learner_prefix']}"
        f"{state['learners']:0{contract['learner_width']}d}"
    )
    if learner_id != expected:
        raise ValueError(
            f"learner stream order differs: expected {expected}, found {learner_id}"
        )
    state["current_learner"] = learner_id
    state["current_sequence"] = 0
    state["current_acquisition_items"] = Counter()
    state["current_acquisition_kcs"] = Counter()
    state["current_probes"] = Counter()
    state["current_mastery"] = {}
    state["current_probe_started"] = False


def _observe_pair(
    state: dict[str, Any],
    interaction: Mapping[str, Any],
    oracle: Mapping[str, Any],
) -> None:
    if tuple(interaction) != OBSERVABLE_FIELDS:
        raise ValueError("observable row schema drift")
    if tuple(oracle) != ORACLE_FIELDS:
        raise ValueError("private oracle row schema drift")
    for field in SHARED_STREAM_FIELDS:
        if interaction[field] != oracle[field]:
            raise ValueError(f"observable/oracle rows disagree on {field}")

    learner_id = interaction["learner_id"]
    if not isinstance(learner_id, str) or not learner_id:
        raise ValueError("learner_id must be a non-empty string")
    if learner_id != state["current_learner"]:
        _start_learner(state, learner_id)
    state["current_sequence"] += 1
    if interaction["sequence_index"] != state["current_sequence"]:
        raise ValueError(f"non-contiguous sequence for learner {learner_id}")

    contract = state["contract"]
    item_id = interaction["item_id"]
    if item_id not in contract["item_ids"]:
        raise ValueError(f"event refers to unknown item: {item_id}")
    expected_regime = contract["regime_by_item"][item_id]
    if interaction["grammar_regime"] != expected_regime:
        raise ValueError(f"event grammar regime differs for item: {item_id}")
    correct = interaction["correct"]
    if isinstance(correct, bool) or correct not in {0, 1}:
        raise ValueError("correct must be integer zero or one")
    pass_index = interaction["pass_index"]
    if isinstance(pass_index, bool) or not isinstance(pass_index, int) or pass_index < 1:
        raise ValueError("pass_index must be a positive integer")

    phase = interaction["phase"]
    if phase == "acquisition":
        if state["current_probe_started"]:
            raise ValueError("acquisition cannot occur after terminal probes begin")
        if expected_regime != contract["acquisition_regime"]:
            raise ValueError("acquisition contains a non-seen grammar item")
        state["current_acquisition_items"][item_id] += 1
        if pass_index != state["current_acquisition_items"][item_id]:
            raise ValueError("acquisition pass_index differs from item exposure index")
        state["current_acquisition_kcs"].update(
            oracle["active_generator_kc_ids"]
        )
        if oracle["updates_mastery"] is not True:
            raise ValueError("acquisition event does not update mastery")
    elif phase == "probe":
        state["current_probe_started"] = True
        if pass_index > contract["probe_repeats"]:
            raise ValueError("probe pass_index exceeds configured repeats")
        state["current_probes"][(pass_index, item_id)] += 1
        if oracle["updates_mastery"] is not False:
            raise ValueError("terminal probe updates mastery")
    else:
        raise ValueError(f"unknown baseline phase: {phase}")

    active = oracle["active_generator_kc_ids"]
    if not isinstance(active, list) or tuple(active) != contract["active_by_item"][item_id]:
        raise ValueError(f"oracle active KCs differ from Q* for item: {item_id}")
    before = oracle["mastery_before"]
    after = oracle["mastery_after"]
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("oracle mastery states must be mappings")
    if list(before) != active or list(after) != active:
        raise ValueError("oracle mastery scope/order differs from active generator KCs")
    before_values = {
        kc_id: _numeric_probability(
            before[kc_id], f"mastery_before[{kc_id}]", upper_inclusive=True
        )
        for kc_id in active
    }
    after_values = {
        kc_id: _numeric_probability(
            after[kc_id], f"mastery_after[{kc_id}]", upper_inclusive=True
        )
        for kc_id in active
    }
    for kc_id, value in before_values.items():
        previous = state["current_mastery"].get(kc_id)
        if previous is not None and value != previous:
            raise ValueError(f"oracle mastery trajectory breaks for {kc_id}")

    aggregated = _numeric_probability(
        oracle["aggregated_mastery_before"],
        "aggregated_mastery_before",
        upper_inclusive=True,
    )
    if aggregated != min(before_values.values()):
        raise ValueError("oracle aggregation is not the minimum active mastery")
    probability = _numeric_probability(
        oracle["response_probability"],
        "response_probability",
        upper_inclusive=True,
    )
    expected_probability = (
        contract["guess"]
        + (1.0 - contract["guess"] - contract["slip"]) * aggregated
    )
    if probability != expected_probability:
        raise ValueError("oracle response probability differs from baseline semantics")
    response_draw = _numeric_probability(
        oracle["response_draw"], "response_draw", upper_inclusive=False
    )
    if correct != int(response_draw < probability):
        raise ValueError("observable correctness differs from the oracle draw")

    for kc_id, value in before_values.items():
        expected_after = (
            value + contract["learning_rate"] * (1.0 - value)
            if phase == "acquisition"
            else value
        )
        if after_values[kc_id] != expected_after:
            raise ValueError(f"oracle learning update differs for {kc_id}")
        state["current_mastery"][kc_id] = after_values[kc_id]

    shared = [interaction[field] for field in SHARED_STREAM_FIELDS]
    state["pair_link_digest"].update(
        (
            json.dumps(
                shared,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    state["rows"] += 1
    state["phase_counts"][phase] += 1
    state["grammar_regime_counts"][expected_regime] += 1
    state["phase_regime_counts"][(phase, expected_regime)] += 1
    state["correct_counts"][phase] += correct


def _finalize_integrity(state: dict[str, Any]) -> dict[str, Any]:
    _finish_current_learner(state)
    contract = state["contract"]
    if state["learners"] != contract["learners"]:
        raise ValueError(
            f"learner count differs: {state['learners']} != {contract['learners']}"
        )
    if not state["rows"]:
        raise ValueError("baseline stream contains no rows")
    acquisition_items: Counter[str] = state["reference_acquisition_items"]
    acquisition_kcs: Counter[str] = state["reference_acquisition_kcs"]
    return {
        "rows": state["rows"],
        "learners": state["learners"],
        "rows_per_learner": state["reference_rows_per_learner"],
        "phase_counts": dict(sorted(state["phase_counts"].items())),
        "grammar_regime_counts": dict(
            sorted(state["grammar_regime_counts"].items())
        ),
        "phase_by_grammar_regime_counts": {
            f"{phase}__{regime}": count
            for (phase, regime), count in sorted(
                state["phase_regime_counts"].items()
            )
        },
        "correct_counts_by_phase": dict(sorted(state["correct_counts"].items())),
        "acquisition": {
            "rows_per_learner": sum(acquisition_items.values()),
            "seen_item_exposures_per_learner": dict(sorted(acquisition_items.items())),
            "seen_kc_opportunities_per_learner": dict(sorted(acquisition_kcs.items())),
            "minimum_seen_kc_opportunities": min(acquisition_kcs.values()),
            "target_seen_kc_opportunities": contract[
                "target_seen_kc_opportunities"
            ],
        },
        "probe": {
            "rows_per_learner": len(contract["item_ids"])
            * contract["probe_repeats"],
            "repeats": contract["probe_repeats"],
            "fixed_items_per_repeat": len(contract["item_ids"]),
            "updates_mastery": False,
        },
        "schemas": {
            "observable": list(OBSERVABLE_FIELDS),
            "private_oracle": list(ORACLE_FIELDS),
        },
        "observable_oracle_pair_link_sha256": state[
            "pair_link_digest"
        ].hexdigest(),
        "observable_has_oracle_fields": False,
        "paired_rows_verified": True,
    }


def _temporary_file(target: Path) -> tuple[int, Path]:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".partial", dir=target.parent
    )
    return descriptor, Path(name)


def _install_paired_outputs(
    temporary_targets: Sequence[tuple[Path, Path, str]],
) -> None:
    """Install each stream atomically without overwrite, with replay recovery.

    No filesystem offers one atomic rename for two files.  A crash between the
    two installs can therefore leave one complete stream, but never a partial
    file or a complete dataset manifest.  Deterministic replay verifies the
    retained member and installs only its missing pair.
    """

    for temporary, target, label in temporary_targets:
        if target.exists():
            if (
                not target.is_file()
                or target.is_symlink()
                or target.stat().st_size != temporary.stat().st_size
                or file_sha256(target) != file_sha256(temporary)
            ):
                raise ValueError(
                    f"refusing to overwrite changed frozen {label}: {target}"
                )
    for temporary, target, _label in temporary_targets:
        if target.exists():
            temporary.unlink()
        else:
            temporary.chmod(0o644)
            try:
                os.link(temporary, target)
            except OSError as error:
                if error.errno != EEXIST:
                    raise
                if (
                    not target.is_file()
                    or target.is_symlink()
                    or target.stat().st_size != temporary.stat().st_size
                    or file_sha256(target) != file_sha256(temporary)
                ):
                    raise ValueError(
                        "refusing to overwrite changed frozen "
                        f"{_label}: {target}"
                    ) from error
            temporary.unlink()
            _fsync_directory(target.parent)


def write_baseline_streams(
    interactions_path: str | Path,
    oracle_path: str | Path,
    row_pairs: Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]],
    *,
    items: Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Write aligned rows once, directly to deterministic atomic gzip files."""

    interactions_target = Path(interactions_path)
    oracle_target = Path(oracle_path)
    contract = _stream_contract(items, q_rows, grammar_regime_by_cell, config)
    state = _new_integrity_state(contract)
    interaction_digest = hashlib.sha256()
    oracle_digest = hashlib.sha256()
    interaction_fd, interaction_temp = _temporary_file(interactions_target)
    oracle_fd, oracle_temp = _temporary_file(oracle_target)
    try:
        with os.fdopen(interaction_fd, "wb") as interaction_raw, os.fdopen(
            oracle_fd, "wb"
        ) as oracle_raw:
            with gzip.GzipFile(
                filename="",
                fileobj=interaction_raw,
                mode="wb",
                compresslevel=9,
                mtime=0,
            ) as interaction_gzip, gzip.GzipFile(
                filename="",
                fileobj=oracle_raw,
                mode="wb",
                compresslevel=9,
                mtime=0,
            ) as oracle_gzip:
                for interaction, oracle in row_pairs:
                    _observe_pair(state, interaction, oracle)
                    interaction_payload = _canonical_row_bytes(
                        interaction, OBSERVABLE_FIELDS
                    )
                    oracle_payload = _canonical_row_bytes(oracle, ORACLE_FIELDS)
                    interaction_gzip.write(interaction_payload)
                    oracle_gzip.write(oracle_payload)
                    interaction_digest.update(interaction_payload)
                    oracle_digest.update(oracle_payload)
            interaction_raw.flush()
            oracle_raw.flush()
            os.fsync(interaction_raw.fileno())
            os.fsync(oracle_raw.fileno())

        integrity = _finalize_integrity(state)
        temporary_targets = (
            (interaction_temp, interactions_target, "observable interactions"),
            (oracle_temp, oracle_target, "private learner truth"),
        )
        _install_paired_outputs(temporary_targets)
        return {
            **integrity,
            "serialization": {
                "format": "canonical_compact_jsonl_gzip",
                "encoding": "utf-8",
                "gzip_mtime": 0,
                "gzip_filename": "",
                "gzip_compresslevel": 9,
            },
            "artifacts": {
                "interactions": {
                    "sha256": file_sha256(interactions_target),
                    "content_sha256": interaction_digest.hexdigest(),
                    "bytes": interactions_target.stat().st_size,
                    "rows": integrity["rows"],
                },
                "private_oracle": {
                    "sha256": file_sha256(oracle_target),
                    "content_sha256": oracle_digest.hexdigest(),
                    "bytes": oracle_target.stat().st_size,
                    "rows": integrity["rows"],
                },
            },
        }
    finally:
        for temporary in (interaction_temp, oracle_temp):
            if temporary.exists():
                temporary.unlink()


def verify_baseline_streams(
    interactions_path: str | Path,
    oracle_path: str | Path,
    *,
    items: Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    config: Mapping[str, Any],
    expected_summary: Mapping[str, Any] | None = None,
    expected_row_pairs: Iterable[
        tuple[Mapping[str, Any], Mapping[str, Any]]
    ]
    | None = None,
) -> dict[str, Any]:
    """Stream-verify retained rows, hashes, contracts, and optional exact replay."""

    interactions_target = Path(interactions_path)
    oracle_target = Path(oracle_path)
    if not interactions_target.is_file() or not oracle_target.is_file():
        raise FileNotFoundError("observable and private-oracle gzip streams are required")
    contract = _stream_contract(items, q_rows, grammar_regime_by_cell, config)
    state = _new_integrity_state(contract)
    interaction_digest = hashlib.sha256()
    oracle_digest = hashlib.sha256()
    replay = iter(expected_row_pairs) if expected_row_pairs is not None else None
    with gzip.open(interactions_target, "rb") as interactions, gzip.open(
        oracle_target, "rb"
    ) as oracles:
        while True:
            interaction_line = interactions.readline()
            oracle_line = oracles.readline()
            if not interaction_line and not oracle_line:
                break
            if not interaction_line or not oracle_line:
                raise ValueError("observable and oracle streams have different row counts")
            try:
                interaction = json.loads(interaction_line)
                oracle = json.loads(oracle_line)
            except json.JSONDecodeError as error:
                raise ValueError("invalid JSON in retained baseline stream") from error
            if interaction_line != _canonical_row_bytes(
                interaction, OBSERVABLE_FIELDS
            ) or oracle_line != _canonical_row_bytes(oracle, ORACLE_FIELDS):
                raise ValueError("retained baseline stream is not canonical JSONL")
            if replay is not None:
                try:
                    expected_interaction, expected_oracle = next(replay)
                except StopIteration as error:
                    raise ValueError(
                        "retained baseline stream has rows beyond deterministic replay"
                    ) from error
                if (
                    interaction != dict(expected_interaction)
                    or oracle != dict(expected_oracle)
                ):
                    raise ValueError(
                        "retained baseline row differs from deterministic replay"
                    )
            _observe_pair(state, interaction, oracle)
            interaction_digest.update(interaction_line)
            oracle_digest.update(oracle_line)
    if replay is not None:
        try:
            next(replay)
        except StopIteration:
            pass
        else:
            raise ValueError(
                "retained baseline stream ends before deterministic replay"
            )
    integrity = _finalize_integrity(state)
    summary = {
        **integrity,
        "serialization": {
            "format": "canonical_compact_jsonl_gzip",
            "encoding": "utf-8",
            "gzip_mtime": 0,
            "gzip_filename": "",
            "gzip_compresslevel": 9,
        },
        "artifacts": {
            "interactions": {
                "sha256": file_sha256(interactions_target),
                "content_sha256": interaction_digest.hexdigest(),
                "bytes": interactions_target.stat().st_size,
                "rows": integrity["rows"],
            },
            "private_oracle": {
                "sha256": file_sha256(oracle_target),
                "content_sha256": oracle_digest.hexdigest(),
                "bytes": oracle_target.stat().st_size,
                "rows": integrity["rows"],
            },
        },
    }
    if expected_summary is not None and summary != dict(expected_summary):
        raise ValueError("retained baseline stream summary differs from its manifest")
    return summary


def artifact_inventory(
    dataset_dir: str | Path,
    *,
    excluded_relative_paths: Iterable[str] = ("manifest.json",),
) -> dict[str, dict[str, Any]]:
    """Inventory every frozen file other than the self-referential manifest."""

    root = Path(dataset_dir).resolve()
    excluded = set(excluded_relative_paths)
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"dataset cannot contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if relative.endswith(".partial"):
            raise ValueError(f"dataset contains an incomplete artifact: {relative}")
        inventory[relative] = {
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    return inventory


def verify_artifact_inventory(
    dataset_dir: str | Path, expected: Mapping[str, Mapping[str, Any]]
) -> None:
    observed = artifact_inventory(dataset_dir)
    if observed != dict(expected):
        missing = sorted(set(expected) - set(observed))
        added = sorted(set(observed) - set(expected))
        changed = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        raise ValueError(
            "frozen dataset artifact inventory changed: "
            f"missing={missing}, added={added}, changed={changed}"
        )
