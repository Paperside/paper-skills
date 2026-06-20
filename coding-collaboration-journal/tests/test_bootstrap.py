from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bootstrap import install_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.py"


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, output: Path, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BOOTSTRAP),
                "--output",
                str(output),
                "--sources",
                "codex,claude",
                "--privacy",
                "Low",
                "--timezone",
                "Asia/Shanghai",
                "--run-time",
                "02:00",
                "--scheduler",
                "none",
                "--no-init-git",
                "--no-auto-commit",
                "--no-auto-push",
                *extra,
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )

    def test_bootstrap_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "journal"
            first = self.run_bootstrap(output)
            self.assertEqual(first.returncode, 0, first.stderr)
            payload = json.loads(first.stdout)
            self.assertGreater(payload["files"]["created"], 10)
            self.assertTrue((output / ".journal" / "config.toml").is_file())
            self.assertTrue((output / "automation" / "daily.md").is_file())
            self.assertTrue((output / "scripts" / "doctor.py").is_file())
            self.assertIn('level = "Low"', (output / ".journal" / "config.toml").read_text())
            config_text = (output / ".journal" / "config.toml").read_text()
            self.assertIn("[memory]", config_text)
            self.assertIn("inject_on_session_start = true", config_text)
            self.assertIn("briefing_char_limit = 6000", config_text)

            manifest_before = (output / ".journal" / "install-manifest.json").read_bytes()
            scheduler_before = (output / ".journal" / "state" / "scheduler.json").read_bytes()
            second = self.run_bootstrap(output)
            self.assertEqual(second.returncode, 0, second.stderr)
            payload2 = json.loads(second.stdout)
            self.assertEqual(payload2["files"]["created"], 0)
            self.assertEqual(payload2["files"]["updated"], 0)
            self.assertEqual(payload2["files"]["preserved"], 0)
            self.assertEqual((output / ".journal" / "install-manifest.json").read_bytes(), manifest_before)
            self.assertEqual((output / ".journal" / "state" / "scheduler.json").read_bytes(), scheduler_before)

    def test_user_modification_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "journal"
            first = self.run_bootstrap(output)
            self.assertEqual(first.returncode, 0, first.stderr)
            agents = output / "AGENTS.md"
            agents.write_text(agents.read_text() + "\nUSER RULE\n", encoding="utf-8")

            second = self.run_bootstrap(output)
            self.assertEqual(second.returncode, 0, second.stderr)
            payload = json.loads(second.stdout)
            self.assertEqual(payload["files"]["preserved"], 1)
            self.assertIn("USER RULE", agents.read_text(encoding="utf-8"))
            proposed = output / ".journal" / "conflicts" / "AGENTS.md.new"
            self.assertFalse(proposed.exists())

    def test_real_upstream_change_emits_conflict_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "journal"
            root.mkdir()
            first = install_files(root, {"AGENTS.md": b"managed v1\n"}, force=False, dry_run=False)
            self.assertEqual(first["actions"][0]["action"], "create")
            (root / "AGENTS.md").write_text("managed v1\nUSER RULE\n", encoding="utf-8")
            second = install_files(root, {"AGENTS.md": b"managed v2\n"}, force=False, dry_run=False)
            self.assertEqual(second["actions"][0]["action"], "preserve-user-modification")
            self.assertEqual(len(second["conflicts"]), 1)
            proposed = root / ".journal" / "conflicts" / "AGENTS.md.new"
            self.assertEqual(proposed.read_text(encoding="utf-8"), "managed v2\n")
            self.assertIn("USER RULE", (root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_english_templates_are_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "journal"
            result = self.run_bootstrap(output, "--language", "en")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("This repository is a long-running", (output / "README.md").read_text())
            self.assertIn("## Daily conclusion", (output / "templates" / "report.md").read_text())

    def test_deployed_runtime_prompts_are_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "journal"
            result = self.run_bootstrap(output, "--scheduler", "codex-automation")
            self.assertEqual(result.returncode, 0, result.stderr)

            runtime_paths = [
                output / "automation" / "daily.md",
                output / "automation" / "weekly.md",
                output / "automation" / "monthly.md",
                output / ".journal" / "scheduler" / "codex-automation.md",
                output / ".journal" / "scheduler" / "claude-desktop-task.md",
            ]
            for path in runtime_paths:
                text = path.read_text(encoding="utf-8")
                self.assertIn("self-contained", text, path)
                self.assertIn("runtime", text, path)
                self.assertNotIn("$coding-collaboration-journal", text, path)
                self.assertNotIn("installed skill", text.lower(), path)

            daily = (output / "automation" / "daily.md").read_text(encoding="utf-8")
            self.assertIn(".journal/config.toml", daily)
            self.assertIn("docs/method/*", daily)
            self.assertIn("scripts/*", daily)

    def isolated_git_env(self, home: Path) -> dict[str, str]:
        env = os.environ.copy()
        for key in (
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
        ):
            env.pop(key, None)
        home.mkdir(parents=True, exist_ok=True)
        env.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
            }
        )
        return env

    def test_repository_local_git_identity_creates_initial_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output = base / "journal"
            result = self.run_bootstrap(
                output,
                "--init-git",
                "--auto-commit",
                "--no-auto-push",
                "--git-user-name",
                "Journal Bot",
                "--git-user-email",
                "journal@example.test",
                env=self.isolated_git_env(base / "home"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["git"]["commit"])
            self.assertEqual(payload["git"]["fatal_errors"], [])
            self.assertEqual(payload["git"]["identity"]["name"], "Journal Bot")
            self.assertEqual(payload["git"]["identity"]["email"], "journal@example.test")
            self.assertTrue(payload["git"]["identity"]["repository_local_override"])
            name = subprocess.run(
                ["git", "config", "--local", "--get", "user.name"],
                cwd=output,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            self.assertEqual(name, "Journal Bot")
            head_before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=output,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            rerun = self.run_bootstrap(
                output,
                "--init-git",
                "--auto-commit",
                "--no-auto-push",
                "--git-user-name",
                "Journal Bot",
                "--git-user-email",
                "journal@example.test",
                env=self.isolated_git_env(base / "home"),
            )
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            rerun_payload = json.loads(rerun.stdout)
            self.assertEqual(rerun_payload["git"]["commit"], "no-change")
            head_after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=output,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            self.assertEqual(head_after, head_before)

    def test_missing_git_identity_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output = base / "journal"
            result = self.run_bootstrap(
                output,
                "--init-git",
                "--auto-commit",
                "--no-auto-push",
                env=self.isolated_git_env(base / "home"),
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            message = "\n".join(payload["git"]["fatal_errors"])
            self.assertIn("Git author identity is missing", message)
            self.assertIn("--git-user-name", message)
            self.assertIn("--git-user-email", message)

    def test_push_failure_is_pending_not_install_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output = base / "journal"
            env = os.environ.copy()
            env.update(
                {
                    "GIT_AUTHOR_NAME": "Journal Test",
                    "GIT_AUTHOR_EMAIL": "journal@example.test",
                    "GIT_COMMITTER_NAME": "Journal Test",
                    "GIT_COMMITTER_EMAIL": "journal@example.test",
                }
            )
            result = self.run_bootstrap(
                output,
                "--init-git",
                "--auto-commit",
                "--auto-push",
                "--remote",
                (base / "missing-remote.git").as_uri(),
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["git"]["push"], "pending")
            self.assertEqual(payload["git"]["fatal_errors"], [])
            self.assertTrue(payload["git"]["warnings"])
            self.assertTrue((output / ".journal" / "state" / "pending-push.json").is_file())

            tracked = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
                cwd=output,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
            self.assertIn(".journal/state/scheduler.json", tracked)


if __name__ == "__main__":
    unittest.main()
