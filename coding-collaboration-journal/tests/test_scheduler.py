from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_scheduler import render_systemd  # noqa: E402


class SchedulerTests(unittest.TestCase):
    def test_systemd_renderer_quotes_paths_and_escapes_specifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal % with spaces"
            root.mkdir()
            service, timer = render_systemd(root, 2, 5)
            content = service.read_text(encoding="utf-8")
            escaped_root = str(root).replace("%", "%%")
            self.assertIn(f'WorkingDirectory="{escaped_root}"', content)
            self.assertIn(f'"{escaped_root}/scripts/run_journal.py"', content)
            self.assertIn(f'"{escaped_root}"', content)
            self.assertIn("OnCalendar=*-*-* 02:05:00", timer.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
