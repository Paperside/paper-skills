#!/usr/bin/env python3
"""Collect Claude Code session JSONL files relevant to a reporting window."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from common import sanitize, sha256_bytes, utc_now_iso, write_json

TIMESTAMP_KEYS = ("timestamp", "created_at", "createdAt", "time", "ts")
TRANSCRIPT_KEYS = {"transcript_path", "agent_transcript_path"}


def parse_instant(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, timezone.utc)
        except (OSError, OverflowError, ValueError):
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


def iter_event_files(events_root: Path) -> Iterable[Path]:
    if not events_root.exists():
        return []
    return events_root.rglob("*.jsonl")


def walk_transcript_paths(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in TRANSCRIPT_KEYS and isinstance(child, str) and child:
                yield child
            else:
                yield from walk_transcript_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_transcript_paths(child)


def event_transcript_paths(events_root: Path, start: datetime, end: datetime) -> set[Path]:
    paths: set[Path] = set()
    for event_file in iter_event_files(events_root):
        try:
            for line in event_file.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                when = parse_instant(item.get("captured_at")) if isinstance(item, dict) else None
                if when is None or not (start <= when < end):
                    continue
                for raw_path in walk_transcript_paths(item):
                    paths.add(Path(raw_path).expanduser())
        except OSError:
            continue
    return paths


def record_timestamp(record: Any) -> datetime | None:
    if not isinstance(record, dict):
        return None
    for key in TIMESTAMP_KEYS:
        parsed = parse_instant(record.get(key))
        if parsed is not None:
            return parsed
    # Some transcript records keep timestamps one level down in metadata/message.
    for nested_key in ("metadata", "message", "event"):
        nested = record.get(nested_key)
        if isinstance(nested, dict):
            for key in TIMESTAMP_KEYS:
                parsed = parse_instant(nested.get(key))
                if parsed is not None:
                    return parsed
    return None


def selected_lines(data: bytes, max_bytes: int) -> tuple[list[bytes], bool, int]:
    if len(data) <= max_bytes:
        return data.splitlines(), False, 0
    half = max(1024, max_bytes // 2)
    head = data[:half]
    tail = data[-half:]
    # Remove potentially partial boundary lines.
    head_lines = head.splitlines()
    tail_lines = tail.splitlines()
    if head and not head.endswith((b"\n", b"\r")) and head_lines:
        head_lines = head_lines[:-1]
    if tail and data[-half - 1 : -half] not in {b"\n", b"\r"} and tail_lines:
        tail_lines = tail_lines[1:]
    omitted = max(0, len(data) - len(head) - len(tail))
    return [*head_lines, b'{"_truncated_gap":true}', *tail_lines], True, omitted


def decode_record(raw_line: bytes) -> tuple[Any, bool]:
    try:
        return json.loads(raw_line), False
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"_raw": raw_line.decode("utf-8", errors="replace")}, True


def parse_jsonl(path: Path, max_bytes: int, start: datetime, end: datetime) -> dict[str, Any]:
    data = path.read_bytes()
    retained_lines, truncated, omitted_bytes = selected_lines(data, max_bytes)

    # Scan every complete JSONL line for timestamps even when only a bounded
    # head/tail sample is retained. Otherwise activity in a large session's omitted
    # middle could be incorrectly reported as no activity.
    parse_errors = 0
    timestamped_records = 0
    activity_records = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    for raw_line in data.splitlines():
        record, failed = decode_record(raw_line)
        parse_errors += int(failed)
        when = record_timestamp(record)
        if when is None:
            continue
        timestamped_records += 1
        stamp = when.isoformat()
        if first_timestamp is None or stamp < first_timestamp:
            first_timestamp = stamp
        if last_timestamp is None or stamp > last_timestamp:
            last_timestamp = stamp
        if start <= when < end:
            activity_records += 1

    records: list[Any] = []
    retained_parse_errors = 0
    for raw_line in retained_lines:
        record, failed = decode_record(raw_line)
        retained_parse_errors += int(failed)
        records.append(record)

    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "path": str(path),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "mtime": modified.isoformat(),
        "truncated": truncated,
        "omitted_bytes": omitted_bytes,
        "parse_errors": parse_errors,
        "retained_parse_errors": retained_parse_errors,
        "timestamped_records": timestamped_records,
        "activity_records": activity_records,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events-root", type=Path)
    default_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "projects"
    parser.add_argument("--claude-root", type=Path, default=default_root)
    parser.add_argument("--scan-lookback-hours", type=int, default=72)
    parser.add_argument("--scan-lookahead-hours", type=int, default=72)
    parser.add_argument("--scan-all", action="store_true", help="Scan the entire session store for historical backfill")
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--max-file-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--privacy", choices=("Low", "Medium", "High"), default="Low")
    parser.add_argument("--custom-sensitive-term", action="append", default=[])
    return parser.parse_args()


def path_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None


def main() -> int:
    args = parse_args()
    start = parse_instant(args.start)
    end = parse_instant(args.end)
    if start is None or end is None or end <= start:
        raise SystemExit("Invalid --start/--end reporting window")

    errors: list[dict[str, Any]] = []
    referenced: set[Path] = set()
    if args.events_root:
        referenced = event_transcript_paths(args.events_root.expanduser(), start, end)

    candidates: set[Path] = set(referenced)
    claude_root = args.claude_root.expanduser()
    scan_floor = start - timedelta(hours=max(0, args.scan_lookback_hours))
    scan_ceiling = end + timedelta(hours=max(0, args.scan_lookahead_hours))
    store_available = claude_root.exists()
    if store_available:
        try:
            for path in claude_root.rglob("*.jsonl"):
                modified = path_mtime(path)
                if modified is None:
                    continue
                if args.scan_all or scan_floor <= modified <= scan_ceiling:
                    candidates.add(path)
        except OSError as exc:
            errors.append({"stage": "scan", "path": str(claude_root), "message": str(exc)})
    else:
        errors.append({"stage": "probe", "path": str(claude_root), "message": "Claude project store not found"})

    def order_key(path: Path) -> tuple[int, float, str]:
        modified = path_mtime(path)
        # Hook references are authoritative. Then prioritize files whose mtime is
        # closest to the report window, which keeps historical scans deterministic.
        distance = 0.0
        if modified is not None:
            if modified < start:
                distance = (start - modified).total_seconds()
            elif modified > end:
                distance = (modified - end).total_seconds()
        else:
            distance = float("inf")
        return (0 if path in referenced else 1, distance, str(path))

    ordered = sorted(candidates, key=order_key)
    if len(ordered) > args.max_files:
        errors.append(
            {
                "stage": "limit",
                "message": f"Candidate file limit reached: {len(ordered)} > {args.max_files}",
            }
        )
        ordered = ordered[: args.max_files]

    sessions: list[dict[str, Any]] = []
    considered = 0
    for path in ordered:
        considered += 1
        if not path.is_file():
            errors.append({"stage": "read", "path": str(path), "message": "file not found"})
            continue
        try:
            session = parse_jsonl(path, args.max_file_bytes, start, end)
        except OSError as exc:
            errors.append({"stage": "read", "path": str(path), "message": str(exc)})
            continue

        modified = parse_instant(session.get("mtime"))
        via_hook = path in referenced
        activity_records = int(session.get("activity_records", 0))
        timestamped_records = int(session.get("timestamped_records", 0))
        mtime_in_window = modified is not None and start <= modified < end
        include = via_hook or activity_records > 0 or (timestamped_records == 0 and mtime_in_window)
        if not include:
            continue
        if via_hook:
            basis = "hook-reference"
        elif activity_records:
            basis = "record-timestamps"
        else:
            basis = "mtime-no-record-timestamps"
        session["activity_basis"] = basis
        sessions.append(session)
        if session.get("truncated"):
            errors.append({"stage": "truncate", "path": str(path), "message": "Session exceeded max-file-bytes"})
        if session.get("parse_errors"):
            errors.append(
                {
                    "stage": "parse",
                    "path": str(path),
                    "message": f"{session['parse_errors']} JSONL line(s) could not be parsed",
                }
            )

    if not store_available and not sessions:
        coverage = "unavailable"
    elif errors:
        coverage = "partial" if sessions or store_available else "unavailable"
    else:
        coverage = "complete"

    payload = {
        "schema_version": 1,
        "adapter": "claude-local-jsonl",
        "collected_at": utc_now_iso(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "claude_root": str(claude_root),
        "store_available": store_available,
        "scan_all": args.scan_all,
        "scan_window": {"start": scan_floor.isoformat(), "end": scan_ceiling.isoformat()},
        "hook_referenced_count": len(referenced),
        "candidate_count": len(candidates),
        "considered_count": considered,
        "selected_session_count": len(sessions),
        "sessions": sessions,
        "errors": errors,
        "coverage": coverage,
    }
    write_json(args.output, sanitize(payload, args.privacy, args.custom_sensitive_term))
    return 0 if coverage == "complete" else (2 if coverage == "partial" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
