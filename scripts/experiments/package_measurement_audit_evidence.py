#!/usr/bin/env python3
"""Package public item-audit call evidence from ignored call directories.

The audited backend keeps call directories ignored because other stages may
contain restricted source context.  The measurement audit contains only the
public frozen items, so this script copies every exact call artifact into one
immutable, tracked JSONL bundle after validating the retained run manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / "experiments/measurement_realism/audits/full_v1_items_v2"
DEFAULT_EVIDENCE = ROOT / "runs/measurement_realism/full_v1_item_audit_evidence_v2"
ARTIFACTS = (
    "input.json",
    "rendered_prompt.txt",
    "model_settings.json",
    "output_schema.json",
    "raw_output.txt",
    "cli_stderr.txt",
    "call_metadata.json",
    "parsed_result.json",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_frozen(path: Path, payload: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed evidence bundle: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def package(audit_dir: Path, evidence_root: Path) -> dict[str, Any]:
    run_manifest_path = audit_dir / "run_manifest.json"
    if not run_manifest_path.is_file():
        raise FileNotFoundError(run_manifest_path)
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if run_manifest.get("status") != "AUTOMATED_CRITIQUE_COMPLETE":
        raise ValueError("audit run is not complete")
    records = []
    for call in run_manifest["call_manifest"]:
        call_dir = evidence_root / call["role"] / f"batch_{int(call['batch_number']):02d}"
        files: dict[str, Any] = {}
        for filename in ARTIFACTS:
            path = call_dir / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            text = path.read_text(encoding="utf-8")
            files[filename] = {
                "sha256": file_sha256(path),
                "content": text,
            }
        expected = {
            "rendered_prompt.txt": call["rendered_prompt_sha256"],
            "raw_output.txt": call["raw_output_sha256"],
            "parsed_result.json": call["parsed_result_sha256"],
        }
        for filename, digest in expected.items():
            if files[filename]["sha256"] != digest:
                raise ValueError(f"run-manifest digest mismatch: {call_dir / filename}")
        records.append(
            {
                "role": call["role"],
                "batch_number": call["batch_number"],
                "item_count": call["items"],
                "files": files,
            }
        )
    records.sort(key=lambda row: (row["role"], row["batch_number"]))
    payload = "".join(canonical_json(row) + "\n" for row in records)
    bundle_path = audit_dir / "call_evidence_bundle.jsonl"
    write_frozen(bundle_path, payload)
    manifest = {
        "artifact_id": "full_v1_platform_plausibility_call_evidence_bundle_v1",
        "status": "PUBLIC_CALL_EVIDENCE_PACKAGED",
        "calls": len(records),
        "files_per_call": len(ARTIFACTS),
        "artifact_names": list(ARTIFACTS),
        "bundle": bundle_path.name,
        "bundle_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "run_manifest_sha256": file_sha256(run_manifest_path),
        "source_evidence_root": (
            str(evidence_root.relative_to(ROOT))
            if evidence_root.is_relative_to(ROOT)
            else str(evidence_root)
        ),
        "contains_restricted_egp_source_text": False,
        "contains_only_public_frozen_item_context": True,
        "packager": str(Path(__file__).resolve().relative_to(ROOT)),
        "packager_sha256": file_sha256(Path(__file__).resolve()),
    }
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    write_frozen(audit_dir / "call_evidence_manifest.json", manifest_payload)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    result = package(args.audit_dir.resolve(), args.evidence_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

