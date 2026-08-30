from __future__ import annotations

import json

import pytest

from scripts.final_release_manifest import (
    DEFAULT_OUTPUT,
    build_manifest,
    verify_manifest,
)


def test_final_release_manifest_matches_every_scoped_artifact() -> None:
    verify_manifest(DEFAULT_OUTPUT)
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    current = build_manifest()
    assert stored == current
    assert stored["artifact_count"] == len(stored["artifacts"])
    assert len({row["path"] for row in stored["artifacts"]}) == stored[
        "artifact_count"
    ]


def test_release_manifest_detects_stored_digest_drift(monkeypatch, tmp_path) -> None:
    stored = build_manifest()
    stored["artifacts"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr("scripts.final_release_manifest.DEFAULT_OUTPUT", path)
    with pytest.raises(ValueError, match="changed="):
        verify_manifest(path)
