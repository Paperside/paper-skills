from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from install_hooks import CODEX_EVENTS, CLAUDE_EVENTS, merge_hooks, write_with_backup  # noqa: E402


class HookMergeTests(unittest.TestCase):
    def test_codex_merge_is_additive_and_idempotent(self) -> None:
        doc = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "existing"}]}]}}
        command = '"python" "capture_event.py" --source codex'
        merged, added = merge_hooks(doc, "codex", command)
        self.assertEqual(added, len(CODEX_EVENTS))
        self.assertEqual(merged["hooks"]["Stop"][0]["hooks"][0]["command"], "existing")
        merged_again, added_again = merge_hooks(merged, "codex", command)
        self.assertEqual(added_again, 0)
        self.assertIs(merged_again, merged)

    def test_claude_tool_matcher(self) -> None:
        merged, _ = merge_hooks({}, "claude", "capture")
        self.assertEqual(set(merged["hooks"]), set(CLAUDE_EVENTS))
        self.assertEqual(merged["hooks"]["PostToolUse"][0]["matcher"], "*")

    def test_identical_hook_settings_do_not_create_backup(self) -> None:
        document = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "capture"}]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            first_backup = write_with_backup(path, document, dry_run=False)
            self.assertIsNone(first_backup)
            original = path.read_text(encoding="utf-8")
            second_backup = write_with_backup(path, document, dry_run=False)
            self.assertIsNone(second_backup)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(path.parent.glob("settings.json.bak.*")), [])


if __name__ == "__main__":
    unittest.main()
