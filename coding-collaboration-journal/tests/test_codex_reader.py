from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "scripts" / "codex_app_server_reader.py"

FAKE_SERVER = r'''#!/usr/bin/env python3
import json
import os
import sys

def send(value):
    sys.stdout.write(json.dumps(value) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        experimental = request.get("params", {}).get("capabilities", {}).get("experimentalApi")
        if experimental is not True:
            send({"id": request_id, "error": {"message": "thread/turns/list requires experimentalApi capability"}})
        else:
            send({"id": request_id, "result": {"serverInfo": {"name": "fake"}}})
    elif method == "initialized":
        continue
    elif method == "thread/list":
        if os.environ.get("FAKE_SOURCE_KINDS_ERROR") == "1" and "sourceKinds" in request.get("params", {}):
            send({"id": request_id, "error": {"message": "unknown source kind in this build"}})
            continue
        send({"id": request_id, "result": {"data": [{
            "id": "thr_1",
            "createdAt": 1781913600,
            "updatedAt": 1781956800,
            "recencyAt": 1781956800,
            "cwd": "/repo"
        }], "nextCursor": None}})
    elif method == "thread/read":
        send({"id": request_id, "result": {"thread": {
            "id": "thr_1",
            "turns": [
                {"id": "fallback-old", "items": [{"type": "userMessage", "text": "start"}]},
                {"id": "fallback-new", "items": [{"type": "agentMessage", "text": "done"}]}
            ]
        }}})
    elif method == "thread/turns/list":
        if os.environ.get("FAKE_TURNS_ERROR") == "1":
            send({"id": request_id, "error": {"message": "experimental method unavailable in this build"}})
            continue
        cursor = request.get("params", {}).get("cursor")
        if cursor is None:
            send({"id": request_id, "result": {"data": [{"id": "new", "items": [{"type": "agentMessage", "text": "done"}]}], "nextCursor": "older"}})
        else:
            send({"id": request_id, "result": {"data": [{"id": "old", "items": [{"type": "userMessage", "text": "start"}]}], "nextCursor": None}})
    else:
        send({"id": request_id, "error": {"message": "unsupported " + str(method)}})
'''


class CodexReaderTests(unittest.TestCase):
    def run_reader(
        self,
        base: Path,
        *,
        turns_error: bool = False,
        source_kinds_error: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        fake = base / "fake-codex"
        fake.write_text(FAKE_SERVER, encoding="utf-8")
        fake.chmod(0o755)
        output = base / "codex.json"
        env = os.environ.copy()
        if turns_error:
            env["FAKE_TURNS_ERROR"] = "1"
        if source_kinds_error:
            env["FAKE_SOURCE_KINDS_ERROR"] = "1"
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
                "--codex",
                str(fake),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )
        return proc, json.loads(output.read_text())

    def test_reads_full_paginated_turns_in_chronological_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc, payload = self.run_reader(Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["selected_thread_count"], 1)
            self.assertTrue(payload["include_archived"])
            self.assertEqual(payload["listed_thread_count"], 1)
            item = payload["threads"][0]
            self.assertEqual(item["turns_interface"], "thread/turns/list:full")
            self.assertEqual([turn["id"] for turn in item["thread"]["turns"]], ["old", "new"])
            self.assertEqual(payload["warnings"], [])

    def test_falls_back_to_stable_thread_read_without_losing_complete_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc, payload = self.run_reader(Path(tmp), turns_error=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["errors"], [])
            self.assertTrue(payload["warnings"])
            item = payload["threads"][0]
            self.assertEqual(item["turns_interface"], "thread/read:includeTurns-fallback")
            self.assertEqual(
                [turn["id"] for turn in item["thread"]["turns"]],
                ["fallback-old", "fallback-new"],
            )

    def test_falls_back_to_interactive_sources_and_marks_scope_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc, payload = self.run_reader(Path(tmp), source_kinds_error=True)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(payload["coverage"], "partial")
            self.assertEqual(payload["source_filter_mode"], "interactive-fallback")
            self.assertEqual(payload["selected_thread_count"], 1)
            self.assertEqual(payload["errors"], [])
            self.assertTrue(any(item.get("stage") == "thread/list" for item in payload["warnings"]))

    def test_repeated_app_server_invocations_exit_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for _ in range(3):
                proc, payload = self.run_reader(base, source_kinds_error=True)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(payload["coverage"], "partial")




if __name__ == "__main__":
    unittest.main()
