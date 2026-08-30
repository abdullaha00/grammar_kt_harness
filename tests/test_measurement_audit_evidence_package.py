from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/package_measurement_audit_evidence.py"
SPEC = importlib.util.spec_from_file_location("package_measurement_audit", SCRIPT)
assert SPEC and SPEC.loader
package_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_module)


def test_packaged_live_audit_evidence_is_complete_and_hashed() -> None:
    audit_dir = ROOT / "experiments/measurement_realism/audits/full_v1_items_v2"
    manifest_path = audit_dir / "call_evidence_manifest.json"
    bundle_path = audit_dir / "call_evidence_bundle.jsonl"
    assert manifest_path.is_file() and bundle_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines()]
    assert manifest["calls"] == 16 == len(rows)
    assert manifest["files_per_call"] == len(package_module.ARTIFACTS)
    assert package_module.file_sha256(bundle_path) == manifest["bundle_sha256"]
    assert all(set(row["files"]) == set(package_module.ARTIFACTS) for row in rows)
    assert all(
        row["files"]["model_settings.json"]["content"].find("gpt-5.6-terra") >= 0
        for row in rows
    )

