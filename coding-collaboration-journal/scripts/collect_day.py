#!/usr/bin/env python3
"""Collect one local calendar day's Codex, Claude, hook, Git, and note evidence.

This script is the stable collection entrypoint installed into every journal. It
normalizes provider-specific readers into a single collection manifest while
keeping provider-native details in the day's sources directory.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from common import find_journal_root, load_toml, read_json, run_command, sanitize, sha256_bytes, utc_now_iso, write_json


WORKSPACE_KEYS = {
    "cwd",
    "working_directory",
    "workingdirectory",
    "workspace",
    "workspace_path",
    "workspacepath",
    "project_path",
    "projectpath",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--date", help="Local report date YYYY-MM-DD; default is yesterday")
    parser.add_argument("--repo", type=Path, action="append", default=[])
    parser.add_argument("--codex", default="codex")
    parser.add_argument(
        "--scan-all-claude",
        action="store_true",
        help="Scan the full Claude Code session store (automatically enabled for historical backfills)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def parse_date(value: str | None, zone: ZoneInfo) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(zone).date() - timedelta(days=1)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def should_scan_all_claude(
    report_date: date,
    local_today: date,
    reconcile_days: int,
    explicit: bool,
) -> bool:
    """Use a full session-store scan for deliberate historical backfills.

    Claude session files can have a recent mtime even when they contain older
    records, and old files can have a stale mtime outside the normal daily scan
    window. Recent reconciliation stays cheap; older requested dates favor
    completeness.
    """
    if explicit:
        return True
    threshold = local_today - timedelta(days=max(1, reconcile_days))
    return report_date < threshold


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def parse_instant(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        # Milliseconds are common in JS-oriented records.
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def collect_hooks(
    events_root: Path,
    start: datetime,
    end: datetime,
    output: Path,
    privacy: str,
    custom_terms: list[str],
) -> dict[str, Any]:
    """Read hook rows and reapply today's privacy policy before persistence.

    The returned payload remains available transiently for source discovery. The
    on-disk artifact is always sanitized with the current policy, so changing from
    Low to Medium/High also affects previously captured events when they are copied
    into a daily report.
    """
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    files = sorted(events_root.rglob("*.jsonl")) if events_root.exists() else []
    for path in files:
        try:
            for item in load_json_lines(path):
                when = parse_instant(item.get("captured_at"))
                if when is not None and start <= when < end:
                    rows.append(item)
        except OSError as exc:
            errors.append({"path": str(path), "message": str(exc)})
    rows.sort(key=lambda item: str(item.get("captured_at", "")))
    payload = {
        "schema_version": 1,
        "adapter": "hook-event-index",
        "collected_at": utc_now_iso(),
        "window": {"start": iso_utc(start), "end": iso_utc(end)},
        "event_file_count": len(files),
        "event_count": len(rows),
        "events": rows,
        "errors": errors,
        "coverage": "complete" if not errors else ("partial" if rows else "unavailable"),
    }
    write_json(output, sanitize(payload, privacy, custom_terms))
    return payload


def custom_term_args(config: dict[str, Any]) -> list[str]:
    terms = config.get("privacy", {}).get("custom_sensitive_terms", [])
    result: list[str] = []
    if isinstance(terms, list):
        for term in terms:
            result.extend(["--custom-sensitive-term", str(term)])
    return result


def invoke_adapter(
    command: list[str],
    output: Path,
    cwd: Path,
    privacy: str,
    custom_terms: list[str],
    timeout: int = 600,
) -> dict[str, Any]:
    """Run an adapter, retain its Low-level output transiently, persist at policy.

    Collection commands are intentionally invoked with Low privacy: credentials are
    still removed by the adapter, while workspace paths remain available long enough
    to discover associated Git repositories. This function then reapplies the chosen
    Low/Medium/High policy before the source artifact reaches the journal.
    """
    result = run_command(command, cwd=cwd, timeout=timeout)
    payload = read_json(output, None)
    if not isinstance(payload, dict):
        payload = {
            "coverage": "unavailable",
            "errors": [{"stage": "adapter", "message": "Adapter produced no valid JSON"}],
        }
    payload.setdefault("process", {})
    if isinstance(payload["process"], dict):
        payload["process"].update(
            {
                "returncode": result.get("returncode"),
                "stderr": result.get("stderr", "")[-8000:],
            }
        )
    write_json(output, sanitize(payload, privacy, custom_terms))
    return payload


def provider_coverage(native: dict[str, Any] | None, hook_events: list[dict[str, Any]], provider: str) -> str:
    native_coverage = native.get("coverage") if isinstance(native, dict) else "unavailable"
    provider_hooks = [item for item in hook_events if item.get("source") == provider]
    if native_coverage == "complete":
        return "complete"
    if native_coverage == "partial" or provider_hooks:
        return "partial"
    return "unavailable"


def walk_workspace_paths(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).replace("-", "_").lower()
            if key in WORKSPACE_KEYS and isinstance(child, str) and child:
                yield child
            else:
                yield from walk_workspace_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_workspace_paths(child)


def discover_repo_candidates(*values: Any) -> set[Path]:
    candidates: set[Path] = set()
    for value in values:
        for raw in walk_workspace_paths(value):
            try:
                candidate = Path(raw).expanduser().resolve()
            except (OSError, RuntimeError):
                continue
            if candidate.is_dir():
                candidates.add(candidate)
    return candidates


def has_git_activity(payload: dict[str, Any]) -> bool:
    for repo in payload.get("repositories", []):
        if not isinstance(repo, dict):
            continue
        if repo.get("commits"):
            return True
        reflog = repo.get("reflog", {})
        if isinstance(reflog, dict) and str(reflog.get("stdout", "")).strip():
            return True
        for key in ("unstaged_diff", "staged_diff"):
            diff = repo.get(key, {})
            if isinstance(diff, dict) and str(diff.get("stdout", "")).strip():
                return True
    return False


def determine_status(sources: dict[str, dict[str, Any]], activity: bool) -> tuple[str, str]:
    coverages = [str(value.get("coverage", "unavailable")) for value in sources.values() if value.get("enabled", True)]
    complete = bool(coverages) and all(value == "complete" for value in coverages)
    if complete:
        return ("active" if activity else "no-activity", "complete")
    available = any(value in {"complete", "partial"} for value in coverages)
    if activity:
        return "partial-activity", "partial" if available else "unavailable"
    return "incomplete-collection", "partial" if available else "unavailable"


def disabled_state() -> dict[str, Any]:
    return {"enabled": False, "coverage": "disabled"}


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else find_journal_root()
    config_path = root / ".journal" / "config.toml"
    config = load_toml(config_path)
    timezone_name = str(config.get("journal", {}).get("timezone", "UTC"))
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise SystemExit(f"Unknown IANA timezone in config: {timezone_name}") from exc

    report_date = parse_date(args.date, zone)
    reconcile_days = int(config.get("journal", {}).get("reconcile_days", 3))
    claude_scan_all = should_scan_all_claude(
        report_date,
        datetime.now(zone).date(),
        reconcile_days,
        args.scan_all_claude,
    )
    start_local = datetime.combine(report_date, datetime.min.time(), tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    day_dir = root / "journal" / f"{report_date.year:04d}" / f"{report_date.month:02d}" / report_date.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    tmp_parent = root / ".journal" / "state" / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f"collect-{report_date}-", dir=tmp_parent))
    source_dir = temp_dir / "sources"
    source_dir.mkdir(parents=True)

    privacy = str(config.get("privacy", {}).get("level", "Low"))
    source_config = config.get("sources", {})
    terms = custom_term_args(config)
    custom_terms = [str(item) for item in config.get("privacy", {}).get("custom_sensitive_terms", [])]
    collection_config = config.get("collection", {})
    scripts = root / "scripts"
    source_states: dict[str, dict[str, Any]] = {}
    collection: dict[str, Any] = {}

    codex_enabled = bool(source_config.get("codex", False))
    claude_enabled = bool(source_config.get("claude", False))
    git_enabled = bool(source_config.get("git", True))
    manual_enabled = bool(source_config.get("manual_notes", True))

    try:
        hooks = collect_hooks(
            root / ".journal" / "events",
            start_utc,
            end_utc,
            source_dir / "hooks.json",
            privacy,
            custom_terms,
        )
        hook_events = hooks.get("events", []) if isinstance(hooks.get("events"), list) else []

        codex_payload: dict[str, Any] | None = None
        if codex_enabled:
            codex_output = source_dir / "codex.json"
            codex_payload = invoke_adapter(
                [
                    sys.executable,
                    str(scripts / "codex_app_server_reader.py"),
                    "--start",
                    iso_utc(start_utc),
                    "--end",
                    iso_utc(end_utc),
                    "--output",
                    str(codex_output),
                    "--codex",
                    args.codex,
                    # Low preserves workspace paths transiently; invoke_adapter
                    # reapplies the configured level before persistence.
                    "--privacy",
                    "Low",
                    *terms,
                ],
                codex_output,
                root,
                privacy,
                custom_terms,
            )
            source_states["codex"] = {
                "enabled": True,
                "coverage": provider_coverage(codex_payload, hook_events, "codex"),
                "native_coverage": codex_payload.get("coverage", "unavailable"),
                "hook_event_count": sum(item.get("source") == "codex" for item in hook_events),
                "artifact": "sources/codex.json",
            }
        else:
            source_states["codex"] = disabled_state()

        claude_payload: dict[str, Any] | None = None
        if claude_enabled:
            claude_output = source_dir / "claude.json"
            claude_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser() / "projects"
            claude_command = [
                sys.executable,
                str(scripts / "claude_session_reader.py"),
                "--start",
                iso_utc(start_utc),
                "--end",
                iso_utc(end_utc),
                "--output",
                str(claude_output),
                "--events-root",
                str(root / ".journal" / "events"),
                "--claude-root",
                str(claude_root),
                "--max-file-bytes",
                str(int(collection_config.get("max_single_transcript_bytes", 100 * 1024 * 1024))),
                "--privacy",
                "Low",
                *terms,
            ]
            if claude_scan_all:
                claude_command.append("--scan-all")
            claude_payload = invoke_adapter(
                claude_command,
                claude_output,
                root,
                privacy,
                custom_terms,
            )
            source_states["claude"] = {
                "enabled": True,
                "coverage": provider_coverage(claude_payload, hook_events, "claude"),
                "native_coverage": claude_payload.get("coverage", "unavailable"),
                "hook_event_count": sum(item.get("source") == "claude" for item in hook_events),
                "artifact": "sources/claude.json",
            }
        else:
            source_states["claude"] = disabled_state()

        repo_candidates = {path.expanduser().resolve() for path in args.repo if path.expanduser().is_dir()}
        repo_candidates |= discover_repo_candidates(codex_payload, claude_payload, hook_events)

        git_payload: dict[str, Any] = {"coverage": "disabled", "repositories": []}
        if git_enabled:
            git_output = source_dir / "git.json"
            git_command = [
                sys.executable,
                str(scripts / "collect_git.py"),
                "--start",
                iso_utc(start_utc),
                "--end",
                iso_utc(end_utc),
                "--output",
                str(git_output),
                "--events-root",
                str(root / ".journal" / "events"),
                "--diff-max-bytes",
                str(int(collection_config.get("max_diff_bytes_per_repo", 20 * 1024 * 1024))),
                "--privacy",
                "Low",
                *terms,
            ]
            for repo in sorted(repo_candidates, key=str):
                git_command.extend(["--repo", str(repo)])
            git_payload = invoke_adapter(git_command, git_output, root, privacy, custom_terms)
            source_states["git"] = {
                "enabled": True,
                "coverage": git_payload.get("coverage", "unavailable"),
                "repository_count": git_payload.get("repository_count", 0),
                "candidate_directory_count": git_payload.get("candidate_directory_count", 0),
                "artifact": "sources/git.json",
            }
        else:
            source_states["git"] = disabled_state()

        note_text = ""
        if manual_enabled:
            note_path = root / ".journal" / "notes" / f"{report_date}.md"
            note_text = note_path.read_text(encoding="utf-8") if note_path.is_file() else ""
            manual_payload = {
                "schema_version": 1,
                "adapter": "manual-notes",
                "collected_at": utc_now_iso(),
                "date": report_date.isoformat(),
                "note_path": str(note_path.relative_to(root)),
                "present": bool(note_text.strip()),
                "content": note_text,
                "coverage": "complete",
            }
            write_json(source_dir / "manual-notes.json", sanitize(manual_payload, privacy, custom_terms))
            source_states["manual-notes"] = {
                "enabled": True,
                "coverage": "complete",
                "present": bool(note_text.strip()),
                "artifact": "sources/manual-notes.json",
            }
        else:
            source_states["manual-notes"] = disabled_state()

        source_states["hooks"] = {
            "enabled": True,
            "coverage": hooks.get("coverage", "unavailable"),
            "event_count": hooks.get("event_count", 0),
            "artifact": "sources/hooks.json",
            "supplemental": True,
        }

        enabled_hook_events = [
            item
            for item in hook_events
            if (item.get("source") == "codex" and codex_enabled)
            or (item.get("source") == "claude" and claude_enabled)
        ]
        activity = bool(enabled_hook_events)
        if manual_enabled:
            activity = activity or bool(note_text.strip())
        if git_enabled:
            activity = activity or has_git_activity(git_payload)
        if codex_enabled and isinstance(codex_payload, dict):
            activity = activity or int(codex_payload.get("selected_thread_count", 0) or 0) > 0
        if claude_enabled and isinstance(claude_payload, dict):
            activity = activity or int(claude_payload.get("selected_session_count", 0) or 0) > 0

        status_hint, coverage = determine_status(
            {key: value for key, value in source_states.items() if key != "hooks"},
            activity,
        )
        collection = {
            "schema_version": 1,
            "collector_version": "installed-runtime",
            "report_date": report_date.isoformat(),
            "timezone": timezone_name,
            "window": {
                "local_start": start_local.isoformat(),
                "local_end": end_local.isoformat(),
                "utc_start": iso_utc(start_utc),
                "utc_end": iso_utc(end_utc),
            },
            "privacy": privacy,
            "collection_mode": "historical-backfill" if claude_scan_all else "daily-window",
            "claude_scan_all": claude_scan_all,
            "status_hint": status_hint,
            "coverage": coverage,
            "activity_signal": activity,
            "repository_candidate_count": len(repo_candidates),
            "sources": source_states,
            "config_sha256": sha256_bytes(config_path.read_bytes()),
            "collected_at": utc_now_iso(),
            "notes": [
                "status_hint is deterministic triage, not the final report conclusion",
                "provider-native files remain the evidence source of truth",
                "disabled sources do not affect activity or completeness",
            ],
        }
        write_json(temp_dir / "collection.json", collection)

        target_sources = day_dir / "sources"
        if target_sources.exists():
            shutil.rmtree(target_sources)
        os.replace(source_dir, target_sources)
        shutil.copy2(temp_dir / "collection.json", day_dir / "collection.json")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if args.as_json:
        print(json.dumps(collection, ensure_ascii=False, indent=2))
    else:
        print(
            f"Collected {report_date} -> {day_dir.relative_to(root)} "
            f"status_hint={collection['status_hint']} coverage={collection['coverage']}"
        )
        for name, state in source_states.items():
            print(f"- {name}: {state.get('coverage')}")
    if collection["coverage"] == "complete":
        return 0
    return 2 if collection["coverage"] == "partial" else 1


if __name__ == "__main__":
    raise SystemExit(main())
