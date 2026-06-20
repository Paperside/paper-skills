#!/usr/bin/env python3
"""Diagnose an installed Coding Collaboration Journal repository."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from common import find_journal_root, load_toml, read_json, run_command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def check(name: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message, "details": details}


def command_version(command: str, args: list[str]) -> tuple[str, str]:
    path = shutil.which(command)
    if not path:
        return "error", f"{command} not found on PATH"
    result = run_command([path, *args], timeout=10)
    output = (result["stdout"] or result["stderr"]).strip().splitlines()
    if result["ok"]:
        return "ok", output[0] if output else path
    return "warn", f"found at {path}, version probe failed: {result['stderr'].strip()}"


def json_contains_command(path: Path, needle: str) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return needle in json.dumps(value, ensure_ascii=False)


def diagnose(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    config_path = root / ".journal" / "config.toml"
    if not config_path.is_file():
        return {
            "root": str(root),
            "status": "error",
            "checks": [check("config", "error", f"Missing {config_path}")],
        }
    try:
        config = load_toml(config_path)
        checks.append(check("config", "ok", "Configuration parsed", path=str(config_path)))
    except Exception as exc:
        return {
            "root": str(root),
            "status": "error",
            "checks": [check("config", "error", f"Could not parse config: {exc}")],
        }

    if sys.version_info >= (3, 11):
        checks.append(check("python", "ok", sys.version.split()[0]))
    else:
        checks.append(check("python", "error", "Python 3.11 or newer is required"))

    timezone_name = str(config.get("journal", {}).get("timezone", "UTC"))
    try:
        ZoneInfo(timezone_name)
        checks.append(check("timezone", "ok", timezone_name))
    except ZoneInfoNotFoundError:
        checks.append(check("timezone", "error", f"Unknown IANA timezone: {timezone_name}"))

    privacy = str(config.get("privacy", {}).get("level", "Low"))
    checks.append(
        check(
            "privacy",
            "ok" if privacy in {"Low", "Medium", "High"} else "error",
            privacy,
        )
    )

    for relative in ("journal", "reviews/weekly", "reviews/monthly", "memory", "radar", "scripts"):
        path = root / relative
        checks.append(check(f"path:{relative}", "ok" if path.is_dir() else "error", str(path)))

    git_status, git_message = command_version("git", ["--version"])
    checks.append(check("git", git_status, git_message))
    repo_probe = run_command(["git", "rev-parse", "--show-toplevel"], cwd=root, timeout=10)
    if repo_probe["ok"]:
        checks.append(check("git-repository", "ok", repo_probe["stdout"].strip()))
        remotes = run_command(["git", "remote", "-v"], cwd=root, timeout=10)
        if remotes["stdout"].strip():
            checks.append(check("git-remote", "ok", remotes["stdout"].strip()))
        else:
            checks.append(check("git-remote", "warn", "No Git remote configured"))
    else:
        checks.append(check("git-repository", "error", "Journal root is not a Git repository"))

    sources = config.get("sources", {})
    capture_path = str((root / "scripts" / "capture_event.py").resolve())
    if bool(sources.get("codex", False)):
        status, message = command_version("codex", ["--version"])
        checks.append(check("codex", status, message))
        hooks_path = Path.home() / ".codex" / "hooks.json"
        if json_contains_command(hooks_path, capture_path):
            checks.append(check("codex-hooks", "ok", str(hooks_path)))
        else:
            checks.append(check("codex-hooks", "warn", "Journal capture command not found in user hooks", path=str(hooks_path)))
        if hooks_path.exists():
            checks.append(check("codex-hook-trust", "warn", "Verify/trust the hook in Codex /hooks after installation"))

    if bool(sources.get("claude", False)):
        status, message = command_version("claude", ["--version"])
        checks.append(check("claude", status, message))
        settings_path = Path.home() / ".claude" / "settings.json"
        if json_contains_command(settings_path, capture_path):
            checks.append(check("claude-hooks", "ok", str(settings_path)))
        else:
            checks.append(check("claude-hooks", "warn", "Journal capture command not found in user settings", path=str(settings_path)))
        transcript_root = Path.home() / ".claude" / "projects"
        checks.append(
            check(
                "claude-session-store",
                "ok" if transcript_root.is_dir() else "warn",
                str(transcript_root) if transcript_root.is_dir() else "Claude CLI session store not found yet",
            )
        )

    event_count = sum(1 for _ in (root / ".journal" / "events").rglob("*.jsonl"))
    checks.append(
        check(
            "hook-events",
            "ok" if event_count else "warn",
            f"{event_count} event file(s)" if event_count else "No hook event files yet; run a smoke-test prompt/tool call",
        )
    )

    scheduler = config.get("scheduler", {})
    kind = str(scheduler.get("kind", "none"))
    scheduler_state = read_json(root / ".journal" / "state" / "scheduler.json", {}) or {}
    state_status = scheduler_state.get("status") or scheduler.get("status") or "not-configured"
    if state_status == "active":
        checks.append(check("scheduler", "ok", f"{kind}: active", state=scheduler_state))
    elif kind == "codex-automation":
        checks.append(
            check(
                "scheduler",
                "warn",
                "Codex Automation is not verified active. Confirm it in Codex and run a manual test. Machine must be on, Codex running, and project path available.",
                state=state_status,
            )
        )
    elif kind == "claude-desktop":
        checks.append(check("scheduler", "warn", "Claude Desktop task is not verified active", state=state_status))
    elif kind == "system":
        checks.append(check("scheduler", "warn", "System scheduler is not verified active", state=state_status))
    else:
        checks.append(check("scheduler", "warn", "No scheduler selected"))

    latest_run = read_json(root / ".journal" / "state" / "last-run.json", None)
    if latest_run:
        checks.append(check("last-run", "ok" if latest_run.get("status") == "complete" else "warn", str(latest_run)))
    else:
        checks.append(check("last-run", "warn", "No completed journal run recorded"))

    if os.access(root, os.W_OK):
        checks.append(check("write-access", "ok", "Journal root is writable"))
    else:
        checks.append(check("write-access", "error", "Journal root is not writable"))

    statuses = [item["status"] for item in checks]
    overall = "error" if "error" in statuses else ("warn" if "warn" in statuses else "ok")
    return {
        "root": str(root),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": overall,
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else find_journal_root()
    report = diagnose(root)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        icons = {"ok": "OK", "warn": "WARN", "error": "ERROR"}
        print(f"Journal doctor: {report['root']} ({report['status']})")
        for item in report["checks"]:
            print(f"[{icons[item['status']]}] {item['name']}: {item['message']}")
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
