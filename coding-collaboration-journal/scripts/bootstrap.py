#!/usr/bin/env python3
"""Create or upgrade a self-running AI coding collaboration journal.

The installer is intentionally idempotent. Files managed by the skill are updated
only when they still match the prior installed version. User-modified files are
preserved and the proposed replacement is written under .journal/conflicts/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from common import atomic_write, read_json, run_command, sha256_bytes, sha256_text, write_json

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "coding-collaboration-journal"
INSTALL_MANIFEST = Path(".journal/install-manifest.json")

OPERATIONAL_SCRIPTS = [
    "common.py",
    "capture_event.py",
    "claude_session_reader.py",
    "codex_app_server_reader.py",
    "collect_git.py",
    "collect_day.py",
    "doctor.py",
    "install_hooks.py",
    "render_scheduler.py",
    "run_journal.py",
    "validate_journal.py",
]
RUNTIME_REFERENCES = [
    "architecture.md",
    "source-adapters.md",
    "scheduler.md",
    "daily-runtime.md",
    "report-contract.md",
    "privacy-levels.md",
    "memory-model.md",
    "analysis-method.md",
    "external-practice-radar.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Journal repository directory")
    parser.add_argument("--name", default="AI Collaboration Journal")
    parser.add_argument("--sources", default="codex,claude", help="Comma-separated: codex,claude")
    parser.add_argument("--privacy", choices=("Low", "Medium", "High"), default="Low")
    parser.add_argument("--timezone", default="UTC", help="IANA timezone, e.g. Asia/Shanghai")
    parser.add_argument("--run-time", default="02:00", help="Daily local time in HH:MM")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument(
        "--scheduler",
        choices=("codex-automation", "claude-desktop", "system", "none"),
        default="codex-automation",
    )
    parser.add_argument("--install-system-scheduler", action="store_true")
    parser.add_argument("--runner", choices=("auto", "codex", "claude"), default="auto")
    parser.add_argument("--radar", choices=("weekly", "monthly", "disabled"), default="weekly")
    parser.add_argument("--remote", help="Git remote URL to attach as origin")
    parser.add_argument("--remote-name", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--git-user-name", help="Repository-local Git author name override")
    parser.add_argument("--git-user-email", help="Repository-local Git author email override")
    parser.add_argument("--init-git", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--auto-commit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--auto-push", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--install-hooks", action="store_true")
    parser.add_argument("--hook-scope", choices=("user", "project"), default="user")
    parser.add_argument("--hook-project", type=Path)
    parser.add_argument("--force", action="store_true", help="Replace user-modified managed files")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def parse_sources(value: str) -> list[str]:
    sources = []
    for item in value.split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized not in {"codex", "claude"}:
            raise ValueError(f"Unsupported source: {item}")
        if normalized not in sources:
            sources.append(normalized)
    if not sources:
        raise ValueError("At least one source is required")
    return sources


def validate_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid --run-time {value!r}; expected HH:MM") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid --run-time {value!r}; expected HH:MM")
    return hour, minute


def validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {value}") from exc


def toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_scalar(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {type(value).__name__}")


def render_config(args: argparse.Namespace, sources: list[str], runner: str) -> str:
    scheduler_status = {
        "codex-automation": "awaiting-user-confirmation",
        "claude-desktop": "awaiting-user-confirmation",
        "system": "rendered",
        "none": "disabled",
    }[args.scheduler]
    raw_transcripts = args.privacy != "High"
    sections: list[tuple[str | None, dict[str, Any]]] = [
        (
            None,
            {
                "schema_version": 1,
            },
        ),
        (
            "journal",
            {
                "name": args.name,
                "timezone": args.timezone,
                "daily_time": args.run_time,
                "language": args.language,
                "report_previous_day": True,
                "reconcile_days": 3,
                "history_days": 30,
                "date_layout": "journal/YYYY/MM/YYYY-MM-DD",
            },
        ),
        (
            "sources",
            {
                "codex": "codex" in sources,
                "claude": "claude" in sources,
                "git": True,
                "resources": True,
                "manual_notes": True,
            },
        ),
        (
            "privacy",
            {
                "level": args.privacy,
                "retain_raw_transcripts": raw_transcripts,
                "record_redactions": True,
                "custom_sensitive_terms": [],
                "exclude_paths": [
                    ".env",
                    ".env.*",
                    "*.pem",
                    "*.key",
                    "**/.git-credentials",
                    "**/credentials.json",
                ],
            },
        ),
        (
            "collection",
            {
                "codex_prefer_app_server": True,
                "claude_prefer_hook_transcript_path": True,
                "include_subagents": True,
                "include_uncommitted_git_changes": True,
                "copy_provider_native_records": raw_transcripts,
                "max_single_transcript_bytes": 104857600,
                "max_diff_bytes_per_repo": 20971520,
            },
        ),
        (
            "scheduler",
            {
                "kind": args.scheduler,
                "status": scheduler_status,
                "daily_time": args.run_time,
                "weekly_enabled": True,
                "weekly_day": "Monday",
                "monthly_enabled": True,
                "monthly_day": 1,
            },
        ),
        (
            "git",
            {
                "auto_commit": bool(args.auto_commit),
                "auto_push": bool(args.auto_push),
                "remote": args.remote_name,
                "remote_url": args.remote or "",
                "branch": args.branch,
                "pull_strategy": "rebase",
                "retry_pending_push": True,
            },
        ),
        (
            "radar",
            {
                "enabled": args.radar != "disabled",
                "cadence": args.radar if args.radar != "disabled" else "disabled",
                "mode": "targeted",
                "prefer_primary_sources": True,
            },
        ),
        (
            "memory",
            {
                "status": "beta",
                "auto_update": True,
                "write_approval": False,
                "inject_on_session_start": False,
                "briefing_char_limit": 6000,
                "briefing_hard_limit": 10000,
                "candidate_repeat_threshold": 2,
                "active_repeat_threshold": 3,
            },
        ),
        (
            "autonomy",
            {
                "daily_reports": "automatic",
                "memory_updates": "automatic",
                "pattern_updates": "automatic",
                "experiment_proposals": "automatic",
                "workflow_file_changes": "proposal",
                "external_research": "automatic_when_triggered",
                "git_commit": "automatic" if args.auto_commit else "manual",
                "git_push": "automatic" if args.auto_push else "manual",
            },
        ),
        (
            "runner",
            {
                "provider": runner,
                "command": [],
            },
        ),
    ]
    lines = ["# Managed initially by coding-collaboration-journal. User edits are supported."]
    for section, values in sections:
        if section:
            lines.extend(["", f"[{section}]"])
        for key, value in values.items():
            lines.append(f"{key} = {toml_scalar(value)}")
    return "\n".join(lines) + "\n"


def scheduler_note(kind: str) -> str:
    if kind == "codex-automation":
        return (
            "Codex Automation（推荐）：需在 Codex 中完成任务确认。项目型任务运行时，"
            "电脑必须开机、Codex 必须运行，而且日志仓库路径必须仍然可用。"
        )
    if kind == "claude-desktop":
        return "Claude Desktop Scheduled Task：需在 Desktop 中确认任务；执行时电脑必须开机。"
    if kind == "system":
        return "系统调度器：由 launchd、systemd user timer 或 Windows Task Scheduler 运行。"
    return "未启用自动调度；可手动运行 python3 scripts/run_journal.py daily。"


def choose_runner(requested: str, sources: list[str]) -> str:
    if requested != "auto":
        if requested not in sources:
            raise ValueError(f"Runner {requested} is not enabled in --sources")
        return requested
    if "codex" in sources:
        return "codex"
    return "claude"


def template_values(args: argparse.Namespace, sources: list[str]) -> dict[str, str]:
    return {
        "JOURNAL_NAME": args.name,
        "DAILY_TIME": args.run_time,
        "TIMEZONE": args.timezone,
        "SOURCES": ", ".join(sources),
        "PRIVACY": args.privacy,
        "SCHEDULER": args.scheduler,
        "AUTO_SYNC": "commit + push" if args.auto_commit and args.auto_push else ("commit" if args.auto_commit else "manual"),
        "RADAR": args.radar,
        "SCHEDULER_NOTE": scheduler_note(args.scheduler),
    }


def collect_desired_files(args: argparse.Namespace, sources: list[str], runner: str) -> dict[str, bytes]:
    desired: dict[str, bytes] = {}
    values = template_values(args, sources)
    scaffold = SKILL_ROOT / "assets" / "scaffold"

    for source in scaffold.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(scaffold)
        # Language-specific template variants are selected below.
        if relative.name in {"README.en.md.tpl", "report.en.md"}:
            continue
        target = relative
        if relative.name.endswith(".tpl"):
            target = relative.with_name(relative.name[:-4])
        text = source.read_text(encoding="utf-8")
        if relative.name.endswith(".tpl"):
            text = Template(text).safe_substitute(values)
        desired[target.as_posix()] = text.encode("utf-8")

    language = args.language.lower()
    if language.startswith("en"):
        english_readme = scaffold / "README.en.md.tpl"
        english_report = scaffold / "templates" / "report.en.md"
        if english_readme.is_file():
            desired["README.md"] = Template(english_readme.read_text(encoding="utf-8")).safe_substitute(values).encode("utf-8")
        if english_report.is_file():
            desired["templates/report.md"] = english_report.read_bytes()

    for prompt_name in ("daily.md", "weekly.md", "monthly.md"):
        desired[f"automation/{prompt_name}"] = (SKILL_ROOT / "assets" / "prompts" / prompt_name).read_bytes()

    for script_name in OPERATIONAL_SCRIPTS:
        desired[f"scripts/{script_name}"] = (SKILL_ROOT / "scripts" / script_name).read_bytes()

    for reference_name in RUNTIME_REFERENCES:
        desired[f"docs/method/{reference_name}"] = (SKILL_ROOT / "references" / reference_name).read_bytes()

    desired[".journal/config.toml"] = render_config(args, sources, runner).encode("utf-8")
    desired[".journal/scheduler/codex-automation.md"] = codex_automation_instruction(args).encode("utf-8")
    desired[".journal/scheduler/claude-desktop-task.md"] = claude_task_instruction(args).encode("utf-8")
    desired[".journal/notes/.gitkeep"] = b""
    desired[".journal/events/.gitkeep"] = b""
    desired[".journal/state/.gitkeep"] = b""
    desired["journal/.gitkeep"] = b""
    desired["reviews/weekly/.gitkeep"] = b""
    desired["reviews/monthly/.gitkeep"] = b""
    return desired


def codex_automation_instruction(args: argparse.Namespace) -> str:
    return f"""# Codex Automation setup\n\n- Name: `AI Collaboration Journal — Daily`\n- Project: `{args.output.expanduser().resolve()}`\n- Schedule: every day at `{args.run_time}` in `{args.timezone}`\n- Prompt: use the contents of `automation/daily.md`. That prompt is self-contained for routine operation and points the agent at this repository's installed runtime files.\n\nOperational conditions: the computer must be powered on, Codex must be running, and this project path must remain available on disk. After creating the Automation, run it manually once and verify report artifacts, commit, and push before marking it active.\n"""


def claude_task_instruction(args: argparse.Namespace) -> str:
    return f"""# Claude Desktop scheduled task setup\n\n- Name: `AI Collaboration Journal — Daily`\n- Project: `{args.output.expanduser().resolve()}`\n- Schedule: every day at `{args.run_time}` in `{args.timezone}`\n- Prompt: run the instructions in `automation/daily.md`. That prompt is self-contained for routine operation and points the agent at this repository's installed runtime files.\n\nThe computer must be powered on. Run one manual smoke test and verify report artifacts, commit, and push before marking the task active. Do not use an in-session `/loop` as the durable scheduler.\n"""


def conflict_path(root: Path, relative: str) -> Path:
    safe = relative.replace("/", "__")
    return root / ".journal" / "conflicts" / f"{safe}.new"


def install_files(root: Path, desired: dict[str, bytes], force: bool, dry_run: bool) -> dict[str, Any]:
    manifest_path = root / INSTALL_MANIFEST
    old_manifest = read_json(manifest_path, {}) or {}
    old_files = old_manifest.get("files", {}) if isinstance(old_manifest, dict) else {}
    if not isinstance(old_files, dict):
        old_files = {}

    actions: list[dict[str, str]] = []
    new_entries: dict[str, dict[str, str]] = {}
    conflicts: list[dict[str, str]] = []

    for relative in sorted(desired):
        payload = desired[relative]
        target = root / relative
        proposed_hash = sha256_bytes(payload)
        prior = old_files.get(relative, {})
        prior_managed = prior.get("managed_sha256") if isinstance(prior, dict) else None
        current_hash = sha256_bytes(target.read_bytes()) if target.is_file() else None

        if current_hash == proposed_hash:
            action = "unchanged"
            managed_hash = proposed_hash
        elif current_hash is None:
            action = "create"
            managed_hash = proposed_hash
            if not dry_run:
                atomic_write(target, payload)
        elif force or (prior_managed and current_hash == prior_managed):
            action = "update"
            managed_hash = proposed_hash
            if not dry_run:
                atomic_write(target, payload)
        elif prior_managed and proposed_hash == prior_managed:
            # The user changed the installed file, while this skill version has not
            # changed its managed baseline. Preserve the edit quietly: producing a
            # conflict copy on every idempotent re-run would create meaningless drift.
            action = "preserve-user-modification"
            managed_hash = prior_managed
        else:
            action = "preserve-user-modification"
            managed_hash = prior_managed or current_hash
            proposed_path = conflict_path(root, relative)
            conflicts.append({
                "path": relative,
                "current_sha256": current_hash,
                "proposed_sha256": proposed_hash,
                "proposed_path": str(proposed_path.relative_to(root)),
            })
            if not dry_run:
                atomic_write(proposed_path, payload)

        actions.append({"path": relative, "action": action})
        new_entries[relative] = {
            "managed_sha256": managed_hash,
            "proposed_sha256": proposed_hash,
        }

    manifest_core = {
        "schema_version": 1,
        "skill": SKILL_NAME,
        "files": new_entries,
        "conflicts": conflicts,
    }
    old_core = {key: old_manifest.get(key) for key in manifest_core} if isinstance(old_manifest, dict) else {}
    if old_core == manifest_core and isinstance(old_manifest.get("updated_at"), str):
        result_manifest = old_manifest
    else:
        result_manifest = {
            **manifest_core,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if not dry_run:
            write_json(manifest_path, result_manifest)
    return {"actions": actions, "conflicts": conflicts, "manifest": result_manifest}


def ensure_executable(root: Path, desired: dict[str, bytes], dry_run: bool) -> None:
    if dry_run:
        return
    for relative in desired:
        if relative.startswith("scripts/") and relative.endswith(".py"):
            path = root / relative
            try:
                path.chmod(path.stat().st_mode | 0o111)
            except OSError:
                pass


def git_setup(root: Path, args: argparse.Namespace, installed_paths: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "initialized": False,
        "commit": None,
        "push": None,
        "errors": [],
        "warnings": [],
        "fatal_errors": [],
        "identity": None,
    }

    def fatal(message: str) -> None:
        cleaned = message.strip() or "Git operation failed"
        result["errors"].append(cleaned)
        result["fatal_errors"].append(cleaned)

    def warn(message: str) -> None:
        cleaned = message.strip() or "Git operation needs attention"
        result["errors"].append(cleaned)
        result["warnings"].append(cleaned)

    if not args.init_git:
        return result

    if not (root / ".git").exists():
        init = run_command(["git", "init", "-b", args.branch], cwd=root, timeout=30)
        if not init["ok"]:
            init = run_command(["git", "init"], cwd=root, timeout=30)
            if init["ok"]:
                run_command(["git", "checkout", "-B", args.branch], cwd=root, timeout=30)
        if not init["ok"]:
            fatal(init["stderr"].strip() or "git init failed")
            return result
        result["initialized"] = True

    current_remote = run_command(["git", "remote", "get-url", args.remote_name], cwd=root, timeout=10)
    if args.remote:
        if current_remote["ok"]:
            existing = current_remote["stdout"].strip()
            if existing != args.remote:
                if args.force:
                    changed = run_command(["git", "remote", "set-url", args.remote_name, args.remote], cwd=root, timeout=10)
                    if not changed["ok"]:
                        warn(changed["stderr"].strip() or f"Could not update remote {args.remote_name}")
                else:
                    warn(
                        f"Remote {args.remote_name} already points to {existing}; use --force to replace it"
                    )
        else:
            added = run_command(["git", "remote", "add", args.remote_name, args.remote], cwd=root, timeout=10)
            if not added["ok"]:
                warn(added["stderr"].strip() or f"Could not add remote {args.remote_name}")

    if args.auto_commit:
        if args.git_user_name:
            configured_name = run_command(
                ["git", "config", "--local", "user.name", args.git_user_name],
                cwd=root,
                timeout=10,
            )
            if not configured_name["ok"]:
                fatal(configured_name["stderr"].strip() or "Could not configure repository-local Git user.name")
                return result
        if args.git_user_email:
            configured_email = run_command(
                ["git", "config", "--local", "user.email", args.git_user_email],
                cwd=root,
                timeout=10,
            )
            if not configured_email["ok"]:
                fatal(configured_email["stderr"].strip() or "Could not configure repository-local Git user.email")
                return result

        identity_name = run_command(["git", "config", "--get", "user.name"], cwd=root, timeout=10)
        identity_email = run_command(["git", "config", "--get", "user.email"], cwd=root, timeout=10)
        configured_name = identity_name["stdout"].strip() if identity_name["ok"] else ""
        configured_email = identity_email["stdout"].strip() if identity_email["ok"] else ""
        environment_name = os.environ.get("GIT_AUTHOR_NAME", "").strip() or os.environ.get(
            "GIT_COMMITTER_NAME", ""
        ).strip()
        environment_email = os.environ.get("GIT_AUTHOR_EMAIL", "").strip() or os.environ.get(
            "GIT_COMMITTER_EMAIL", ""
        ).strip()
        name = configured_name or environment_name
        email = configured_email or environment_email
        if not name or not email:
            missing = []
            if not name:
                missing.append("user.name")
            if not email:
                missing.append("user.email")
            fatal(
                "Git author identity is missing ("
                + ", ".join(missing)
                + "). Re-run with --git-user-name and --git-user-email, or configure Git before enabling automatic commits."
            )
            return result
        if args.git_user_name or args.git_user_email:
            identity_source = "repository-local"
        elif configured_name and configured_email:
            identity_source = "git-config"
        else:
            identity_source = "environment"
        result["identity"] = {
            "name": name,
            "email": email,
            "source": identity_source,
            "repository_local_override": bool(args.git_user_name or args.git_user_email),
        }

        paths = sorted(set(installed_paths + [INSTALL_MANIFEST.as_posix()]))
        add_result = run_command(["git", "add", "--", *paths], cwd=root, timeout=60)
        if not add_result["ok"]:
            fatal(add_result["stderr"].strip() or "git add failed")
            return result
        diff = run_command(["git", "diff", "--cached", "--quiet"], cwd=root, timeout=30)
        # git diff --quiet returns 1 when there are staged changes.
        if diff["returncode"] == 1:
            commit = run_command(
                ["git", "commit", "-m", "chore: install coding collaboration journal"],
                cwd=root,
                timeout=60,
            )
            if commit["ok"]:
                sha = run_command(["git", "rev-parse", "HEAD"], cwd=root, timeout=10)
                result["commit"] = sha["stdout"].strip() if sha["ok"] else "created"
            else:
                fatal(commit["stderr"].strip() or "git commit failed")
        elif diff["returncode"] == 0:
            result["commit"] = "no-change"
        else:
            fatal(diff["stderr"].strip() or "git diff failed")

    if args.auto_push and result.get("commit") not in {None, "no-change"}:
        remote_probe = run_command(["git", "remote", "get-url", args.remote_name], cwd=root, timeout=10)
        if remote_probe["ok"]:
            push = run_command(
                ["git", "push", "-u", args.remote_name, args.branch], cwd=root, timeout=120
            )
            if push["ok"]:
                result["push"] = "complete"
            else:
                result["push"] = "pending"
                warn(push["stderr"].strip() or "git push failed")
                if not args.dry_run:
                    write_json(
                        root / ".journal" / "state" / "pending-push.json",
                        {
                            "remote": args.remote_name,
                            "branch": args.branch,
                            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "error": push["stderr"].strip(),
                        },
                    )
        else:
            result["push"] = "not-configured"
    return result


def install_hooks(root: Path, args: argparse.Namespace, sources: list[str]) -> dict[str, Any]:
    if not args.install_hooks or args.dry_run:
        return {"status": "skipped" if not args.install_hooks else "dry-run"}
    source_arg = "both" if set(sources) == {"codex", "claude"} else sources[0]
    command = [
        sys.executable,
        str(root / "scripts" / "install_hooks.py"),
        "--root",
        str(root),
        "--source",
        source_arg,
        "--scope",
        args.hook_scope,
    ]
    if args.hook_scope == "project":
        project = args.hook_project or root
        command.extend(["--project", str(project.expanduser().resolve())])
    proc = run_command(command, cwd=root, timeout=60)
    return {
        "status": "complete" if proc["ok"] else "failed",
        "stdout": proc["stdout"].strip(),
        "stderr": proc["stderr"].strip(),
    }


def configure_scheduler(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run:
        return {"kind": args.scheduler, "status": "dry-run"}
    if args.scheduler == "system":
        command = [sys.executable, str(root / "scripts" / "render_scheduler.py"), "--root", str(root)]
        if args.install_system_scheduler:
            command.append("--install")
        proc = run_command(command, cwd=root, timeout=90)
        result: dict[str, Any] = {
            "kind": "system",
            "status": "active" if args.install_system_scheduler and proc["ok"] else ("rendered" if proc["ok"] else "failed"),
            "stdout": proc["stdout"].strip(),
            "stderr": proc["stderr"].strip(),
        }
        if proc["ok"]:
            try:
                rendered = json.loads(proc["stdout"])
            except json.JSONDecodeError:
                rendered = {}
            result["files"] = rendered.get("files", []) if isinstance(rendered, dict) else []
        return result
    status = "awaiting-user-confirmation" if args.scheduler != "none" else "disabled"
    state_path = root / ".journal" / "state" / "scheduler.json"
    state_core = {
        "kind": args.scheduler,
        "status": status,
        "schedule": args.run_time,
        "timezone": args.timezone,
    }
    existing = read_json(state_path, {}) or {}
    existing_core = {key: existing.get(key) for key in state_core} if isinstance(existing, dict) else {}
    if existing_core == state_core and isinstance(existing.get("updated_at"), str):
        state = dict(existing)
    else:
        state = {
            **state_core,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        write_json(state_path, state)
    state["files"] = [".journal/state/scheduler.json"]
    return state


def main() -> int:
    args = parse_args()
    try:
        sources = parse_sources(args.sources)
        validate_time(args.run_time)
        validate_timezone(args.timezone)
        runner = choose_runner(args.runner, sources)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    root = args.output.expanduser().resolve()
    if not args.dry_run:
        root.mkdir(parents=True, exist_ok=True)
    desired = collect_desired_files(args, sources, runner)
    install_result = install_files(root, desired, args.force, args.dry_run)
    ensure_executable(root, desired, args.dry_run)
    scheduler_result = configure_scheduler(root, args)
    hooks_result = install_hooks(root, args, sources)
    installed_paths = [item["path"] for item in install_result["actions"] if item["action"] != "preserve-user-modification"]
    installed_paths.extend(item["proposed_path"] for item in install_result["conflicts"])
    if not args.dry_run:
        scheduler_paths = scheduler_result.get("files", []) if isinstance(scheduler_result, dict) else []
        installed_paths.extend(path for path in scheduler_paths if isinstance(path, str))
        scheduler_state = root / ".journal" / "state" / "scheduler.json"
        if scheduler_state.is_file():
            installed_paths.append(scheduler_state.relative_to(root).as_posix())
    git_result = git_setup(root, args, installed_paths) if not args.dry_run else {"status": "dry-run"}

    summary = {
        "root": str(root),
        "sources": sources,
        "privacy": args.privacy,
        "timezone": args.timezone,
        "daily_time": args.run_time,
        "scheduler": scheduler_result,
        "hooks": hooks_result,
        "git": git_result,
        "files": {
            "created": sum(item["action"] == "create" for item in install_result["actions"]),
            "updated": sum(item["action"] == "update" for item in install_result["actions"]),
            "unchanged": sum(item["action"] == "unchanged" for item in install_result["actions"]),
            "preserved": sum(item["action"] == "preserve-user-modification" for item in install_result["actions"]),
        },
        "conflicts": install_result["conflicts"],
        "next_action": (
            "Confirm the generated Codex Automation in the Codex UI and run one smoke test."
            if args.scheduler == "codex-automation"
            else (
                "Confirm the generated task in Claude Desktop and run one smoke test."
                if args.scheduler == "claude-desktop"
                else "Run doctor.py and a manual daily dry run."
            )
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    fatal = bool(git_result.get("fatal_errors")) and args.auto_commit
    # Preserved edits are a successful safe upgrade, not a fatal install error.
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
