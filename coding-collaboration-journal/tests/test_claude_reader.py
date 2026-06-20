from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "scripts" / "claude_session_reader.py"


class ClaudeReaderTests(unittest.TestCase):
    def test_reads_recent_jsonl_and_reports_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = base / "projects" / "repo"
            store.mkdir(parents=True)
            session = store / "session.jsonl"
            session.write_text(json.dumps({"type": "user", "message": "hello"}) + "\n", encoding="utf-8")
            output = base / "evidence.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(READER),
                    "--start",
                    "2026-06-19T00:00:00Z",
                    "--end",
                    "2027-06-21T00:00:00Z",
                    "--output",
                    str(output),
                    "--claude-root",
                    str(base / "projects"),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["selected_session_count"], 1)
            self.assertEqual(payload["sessions"][0]["records"][0]["message"], "hello")

    def test_large_session_detects_activity_in_omitted_middle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = base / "projects" / "repo"
            store.mkdir(parents=True)
            session = store / "large.jsonl"
            rows = [{"timestamp": "2026-06-19T00:00:00Z", "message": "head"}]
            rows.extend({"message": "x" * 100, "index": i} for i in range(80))
            rows.insert(40, {"timestamp": "2026-06-20T12:00:00Z", "message": "middle activity"})
            rows.append({"timestamp": "2026-06-22T00:00:00Z", "message": "tail"})
            session.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            epoch = datetime(2026, 6, 20, 12, tzinfo=timezone.utc).timestamp()
            os.utime(session, (epoch, epoch))

            output = base / "evidence.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(READER),
                    "--start",
                    "2026-06-20T00:00:00Z",
                    "--end",
                    "2026-06-21T00:00:00Z",
                    "--output",
                    str(output),
                    "--claude-root",
                    str(base / "projects"),
                    "--max-file-bytes",
                    "2048",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["coverage"], "partial")
            self.assertEqual(payload["selected_session_count"], 1)
            selected = payload["sessions"][0]
            self.assertTrue(selected["truncated"])
            self.assertEqual(selected["activity_records"], 1)
            retained_text = json.dumps(selected["records"])
            self.assertNotIn("middle activity", retained_text)


if __name__ == "__main__":
    unittest.main()
