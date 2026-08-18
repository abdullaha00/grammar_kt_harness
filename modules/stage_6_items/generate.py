"""Generate only the current v0.1 candidates while preserving its frozen target order."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from modules.stage_6_items.helpers import item_id, nuisance_signature, render_prompt
from modules.stage_4_realization.engine import realize, validate_spec
from shared.utils.contracts import validate_jsonl, validate_value
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, require_new_directory, sha256_file, utc_now, write_json, write_jsonl
from shared.utils.manifests import describe, write_stage_manifest


TRANSITIVE = ("FRAME_INSPECT", "FRAME_WRITE", "FRAME_REPAIR")
SUBJECTS = (
    {"text": "the technician", "person": 3, "number": "singular"},
    {"text": "the technicians", "person": 3, "number": "plural"},
    {"text": "I", "person": 1, "number": "singular"},
    {"text": "we", "person": 1, "number": "plural"},
    {"text": "she", "person": 3, "number": "singular"},
)


def _sampling_item_id(kc_id: str, spec: dict[str, Any], replicate: int) -> str:
    basis = "|".join(
        (
            kc_id,
            spec["canonical_cell_id"],
            spec["source_descriptor_id"],
            spec["predicate_frame_id"],
            json.dumps(spec["subject"], sort_keys=True),
            str(spec["imperative_subtype"]),
            str(replicate),
        )
    )
    return "ITEM_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper()


def _sampling_frame(cell: dict[str, str], offset: int) -> str:
    if cell["modal"] == "would":
        return "FRAME_LIKE"
    if cell["voice"] == "passive":
        return ("FRAME_REPAIR", "FRAME_WRITE", "FRAME_INSPECT")[offset % 3]
    if cell["aspect"] in {"progressive", "perfect_progressive"}:
        return ("FRAME_WORK", "FRAME_WRITE", "FRAME_INSPECT")[offset % 3]
    return ("FRAME_INSPECT", "FRAME_WRITE", "FRAME_WORK")[offset % 3]


def _sampling_spec(
    kc_id: str,
    opportunity: dict[str, Any],
    replicate: int,
    offset: int,
    imperative_realizations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    cell = opportunity["cell"]
    if cell["clause"] == "imperative":
        choices = imperative_realizations[opportunity["canonical_cell_id"]]
        existing = choices[(replicate + offset) % len(choices)]["spec"]
        source_id = existing["source_descriptor_id"]
        subtype = existing["imperative_subtype"]
        let_pronoun = existing["let_pronoun"]
    else:
        source_id = opportunity["source_descriptor_ids"][(replicate + offset) % len(opportunity["source_descriptor_ids"])]
        subtype = None
        let_pronoun = None
    frame_id = _sampling_frame(cell, replicate + offset)
    subject = dict(SUBJECTS[(replicate + offset) % len(SUBJECTS)])
    if cell["voice"] == "passive":
        subject = (
            {"text": "the machine", "person": 3, "number": "singular"}
            if (replicate + offset) % 2 == 0
            else {"text": "the reports", "person": 3, "number": "plural"}
        )
    basis = f"{kc_id}|{opportunity['canonical_cell_id']}|{source_id}|{frame_id}|{subject}|{subtype}|{replicate}"
    return {
        "realization_id": "REAL_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
        "canonical_cell_id": opportunity["canonical_cell_id"],
        "source_descriptor_id": source_id,
        "predicate_frame_id": frame_id,
        "subject": subject,
        "wh": None,
        "imperative_subtype": subtype,
        "let_pronoun": let_pronoun,
    }


def _sampling_prompt_signature(cell: dict[str, str], spec: dict[str, Any], frame: dict[str, Any]) -> tuple[Any, ...]:
    """Exact value tuple that determined uniqueness/order before the accepted v0.1 materialization."""
    passive = cell["voice"] == "passive"
    return (
        tuple(cell.items()),
        spec["imperative_subtype"] or "NONE",
        spec["subject"]["text"],
        frame["lemma"].upper(),
        "NONE" if passive or frame["object"] is None else frame["object"],
        frame["complement"] or "NONE",
        spec["wh"]["phrase"] if spec["wh"] else "NONE",
        spec["let_pronoun"] or "NONE",
    )


def generate_candidates(
    *,
    projections: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    realizations: list[dict[str, Any]],
    cells: dict[str, dict[str, str]],
    mappings: dict[str, dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    template: str,
    template_hash: str,
    replicates: int,
    development_replicates: int,
) -> list[dict[str, Any]]:
    imperative_realizations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in realizations:
        if row["cell"]["clause"] == "imperative":
            imperative_realizations[row["spec"]["canonical_cell_id"]].append(row)
    for rows in imperative_realizations.values():
        rows.sort(key=lambda row: row["spec"]["realization_id"])
    by_kc = {card["kc_id"]: [row for row in projections if card["kc_id"] in row["kc_ids"]] for card in cards}
    frozen_targets = []
    used_signatures: set[tuple[Any, ...]] = set()
    for kc_offset, kc_id in enumerate(sorted(by_kc)):
        domain = sorted(by_kc[kc_id], key=lambda row: row["canonical_cell_id"])
        for replicate in range(replicates):
            opportunity = domain[(replicate + kc_offset) % len(domain)]
            for adjustment in range(15):
                spec = _sampling_spec(kc_id, opportunity, replicate, kc_offset + adjustment, imperative_realizations)
                frame = frames[spec["predicate_frame_id"]]
                if validate_spec(spec, opportunity["cell"], frame, mappings[spec["source_descriptor_id"]].get("note")):
                    continue
                signature = _sampling_prompt_signature(opportunity["cell"], spec, frame)
                if signature not in used_signatures:
                    break
            else:
                raise RuntimeError(f"could not construct frozen target for {kc_id} replicate {replicate}")
            used_signatures.add(signature)
            frozen_targets.append(
                {
                    "order_id": _sampling_item_id(kc_id, spec, replicate),
                    "primary_kc_id": kc_id,
                    "opportunity": opportunity,
                    "sampling_spec": spec,
                    "replicate": replicate,
                }
            )

    candidates: list[dict[str, Any]] = []
    used_prompts: set[str] = set()
    used_answers: set[str] = set()
    for serial, target in enumerate(sorted(frozen_targets, key=lambda row: row["order_id"])):
        opportunity = target["opportunity"]
        cell = cells[opportunity["canonical_cell_id"]]
        replicate = target["replicate"]
        prior_spec = target["sampling_spec"]
        for adjustment in range(30):
            frame_id = "FRAME_LIKE" if cell["modal"] == "would" else TRANSITIVE[(serial + replicate + adjustment) % len(TRANSITIVE)]
            frame = frames[frame_id]
            if cell["voice"] == "passive":
                subject = {"text": frame["object"], "person": 3, "number": "singular"}
            elif cell["clause"] == "imperative":
                subject = {"text": "you", "person": 2, "number": "singular"}
            else:
                subject = dict(SUBJECTS[(serial + replicate + adjustment) % len(SUBJECTS)])
            basis = f"v0.1|{target['primary_kc_id']}|{cell}|{frame_id}|{subject}|{prior_spec['source_descriptor_id']}|{replicate}"
            spec = {
                **prior_spec,
                "realization_id": "REAL_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
                "predicate_frame_id": frame_id,
                "subject": subject,
            }
            errors = validate_spec(spec, cell, frame, mappings[spec["source_descriptor_id"]].get("note"))
            if errors:
                continue
            derivation = realize(spec, cell, frame)
            prompt = render_prompt(template, cell, spec, frame)
            if prompt not in used_prompts and derivation["surface"] not in used_answers:
                break
        else:
            raise RuntimeError(f"could not construct unique current item for {target['order_id']}")
        used_prompts.add(prompt)
        used_answers.add(derivation["surface"])
        candidates.append(
            {
                "item_id": item_id(target["primary_kc_id"], spec, replicate),
                "source_descriptor_ids": opportunity["source_descriptor_ids"],
                "canonical_cell_id": opportunity["canonical_cell_id"],
                "realization_spec": spec,
                "item_family": "CONTROLLED_TRANSFORMATION_v0_1",
                "primary_kc_id": target["primary_kc_id"],
                "all_kc_ids": opportunity["kc_ids"],
                "prompt": prompt,
                "target_answer": derivation["surface"],
                "accepted_answers": [derivation["surface"]],
                "contrast_set_id": None,
                "generation_metadata": {
                    "generator": "scripts/generate_items_v0_1.py",
                    "generator_version": "v0.1",
                    "deterministic": True,
                    "replicate": replicate,
                    "split": "development" if replicate < development_replicates else "held_out",
                    "template_sha256": template_hash,
                    "model_used": None,
                    "lexical_search_offset": adjustment,
                },
                "validator_results": {"status": "pending"},
                "provenance": {
                    "opportunity_id": opportunity["opportunity_id"],
                    "realization_version": "v1",
                    "kc_projection_version": "v1",
                    "item_method_parent": "v0",
                    "item_method_version": "v0.1",
                    "parent_rewrite_or_adjudication": False,
                },
            }
        )
    assigned: set[str] = set()
    contrast_serial = 0
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if left["item_id"] in assigned or right["item_id"] in assigned:
                continue
            if nuisance_signature(left["realization_spec"]) != nuisance_signature(right["realization_spec"]):
                continue
            left_cell = cells[left["canonical_cell_id"]]
            right_cell = cells[right["canonical_cell_id"]]
            if sum(left_cell[key] != right_cell[key] for key in left_cell) == 1:
                contrast_serial += 1
                contrast_id = f"CONTRAST_V01_{contrast_serial:03d}"
                left["contrast_set_id"] = right["contrast_set_id"] = contrast_id
                assigned.update((left["item_id"], right["item_id"]))
                break
    if len({row["item_id"] for row in candidates}) != len(candidates):
        raise RuntimeError("current item IDs are not unique")
    return candidates


def run_generation(items_dir: Path, run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = items_dir / "generation"
    require_new_directory(output)
    projection_path = run_dir / "kc" / "cell_kc_projection.jsonl"
    inventory_path = run_dir / "kc" / "kc_inventory.jsonl"
    realizations_path = run_dir / "realization" / "realizations.jsonl"
    template_path = repo_path(config["generation"]["template"])
    lexicon_path = repo_path(config["_realization"]["lexicon"])
    rules_path = repo_path(config["_realization"]["rules"])
    activation_schema = ROOT / "modules/stage_5_kc/schemas/kc_activation.schema.json"
    kc_schema = ROOT / "modules/stage_5_kc/schemas/kc_spec.schema.json"
    realization_schema = ROOT / "modules/stage_4_realization/schemas/realization_spec_v0.schema.json"
    validate_jsonl(projection_path, activation_schema, label="items input KCActivation")
    validate_jsonl(inventory_path, kc_schema, label="items input KCSpec")
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(lexicon_path)}
    projections = read_jsonl(projection_path)
    cards = read_jsonl(inventory_path)
    realizations = read_jsonl(realizations_path)
    for row in realizations:
        validate_value(row.get("spec"), realization_schema, label="items input RealizationSpec")
    cells = {row["canonical_cell_id"]: row["cell"] for row in projections}
    mappings: dict[str, dict[str, Any]] = {}
    for row in projections:
        for source_id, note in row.get("source_mapping_notes", {}).items():
            mappings[source_id] = {"egp_id": source_id, "note": note}
        for source_id in row["source_descriptor_ids"]:
            mappings.setdefault(source_id, {"egp_id": source_id, "note": None})
    candidates = generate_candidates(
        projections=projections,
        cards=cards,
        realizations=realizations,
        cells=cells,
        mappings=mappings,
        frames=frames,
        template=template_path.read_text(encoding="utf-8"),
        template_hash=sha256_file(template_path),
        replicates=int(config["generation"]["replicates_per_kc"]),
        development_replicates=int(config["generation"]["development_replicates"]),
    )
    ordered = sorted(candidates, key=lambda row: row["item_id"])
    candidates_path = output / "candidate_items.jsonl"
    units_path = output / "validation_units.jsonl"
    write_jsonl(candidates_path, ordered)
    units = [
        {"validation_unit_id": f"IV1{index:02d}", "item_id": row["item_id"], "duplicate_of": None}
        for index, row in enumerate(ordered, 1)
    ]
    duplicate_items = [row for row in ordered if row["generation_metadata"]["split"] == "held_out"][:5]
    originals = {unit["item_id"]: unit["validation_unit_id"] for unit in units}
    for offset, row in enumerate(duplicate_items, len(units) + 1):
        units.append(
            {
                "validation_unit_id": f"IV1{offset:02d}",
                "item_id": row["item_id"],
                "duplicate_of": originals[row["item_id"]],
            }
        )
    write_jsonl(units_path, units)
    opportunities = {row["opportunity_id"]: row for row in projections}
    cards_by_id = {row["kc_id"]: row for row in cards}
    realizations_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in realizations:
        realizations_by_cell[row["spec"]["canonical_cell_id"]].append(row)
    for item in ordered:
        unit_dir = output / "units" / item["item_id"]
        unit_dir.mkdir(parents=True, exist_ok=False)
        opportunity = opportunities[item["provenance"]["opportunity_id"]]
        write_json(
            unit_dir / "input.json",
            {
                "opportunity": opportunity,
                "primary_kc": cards_by_id[item["primary_kc_id"]],
                "realizations_for_cell": realizations_by_cell[item["canonical_cell_id"]],
                "generation_configuration": config["generation"],
                "batch_input_artifacts": [
                    describe(projection_path), describe(inventory_path), describe(realizations_path)
                ],
            },
        )
        write_json(
            unit_dir / "procedure.json",
            {
                "implementation": config["generation"]["implementation"],
                "deterministic": True,
                "template": describe(template_path),
                "lexicon": describe(lexicon_path),
                "rules": describe(rules_path),
                "model_invoked": False,
            },
        )
        write_json(unit_dir / "generated_item.json", item)
    write_stage_manifest(
        output,
        module="items.generation",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[projection_path, inventory_path, realizations_path],
        configs=[
            experiment_manifest, template_path, lexicon_path, rules_path,
            activation_schema, kc_schema, realization_schema,
        ],
        code=[
            Path(__file__),
            ROOT / "modules" / "stage_6_items" / "helpers.py",
            ROOT / "modules" / "stage_4_realization" / "engine.py",
        ],
        outputs=[candidates_path, units_path, output / "units"],
        details={
            "item_family": config["family"],
            "generator": config["generation"]["implementation"],
            "model_invoked": False,
            "candidate_items": len(ordered),
            "diagnostic_units": len(units),
        },
    )
