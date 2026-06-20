#!/usr/bin/env python3
"""Render and optionally install OS scheduler files for an installed journal."""
from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import find_journal_root, load_toml, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--kind", choices=("auto", "launchd", "systemd", "windows"), default="auto")
    parser.add_argument("--install", action="store_true")
    return parser.parse_args()


def choose_kind(requested: str) -> str:
    if requested != "auto":
        return requested
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Windows":
        return "windows"
    return "systemd"


def parse_time(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid daily_time: {value}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid daily_time: {value}")
    return hour, minute


def command(root: Path) -> list[str]:
    return [str(Path(sys.executable).resolve()), str((root / "scripts" / "run_journal.py").resolve()), "daily", "--root", str(root)]


def systemd_quote(value: str) -> str:
    """Quote one systemd command argument without invoking a shell.

    systemd performs its own command-line tokenization and `%` specifier
    expansion. Doubling `%` and double-quoting every argument keeps paths with
    spaces, quotes, and backslashes intact.
    """
    escaped = value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_launchd(root: Path, hour: int, minute: int) -> Path:
    target = root / ".journal" / "scheduler" / "com.paperside.ai-collaboration-journal.plist"
    logs = root / ".journal" / "state" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": "com.paperside.ai-collaboration-journal",
        "ProgramArguments": command(root),
        "WorkingDirectory": str(root),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(logs / "launchd.stdout.log"),
        "StandardErrorPath": str(logs / "launchd.stderr.log"),
        "ProcessType": "Background",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)
    return target


def render_systemd(root: Path, hour: int, minute: int) -> tuple[Path, Path]:
    directory = root / ".journal" / "scheduler"
    directory.mkdir(parents=True, exist_ok=True)
    service = directory / "ai-collaboration-journal.service"
    timer = directory / "ai-collaboration-journal.timer"
    cmd = " ".join(systemd_quote(arg) for arg in command(root))
    working_directory = systemd_quote(str(root))
    service.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=AI Collaboration Journal daily run",
                "",
                "[Service]",
                "Type=oneshot",
                f"WorkingDirectory={working_directory}",
                f"ExecStart={cmd}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    timer.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Run AI Collaboration Journal daily",
                "",
                "[Timer]",
                f"OnCalendar=*-*-* {hour:02d}:{minute:02d}:00",
                "Persistent=true",
                "Unit=ai-collaboration-journal.service",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return service, timer


def render_windows(root: Path, hour: int, minute: int) -> Path:
    target = root / ".journal" / "scheduler" / "install-windows-task.ps1"
    target.parent.mkdir(parents=True, exist_ok=True)
    args = command(root)
    executable = args[0].replace("'", "''")
    argument = subprocess.list2cmdline(args[1:]).replace("'", "''")
    content = f'''$action = New-ScheduledTaskAction -Execute '{executable}' -Argument '{argument}' -WorkingDirectory '{str(root).replace("'", "''")}'
$trigger = New-ScheduledTaskTrigger -Daily -At '{hour:02d}:{minute:02d}'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName 'AI Collaboration Journal Daily' -Action $action -Trigger $trigger -Settings $settings -Force
'''
    target.write_text(content, encoding="utf-8")
    return target


def install_launchd(path: Path) -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)


def install_systemd(service: Path, timer: Path) -> None:
    target = Path.home() / ".config" / "systemd" / "user"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(service, target / service.name)
    shutil.copy2(timer, target / timer.name)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", timer.name], check=True)


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else find_journal_root()
    config = load_toml(root / ".journal" / "config.toml")
    hour, minute = parse_time(str(config.get("journal", {}).get("daily_time", "02:00")))
    kind = choose_kind(args.kind)
    files: list[Path] = []
    installed = False
    if kind == "launchd":
        path = render_launchd(root, hour, minute)
        files = [path]
        if args.install:
            install_launchd(path)
            installed = True
    elif kind == "systemd":
        service, timer = render_systemd(root, hour, minute)
        files = [service, timer]
        if args.install:
            install_systemd(service, timer)
            installed = True
    else:
        path = render_windows(root, hour, minute)
        files = [path]
        if args.install:
            if platform.system() != "Windows":
                raise SystemExit("Windows task installation must run on Windows")
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(path)], check=True)
            installed = True

    state = {
        "kind": kind,
        "status": "active" if installed else "rendered",
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": [str(path.relative_to(root)) for path in files],
        "schedule": f"{hour:02d}:{minute:02d}",
    }
    write_json(root / ".journal" / "state" / "scheduler.json", state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
