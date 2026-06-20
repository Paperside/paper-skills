#!/usr/bin/env python3
"""Idempotently merge journal capture hooks into Codex and Claude Code settings."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import atomic_write

CODEX_EVENTS = ["SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "SubagentStart", "SubagentStop"]
CLAUDE_EVENTS = [
    "SessionStart",
    "UserPromptSubmit",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "SessionEnd",
    "SubagentStart",
    "SubagentStop",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Installed journal root")
    parser.add_argument("--source", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project", type=Path, help="Project path for project scope")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot merge invalid JSON settings file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def hook_command(root: Path, source: str) -> str:
    python = Path(sys.executable).resolve()
    script = (root / "scripts" / "capture_event.py").resolve()
    # JSON settings pass this to a shell on supported clients. Quote both paths.
    return f'"{python}" "{script}" --source {source} --root "{root.resolve()}"'


def group_for(event: str, command: str, provider: str) -> dict[str, Any]:
    group: dict[str, Any] = {
        "hooks": [{"type": "command", "command": command, "timeout": 10}]
    }
    if event in {"PostToolUse", "PostToolUseFailure"}:
        group["matcher"] = ".*" if provider == "codex" else "*"
    return group


def merge_hooks(document: dict[str, Any], provider: str, command: str) -> tuple[dict[str, Any], int]:
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing 'hooks' value is not an object")
    events = CODEX_EVENTS if provider == "codex" else CLAUDE_EVENTS
    added = 0
    for event in events:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Existing hooks.{event} is not a list")
        exists = False
        for group in groups:
            if not isinstance(group, dict):
                continue
            for handler in group.get("hooks", []):
                if isinstance(handler, dict) and handler.get("command") == command:
                    exists = True
                    break
            if exists:
                break
        if not exists:
            groups.append(group_for(event, command, provider))
            added += 1
    return document, added


def settings_path(provider: str, scope: str, project: Path | None) -> Path:
    home = Path.home()
    if scope == "user":
        return home / (".codex/hooks.json" if provider == "codex" else ".claude/settings.json")
    if not project:
        raise ValueError("--project is required for project scope")
    project = project.expanduser().resolve()
    return project / (".codex/hooks.json" if provider == "codex" else ".claude/settings.local.json")


def write_with_backup(path: Path, document: dict[str, Any], dry_run: bool) -> Path | None:
    rendered = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if dry_run:
        print(f"--- {path} ---")
        print(rendered)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == rendered:
                return None
        except OSError:
            # Fall through to the normal backup-and-rewrite path.
            pass
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.bak.{stamp}")
        shutil.copy2(path, backup)
    atomic_write(path, rendered)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return backup


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    providers = ["codex", "claude"] if args.source == "both" else [args.source]
    result = []
    for provider in providers:
        path = settings_path(provider, args.scope, args.project)
        document = load_json(path)
        command = hook_command(root, provider)
        merged, added = merge_hooks(document, provider, command)
        backup = write_with_backup(path, merged, args.dry_run)
        result.append({"provider": provider, "path": str(path), "added_groups": added, "backup": str(backup) if backup else None})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
