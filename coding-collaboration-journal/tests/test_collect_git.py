from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECT_GIT = ROOT / "scripts" / "collect_git.py"


class CollectGitTests(unittest.TestCase):
    def test_unborn_repository_is_complete_and_snapshot_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "unborn"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "draft.txt").write_text("uncommitted work\n", encoding="utf-8")
            output = base / "git.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    str(COLLECT_GIT),
                    "--start",
                    "2026-06-20T00:00:00Z",
                    "--end",
                    "2026-06-21T00:00:00Z",
                    "--output",
                    str(output),
                    "--repo",
                    str(repo),
                    "--privacy",
                    "Low",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["repository_count"], 1)
            collected = payload["repositories"][0]
            self.assertFalse(collected["has_head"])
            self.assertIsNone(collected["head"])
            self.assertEqual(collected["coverage"], "complete")
            self.assertEqual(collected["command_failures"], [])
            snapshot = collected["working_tree_snapshot"]
            self.assertEqual(snapshot["temporal_scope"], "collection-time-working-tree-snapshot")
            self.assertIn("cannot date individual uncommitted edits", snapshot["note"])
            self.assertEqual(
                collected["unstaged_diff"]["temporal_scope"],
                "collection-time-working-tree-snapshot",
            )
            self.assertEqual(
                collected["staged_diff"]["temporal_scope"],
                "collection-time-working-tree-snapshot",
            )


if __name__ == "__main__":
    unittest.main()
