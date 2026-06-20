from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.py"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_journal import validate  # noqa: E402


class JournalValidationTests(unittest.TestCase):
    def scaffold(self, output: Path) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(BOOTSTRAP),
                "--output",
                str(output),
                "--sources",
                "codex,claude",
                "--scheduler",
                "none",
                "--no-init-git",
                "--no-auto-commit",
                "--no-auto-push",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def write_day(self, root: Path, status: str, codex_coverage: str = "complete") -> Path:
        day = root / "journal" / "2026" / "06" / "2026-06-20"
        day.mkdir(parents=True)
        (day / "report.md").write_text(
            f"---\ndate: 2026-06-20\nstatus: {status}\n---\n\n## 协作分析\n\nObserved E-CODEX-001.\n\n## 综合评价\n\n## 数据质量\n",
            encoding="utf-8",
        )
        (day / "evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "report_date": "2026-06-20",
                    "timezone": "UTC",
                    "status": status,
                    "sources": {"codex": {"coverage": codex_coverage}, "claude": {"coverage": "complete"}},
                    "evidence": [
                        {
                            "evidence_id": "E-CODEX-001",
                            "source": "codex",
                            "kind": "message",
                            "occurred_at": "2026-06-20T12:00:00Z",
                            "content_hash": "sha256:test",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (day / "run.json").write_text(
            '{"schema_version":1,"report_date":"2026-06-20","started_at":"2026-06-21T02:00:00Z","status":"complete","stages":[]}\n',
            encoding="utf-8",
        )
        return day

    def test_false_no_activity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            self.write_day(root, "no-activity", codex_coverage="unavailable")
            result = validate(root)
            self.assertFalse(result["valid"])
            self.assertIn("false-no-activity", {item["code"] for item in result["findings"]})

    def test_complete_active_day_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            self.write_day(root, "active")
            result = validate(root)
            self.assertTrue(result["valid"], result["findings"])

    def test_dangling_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            day = self.write_day(root, "active")
            report = day / "report.md"
            report.write_text(report.read_text() + "\nMissing E-GIT-404\n", encoding="utf-8")
            result = validate(root)
            self.assertIn("dangling-evidence", {item["code"] for item in result["findings"]})


    def test_disabled_source_does_not_invalidate_no_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            day = self.write_day(root, "no-activity")
            evidence_path = day / "evidence.json"
            evidence = json.loads(evidence_path.read_text())
            evidence["sources"]["git"] = {"enabled": False, "coverage": "disabled"}
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            result = validate(root)
            self.assertTrue(result["valid"], result["findings"])

    def test_date_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            day = self.write_day(root, "active")
            evidence_path = day / "evidence.json"
            evidence = json.loads(evidence_path.read_text())
            evidence["report_date"] = "2026-06-19"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            result = validate(root)
            self.assertIn("evidence-date-mismatch", {item["code"] for item in result["findings"]})

    def test_secret_in_provider_native_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            day = self.write_day(root, "active")
            sources = day / "sources"
            sources.mkdir()
            (sources / "codex.json").write_text(
                '{"tool_input":"API_KEY=ordinary-looking-secret"}\n',
                encoding="utf-8",
            )
            result = validate(root)
            findings = [item for item in result["findings"] if item["code"] == "secret-pattern"]
            self.assertTrue(findings)
            self.assertTrue(any(str(item.get("path", "")).endswith("sources/codex.json") for item in findings))

    def test_runtime_detection_source_is_not_scanned_as_user_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            self.scaffold(root)
            self.write_day(root, "active")
            (root / "scripts" / "custom_detector.py").write_text(
                'EXAMPLE = "API_KEY=ordinary-looking-example"\n',
                encoding="utf-8",
            )
            result = validate(root)
            findings = [item for item in result["findings"] if item["code"] == "secret-pattern"]
            self.assertFalse(findings, findings)


if __name__ == "__main__":
    unittest.main()
