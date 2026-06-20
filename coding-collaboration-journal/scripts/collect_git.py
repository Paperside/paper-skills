#!/usr/bin/env python3
"""Collect repository state for working directories discovered from coding sessions."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from common import run_command, sanitize, sha256_text, utc_now_iso, write_json


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def walk_cwds(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in {"cwd", "working_directory", "workspace", "workspace_path", "project_path"} and isinstance(child, str):
                yield child
            else:
                yield from walk_cwds(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_cwds(child)


def discover_cwds(events_root: Path | None, start: datetime, end: datetime) -> set[Path]:
    roots: set[Path] = set()
    if not events_root or not events_root.exists():
        return roots
    for path in events_root.rglob("*.jsonl"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                captured = item.get("captured_at") if isinstance(item, dict) else None
                try:
                    when = parse_instant(captured) if isinstance(captured, str) else None
                except ValueError:
                    when = None
                if when is None or not (start <= when < end):
                    continue
                for cwd in walk_cwds(item):
                    candidate = Path(cwd).expanduser()
                    if candidate.is_dir():
                        roots.add(candidate.resolve())
        except OSError:
            continue
    return roots


def git(root: Path, *args: str, timeout: int = 60) -> dict[str, Any]:
    return run_command(["git", *args], cwd=root, timeout=timeout)


def resolve_repo(path: Path) -> Path | None:
    result = git(path, "rev-parse", "--show-toplevel")
    if not result["ok"]:
        return None
    text = result["stdout"].strip()
    return Path(text).resolve() if text else None


def capped(text: str, max_bytes: int) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text, False
    clipped = data[:max_bytes].decode("utf-8", errors="replace")
    return clipped, True


def failure(stage: str, result: dict[str, Any], *, expected: bool = False) -> dict[str, Any] | None:
    if result.get("ok") or expected:
        return None
    return {
        "stage": stage,
        "returncode": result.get("returncode"),
        "message": str(result.get("stderr", "")).strip() or "Git command failed",
    }


def collect_repo(root: Path, start: datetime, end: datetime, diff_max_bytes: int) -> dict[str, Any]:
    collected_at = utc_now_iso()
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    has_head = bool(head["ok"] and head["stdout"].strip())
    status = git(root, "status", "--porcelain=v2", "--branch", "--untracked-files=all")
    remotes = git(root, "remote", "-v")
    log = git(
        root,
        "log",
        "--all",
        f"--since={start.isoformat()}",
        f"--until={end.isoformat()}",
        "--date=iso-strict",
        "--format=%H%x1f%aI%x1f%cI%x1f%an%x1f%ae%x1f%s%x1e",
        timeout=120,
    )
    unstaged = git(root, "diff", "--no-ext-diff", "--binary", timeout=120)
    staged = git(root, "diff", "--cached", "--no-ext-diff", "--binary", timeout=120)
    diff_stat = git(root, "diff", "--stat", "HEAD", timeout=60) if has_head else {
        "ok": True,
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "not_applicable": "repository has no HEAD yet",
    }
    reflog = git(
        root,
        "reflog",
        "--date=iso-strict",
        f"--since={start.isoformat()}",
        f"--until={end.isoformat()}",
        "--format=%H%x1f%gD%x1f%gs%x1f%cd",
        timeout=60,
    ) if has_head else {
        "ok": True,
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "not_applicable": "repository has no HEAD yet",
    }

    unstaged_text, unstaged_truncated = capped(unstaged["stdout"], diff_max_bytes)
    staged_text, staged_truncated = capped(staged["stdout"], diff_max_bytes)

    commit_rows: list[dict[str, str]] = []
    if log["ok"]:
        for record in log["stdout"].split("\x1e"):
            record = record.strip("\n")
            if not record:
                continue
            fields = record.split("\x1f")
            if len(fields) >= 6:
                commit_rows.append(
                    {
                        "sha": fields[0],
                        "author_time": fields[1],
                        "committer_time": fields[2],
                        "author_name": fields[3],
                        "author_email": fields[4],
                        "subject": "\x1f".join(fields[5:]),
                    }
                )

    remote_lines = sorted(set(line.strip() for line in remotes["stdout"].splitlines() if line.strip()))
    remote_identity = "|".join(remote_lines) or str(root)

    failures = [
        item
        for item in (
            failure("branch", branch),
            failure("status", status),
            failure("remotes", remotes),
            failure("log", log, expected=not has_head),
            failure("unstaged-diff", unstaged),
            failure("staged-diff", staged),
            failure("diff-stat", diff_stat),
            failure("reflog", reflog),
        )
        if item is not None
    ]
    truncated = unstaged_truncated or staged_truncated
    coverage = "partial" if failures or truncated else "complete"

    snapshot_note = {
        "captured_at": collected_at,
        "temporal_scope": "collection-time-working-tree-snapshot",
        "report_window": {"start": start.isoformat(), "end": end.isoformat()},
        "note": "Uncommitted status and diffs are snapshots taken when collection ran; Git cannot date individual uncommitted edits reliably.",
    }
    return {
        "repo_id": f"repo-{sha256_text(remote_identity)[:12]}",
        "root": str(root),
        "branch": branch["stdout"].strip() if branch["ok"] else None,
        "head": head["stdout"].strip() if has_head else None,
        "has_head": has_head,
        "remotes": remote_lines,
        "status": status,
        "commits": commit_rows,
        "reflog": reflog,
        "diff_stat": diff_stat,
        "working_tree_snapshot": snapshot_note,
        "unstaged_diff": {**unstaged, "stdout": unstaged_text, "truncated": unstaged_truncated, **snapshot_note},
        "staged_diff": {**staged, "stdout": staged_text, "truncated": staged_truncated, **snapshot_note},
        "command_failures": failures,
        "coverage": coverage,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events-root", type=Path)
    parser.add_argument("--repo", type=Path, action="append", default=[])
    parser.add_argument("--diff-max-bytes", type=int, default=20 * 1024 * 1024)
    parser.add_argument("--privacy", choices=("Low", "Medium", "High"), default="Low")
    parser.add_argument("--custom-sensitive-term", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = parse_instant(args.start)
    end = parse_instant(args.end)
    candidates = {path.expanduser().resolve() for path in args.repo if path.expanduser().is_dir()}
    candidates |= discover_cwds(args.events_root.expanduser() if args.events_root else None, start, end)

    repos: set[Path] = set()
    non_repos: list[str] = []
    for candidate in sorted(candidates, key=str):
        repo = resolve_repo(candidate)
        if repo:
            repos.add(repo)
        else:
            non_repos.append(str(candidate))

    collected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for repo in sorted(repos, key=str):
        try:
            collected.append(collect_repo(repo, start, end, args.diff_max_bytes))
        except Exception as exc:
            errors.append({"root": str(repo), "type": type(exc).__name__, "message": str(exc)})

    repo_partial = any(item.get("coverage") != "complete" for item in collected)
    if errors and not collected:
        coverage = "unavailable"
    elif errors or repo_partial:
        coverage = "partial"
    else:
        coverage = "complete"

    payload = {
        "schema_version": 1,
        "adapter": "git-local",
        "collected_at": utc_now_iso(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "candidate_directory_count": len(candidates),
        "repository_count": len(collected),
        "non_repository_directories": non_repos,
        "repositories": collected,
        "errors": errors,
        "coverage": coverage,
    }
    write_json(args.output, sanitize(payload, args.privacy, args.custom_sensitive_term))
    return 0 if coverage == "complete" else (2 if coverage == "partial" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
