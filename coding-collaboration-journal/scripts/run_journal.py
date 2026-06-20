#!/usr/bin/env python3
"""Launch a journal mode through the configured non-interactive coding agent."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import find_journal_root, load_toml, write_json

PROMPTS = {
    "daily": "automation/daily.md",
    "weekly": "automation/weekly.md",
    "monthly": "automation/monthly.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("daily", "weekly", "monthly"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--command", help="Override runner command; prompt is appended as the final argument")
    return parser.parse_args()


def acquire_lock(path: Path, stale_seconds: int = 12 * 3600) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            age = 0
        if age > stale_seconds:
            path.unlink(missing_ok=True)
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        raise RuntimeError(f"Another journal run appears active: {path}")


def configured_command(config: dict[str, Any], override: str | None) -> list[str]:
    if override:
        return shlex.split(override)
    runner = config.get("runner", {})
    raw = runner.get("command", [])
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw]
    provider = str(runner.get("provider", "codex"))
    if provider == "claude":
        return ["claude", "-p"]
    return ["codex", "exec"]


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else find_journal_root()
    config = load_toml(root / ".journal" / "config.toml")
    prompt_path = root / PROMPTS[args.mode]
    if not prompt_path.is_file():
        raise SystemExit(f"Missing automation prompt: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8")
    command = configured_command(config, args.command)
    full_command = [*command, prompt]

    if args.dry_run:
        print(json.dumps({"cwd": str(root), "command": full_command[:-1], "prompt_path": str(prompt_path)}, ensure_ascii=False, indent=2))
        return 0

    lock_path = root / ".journal" / "state" / "run.lock"
    lock_fd = acquire_lock(lock_path)
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    os.write(lock_fd, f"pid={os.getpid()} started={started}\n".encode())
    os.close(lock_fd)
    logs = root / ".journal" / "state" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"{args.mode}-{stamp}.log"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"started={started}\ncommand={shlex.join(command)} <prompt:{prompt_path}>\n\n")
            log.flush()
            try:
                proc = subprocess.run(
                    full_command,
                    cwd=root,
                    text=True,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                returncode = proc.returncode
            except FileNotFoundError as exc:
                log.write(f"runner not found: {exc}\n")
                returncode = 127
        state = {
            "mode": args.mode,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "complete" if returncode == 0 else "failed",
            "returncode": returncode,
            "log": str(log_path.relative_to(root)),
            "runner": command,
        }
        write_json(root / ".journal" / "state" / "last-run.json", state)
        return returncode
    finally:
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
