from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = (
    ROOT / "notebooks" / "module_unit_examples.ipynb",
    ROOT / "notebooks" / "research_audit.ipynb",
)


class NotebookSmokeTests(unittest.TestCase):
    def test_research_notebooks_execute_with_fixture_backends(self) -> None:
        """Execute code cells in order without a notebook-server dependency."""

        original_directory = Path.cwd()
        try:
            os.chdir(ROOT)
            with patch.dict(os.environ, {"AUDIT_SMOKE_TEST": "1"}):
                for notebook_path in NOTEBOOKS:
                    with self.subTest(notebook=notebook_path.name):
                        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
                        namespace = {"__name__": "__notebook_smoke__"}
                        captured = io.StringIO()
                        for index, cell in enumerate(notebook["cells"]):
                            if cell["cell_type"] != "code":
                                continue
                            source = cell["source"]
                            if isinstance(source, list):
                                source = "".join(source)
                            try:
                                with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                                    exec(
                                        compile(
                                            source,
                                            f"{notebook_path}:cell-{index}",
                                            "exec",
                                        ),
                                        namespace,
                                    )
                            except Exception as error:
                                tail = captured.getvalue()[-4000:]
                                self.fail(
                                    f"{notebook_path.name} code cell {index} failed: "
                                    f"{type(error).__name__}: {error}\n{tail}"
                                )
                        for value in namespace.values():
                            if isinstance(value, tempfile.TemporaryDirectory):
                                value.cleanup()
        finally:
            os.chdir(original_directory)

    def test_walkthrough_is_synchronised_and_builder_preserves_audit(self) -> None:
        before = {path: path.read_bytes() for path in NOTEBOOKS}
        subprocess.run(
            ["python", "scripts/build_notebooks.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(NOTEBOOKS[0].read_bytes(), before[NOTEBOOKS[0]])
        self.assertEqual(NOTEBOOKS[1].read_bytes(), before[NOTEBOOKS[1]])

    def test_walkthrough_links_and_replay_fingerprints_resolve(self) -> None:
        notebook_path = NOTEBOOKS[0]
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        markdown = "\n".join(
            cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
        links = re.findall(r"\]\(([^)]+)\)", markdown)
        relative_links = [link.split("#", 1)[0] for link in links if "://" not in link]
        missing = [
            link for link in relative_links
            if not (notebook_path.parent / link).resolve().exists()
        ]
        self.assertFalse(missing, f"walkthrough contains missing relative links: {missing}")

        manifest_path = ROOT / "reference/pipeline_walkthrough/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mismatches = []
        for relative_path, expected in manifest["artifact_sha256"].items():
            actual = hashlib.sha256((manifest_path.parent / relative_path).read_bytes()).hexdigest()
            if actual != expected:
                mismatches.append(relative_path)
        self.assertFalse(mismatches, f"walkthrough replay fingerprints differ: {mismatches}")

    def test_walkthrough_declares_active_boundaries(self) -> None:
        notebook = json.loads(NOTEBOOKS[0].read_text(encoding="utf-8"))
        markdown = "\n".join(
            cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
        code = "\n".join(
            cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        for heading in (
            "# 1. Grammar", "# 2. Measurement", "# 3. Dataset Generation",
            "# 4. Knowledge Representation", "# 5. Evaluation",
            "# 6. One complete provenance trace", "# 7. Scientific invariant summary",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("The five boxes are scientific groupings", markdown)
        self.assertIn("Controlled methodology demonstration (not derived from the five EGP records)", markdown)
        self.assertIn("simulation oracle features ≠ candidate KCs", markdown)
        self.assertIn("LIVE_MODE = False", code)
        self.assertNotIn("archived_code", code)


if __name__ == "__main__":
    unittest.main()
