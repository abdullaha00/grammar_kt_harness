#!/usr/bin/env python3
"""Audit overlap in the released FEAT DIRECT-G five-criteria split."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any


FEAT_COMMIT = "c598a7b6f52e5b3b22fa31fd5c40024d93f37e3f"
BASE_URL = (
    "https://raw.githubusercontent.com/hyenee/FEAT/"
    f"{FEAT_COMMIT}/datasets/DIRECT-G/base"
)


def fetch(split: str) -> tuple[list[dict[str, Any]], str, str]:
    url = f"{BASE_URL}/{split}.criteria_5.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = response.read()
    return json.loads(payload), hashlib.sha256(payload).hexdigest(), url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/post_training/literature/feat_release_audit.json"),
    )
    args = parser.parse_args()

    train, train_hash, train_url = fetch("train")
    test, test_hash, test_url = fetch("test")
    train_contexts = {(row["data_id"], row["reply_id"]) for row in train}
    test_contexts = {(row["data_id"], row["reply_id"]) for row in test}
    train_data_ids = {row["data_id"] for row in train}
    test_data_ids = {row["data_id"] for row in test}
    result = {
        "audit": "FEAT DIRECT-G base, five-criteria released split overlap",
        "feat_commit": FEAT_COMMIT,
        "files": {
            "train": {"url": train_url, "sha256": train_hash},
            "test": {"url": test_url, "sha256": test_hash},
        },
        "train": {
            "records": len(train),
            "unique_data_id_reply_id": len(train_contexts),
            "unique_data_ids": len(train_data_ids),
        },
        "test": {
            "records": len(test),
            "unique_data_id_reply_id": len(test_contexts),
            "unique_data_ids": len(test_data_ids),
        },
        "overlap": {
            "test_contexts_also_in_train": len(train_contexts & test_contexts),
            "test_contexts": len(test_contexts),
            "test_data_ids_also_in_train": len(train_data_ids & test_data_ids),
            "test_data_ids": len(test_data_ids),
        },
        "interpretation": (
            "This describes the released DIRECT-G internal split only. FEAT evaluates "
            "DIRECT-G augmentation on the independently human-ranked DIRECT-M test set, "
            "so this audit does not invalidate the paper's main DG-to-DM result. It does "
            "mean the released DIRECT-G split should not be used as evidence of held-out "
            "context generalization."
        ),
        "exact_command": (
            ".venv/bin/python "
            "experiments/post_training/scripts/audit_feat_release.py"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
