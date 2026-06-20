from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from collect_day import should_scan_all_claude  # noqa: E402
BOOTSTRAP = ROOT / "scripts" / "bootstrap.py"

FAKE_SERVER = r'''#!/usr/bin/env python3
import json, os, sys

def send(x):
    print(json.dumps(x), flush=True)

for line in sys.stdin:
    r = json.loads(line)
    m, i = r.get("method"), r.get("id")
    if m == "initialize": send({"id": i, "result": {}})
    elif m == "initialized": pass
    elif m == "thread/list":
        if os.environ.get("FAKE_EMPTY") == "1":
            data = []
        else:
            data = [{"id": "thr", "createdAt": 1781913600, "updatedAt": 1781956800, "recencyAt": 1781956800, "cwd": os.environ.get("FAKE_CWD", "")}]
        send({"id": i, "result": {"data": data, "nextCursor": None}})
    elif m == "thread/read": send({"id": i, "result": {"thread": {"id": "thr", "cwd": os.environ.get("FAKE_CWD", ""), "turns": []}}})
    elif m == "thread/turns/list": send({"id": i, "result": {"data": [{"id": "turn", "items": [{"type": "userMessage", "text": "work"}]}], "nextCursor": None}})
    else: send({"id": i, "error": {"message": "unsupported"}})
'''


class CollectDayTests(unittest.TestCase):
    def test_historical_backfill_scans_full_claude_store(self) -> None:
        today = date(2026, 6, 20)
        self.assertFalse(should_scan_all_claude(date(2026, 6, 19), today, 3, False))
        self.assertTrue(should_scan_all_claude(date(2026, 6, 16), today, 3, False))
        self.assertTrue(should_scan_all_claude(date(2026, 6, 19), today, 3, True))

    def bootstrap(self, journal: Path) -> None:
        bootstrap = subprocess.run(
            [
                sys.executable,
                str(BOOTSTRAP),
                "--output",
                str(journal),
                "--sources",
                "codex",
                "--timezone",
                "UTC",
                "--scheduler",
                "none",
                "--no-init-git",
                "--no-auto-commit",
                "--no-auto-push",
                "--yes",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

    def fake_codex(self, base: Path) -> Path:
        fake = base / "fake-codex"
        fake.write_text(FAKE_SERVER, encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def test_normalizes_sources_discovers_repo_and_emits_status_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            journal = base / "journal"
            self.bootstrap(journal)
            fake = self.fake_codex(base)

            workspace = base / "workspace"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            (workspace / "work.txt").write_text("uncommitted", encoding="utf-8")

            env = os.environ.copy()
            env["FAKE_CWD"] = str(workspace)
            collect = subprocess.run(
                [
                    sys.executable,
                    str(journal / "scripts" / "collect_day.py"),
                    "--root",
                    str(journal),
                    "--date",
                    "2026-06-20",
                    "--codex",
                    str(fake),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )
            self.assertEqual(collect.returncode, 0, collect.stderr)
            payload = json.loads(collect.stdout)
            self.assertEqual(payload["status_hint"], "active")
            self.assertEqual(payload["coverage"], "complete")
            self.assertGreaterEqual(payload["repository_candidate_count"], 1)
            self.assertEqual(payload["sources"]["git"]["repository_count"], 1)
            day = journal / "journal" / "2026" / "06" / "2026-06-20"
            self.assertTrue((day / "collection.json").is_file())
            self.assertTrue((day / "sources" / "codex.json").is_file())
            self.assertTrue((day / "sources" / "git.json").is_file())
            self.assertTrue((day / "sources" / "manual-notes.json").is_file())

    def test_disabled_sources_are_not_collected_or_counted_as_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            journal = base / "journal"
            self.bootstrap(journal)
            fake = self.fake_codex(base)

            config_path = journal / ".journal" / "config.toml"
            config = config_path.read_text(encoding="utf-8")
            config = config.replace("git = true", "git = false").replace("manual_notes = true", "manual_notes = false")
            config_path.write_text(config, encoding="utf-8")

            workspace = base / "workspace"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            (workspace / "work.txt").write_text("should not count", encoding="utf-8")
            note = journal / ".journal" / "notes" / "2026-06-20.md"
            note.write_text("also disabled", encoding="utf-8")

            hook_dir = journal / ".journal" / "events" / "claude"
            hook_dir.mkdir(parents=True, exist_ok=True)
            (hook_dir / "2026-06-20.jsonl").write_text(
                json.dumps(
                    {
                        "source": "claude",
                        "captured_at": "2026-06-20T10:00:00Z",
                        "event": {"cwd": str(workspace)},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["FAKE_EMPTY"] = "1"
            collect = subprocess.run(
                [
                    sys.executable,
                    str(journal / "scripts" / "collect_day.py"),
                    "--root",
                    str(journal),
                    "--date",
                    "2026-06-20",
                    "--codex",
                    str(fake),
                    "--repo",
                    str(workspace),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )
            self.assertEqual(collect.returncode, 0, collect.stderr)
            payload = json.loads(collect.stdout)
            self.assertEqual(payload["status_hint"], "no-activity")
            self.assertEqual(payload["coverage"], "complete")
            self.assertFalse(payload["activity_signal"])
            self.assertEqual(payload["sources"]["git"]["coverage"], "disabled")
            self.assertEqual(payload["sources"]["manual-notes"]["coverage"], "disabled")
            day_sources = journal / "journal" / "2026" / "06" / "2026-06-20" / "sources"
            self.assertFalse((day_sources / "git.json").exists())
            self.assertFalse((day_sources / "manual-notes.json").exists())
            self.assertTrue((day_sources / "hooks.json").exists())


if __name__ == "__main__":
    unittest.main()
