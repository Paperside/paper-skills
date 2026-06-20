from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "scripts" / "capture_event.py"


class CaptureEventTests(unittest.TestCase):
    def write_config(self, journal: Path, *, inject: bool = True) -> None:
        config = journal / ".journal" / "config.toml"
        config.parent.mkdir(parents=True)
        config.write_text(
            '[journal]\ntimezone = "UTC"\n'
            '[privacy]\nlevel = "Low"\ncustom_sensitive_terms = []\n'
            '[memory]\n'
            f'inject_on_session_start = {str(inject).lower()}\n'
            'briefing_char_limit = 6000\n',
            encoding="utf-8",
        )

    def run_capture(self, journal: Path, incoming: dict[str, object], source: str = "codex") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CAPTURE), "--source", source, "--root", str(journal)],
            input=json.dumps(incoming),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_hook_sink_writes_sanitized_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp)
            self.write_config(journal)
            incoming = {"hook_event_name": "UserPromptSubmit", "cwd": "/repo", "api_key": "nope"}
            proc = self.run_capture(journal, incoming)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            files = list((journal / ".journal" / "events" / "codex").glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            record = json.loads(files[0].read_text().strip())
            self.assertEqual(record["event"]["cwd"], "/repo")
            self.assertEqual(record["event"]["api_key"], "[REDACTED_SECRET]")

    def test_session_start_injects_bounded_sanitized_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp)
            self.write_config(journal)
            memory = journal / "memory"
            memory.mkdir()
            (memory / "user-profile.md").write_text(
                "# User Collaboration Profile\n\n- Prefer tests before refactors.\n- API_KEY=do-not-inject\n",
                encoding="utf-8",
            )
            (memory / "open-loops.yaml").write_text(
                "schema_version: 1\nopen_loops:\n  - id: O-1\n    summary: Finish callback migration\n",
                encoding="utf-8",
            )
            proc = self.run_capture(
                journal,
                {"hook_event_name": "SessionStart", "source": "resume", "session_id": "s1"},
                source="claude",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = json.loads(proc.stdout)
            hook = output["hookSpecificOutput"]
            self.assertEqual(hook["hookEventName"], "SessionStart")
            context = hook["additionalContext"]
            self.assertIn("Prefer tests before refactors", context)
            self.assertIn("Finish callback migration", context)
            self.assertNotIn("do-not-inject", context)
            self.assertIn("[REDACTED_SECRET]", context)
            self.assertLessEqual(len(context), 6000)

    def test_session_start_memory_injection_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp)
            self.write_config(journal, inject=False)
            memory = journal / "memory"
            memory.mkdir()
            (memory / "user-profile.md").write_text("# User Collaboration Profile\n\n- Prefer small commits.\n")
            proc = self.run_capture(journal, {"hook_event_name": "SessionStart"})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_hook_sink_is_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(CAPTURE), "--source", "claude", "--root", tmp],
                input="not-json",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertTrue((Path(tmp) / ".journal" / "state" / "hook-errors.log").is_file())


if __name__ == "__main__":
    unittest.main()
