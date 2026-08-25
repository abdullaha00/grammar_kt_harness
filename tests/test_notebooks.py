from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
