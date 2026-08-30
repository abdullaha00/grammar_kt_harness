from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/analyze_platform_audits.py"
FROZEN_DATASET = ROOT / "data/grammar_kt_full_v1"


def test_platform_audit_synthesis_replays_exactly(tmp_path: Path) -> None:
    expected_json_path = (
        ROOT
        / "experiments/measurement_realism/audits/platform_audit_synthesis.json"
    )
    expected_report_path = ROOT / "reports/platform_plausibility_audit.md"
    replay_json = tmp_path / "synthesis.json"
    replay_report = tmp_path / "report.md"

    before_manifest = (FROZEN_DATASET / "manifest.json").read_bytes()
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--json-output",
            str(replay_json),
            "--report-output",
            str(replay_report),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (FROZEN_DATASET / "manifest.json").read_bytes() == before_manifest
    assert replay_json.read_bytes() == expected_json_path.read_bytes()
    assert replay_report.read_bytes() == expected_report_path.read_bytes()

    result = json.loads(replay_json.read_text(encoding="utf-8"))
    assert result["coverage"] == {
        "common_items": 113,
        "live_items": 113,
        "live_judgments": 452,
        "live_roles": ["learner", "teacher", "platform_product", "measurement"],
        "strict_items": 113,
    }
    confusion = result["agreement"][
        "confusion_counts_rows_strict_columns_live"
    ]
    assert sum(sum(row.values()) for row in confusion.values()) == 113
    assert result["agreement"]["exact_mapped_category"]["count"] == 70
    assert result["agreement"]["critical_redesign_threshold"]["either_critical"][
        "count"
    ] == 18
    assert len(result["item_level"]) == 113
