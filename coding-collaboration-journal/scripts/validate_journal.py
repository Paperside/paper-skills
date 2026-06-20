#!/usr/bin/env python3
"""Validate an installed journal's structure, evidence links, and secret boundary."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import find_journal_root, load_toml, secret_hits

EVIDENCE_ID_RE = re.compile(r"\bE-[A-Z0-9][A-Z0-9-]{2,}\b")
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRONTMATTER_STATUS_RE = re.compile(r"(?m)^status:\s*([A-Za-z-]+)\s*$")
FRONTMATTER_DATE_RE = re.compile(r"(?m)^date:\s*(\d{4}-\d{2}-\d{2})\s*$")
ALLOWED_STATUS = {"active", "no-activity", "partial-activity", "incomplete-collection"}
MAX_SECRET_SCAN_BYTES = 128 * 1024 * 1024
SECRET_SCAN_SUFFIXES = {
    "", ".json", ".jsonl", ".md", ".yaml", ".yml", ".toml", ".txt", ".log",
    ".py", ".sh", ".ps1", ".service", ".timer", ".plist",
}
SECRET_SCAN_SKIP_PARTS = {".git", "__pycache__", "scripts"}
REQUIRED_REPORT_SECTIONS = (
    ("collaboration-analysis", ("协作分析", "Collaboration analysis")),
    ("overall-evaluation", ("综合评价", "Overall evaluation")),
    ("data-quality", ("数据质量", "Data quality")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_positional", type=Path, nargs="?")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def add(items: list[dict[str, Any]], level: str, code: str, message: str, path: Path | None = None) -> None:
    entry = {"level": level, "code": code, "message": message}
    if path:
        entry["path"] = str(path)
    items.append(entry)


def read_json_object(path: Path, items: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(items, "error", code, str(exc), path)
        return None
    except OSError as exc:
        add(items, "error", code, str(exc), path)
        return None
    if not isinstance(value, dict):
        add(items, "error", code, "Expected a JSON object", path)
        return None
    return value


def has_heading(report: str, aliases: tuple[str, ...]) -> bool:
    headings = {
        match.group(1).strip().casefold()
        for match in re.finditer(r"(?m)^##\s+(.+?)\s*$", report)
    }
    return any(alias.casefold() in headings for alias in aliases)


def source_is_complete(state: Any) -> bool:
    if isinstance(state, dict):
        if state.get("enabled") is False or state.get("coverage") == "disabled":
            return True
        return state.get("coverage") == "complete"
    return state in {"complete", "disabled"}


def validate_evidence_shape(evidence: dict[str, Any], evidence_path: Path, items: list[dict[str, Any]]) -> set[str]:
    evidence_items = evidence.get("evidence", [])
    if not isinstance(evidence_items, list):
        add(items, "error", "invalid-evidence-items", "evidence must be an array", evidence_path)
        return set()

    ids: set[str] = set()
    duplicates: set[str] = set()
    for index, entry in enumerate(evidence_items):
        if not isinstance(entry, dict):
            add(items, "error", "invalid-evidence-item", f"evidence[{index}] must be an object", evidence_path)
            continue
        evidence_id = entry.get("evidence_id")
        if not isinstance(evidence_id, str) or not EVIDENCE_ID_RE.fullmatch(evidence_id):
            add(items, "error", "invalid-evidence-id", f"evidence[{index}] has invalid evidence_id", evidence_path)
            continue
        if evidence_id in ids:
            duplicates.add(evidence_id)
        ids.add(evidence_id)
    if duplicates:
        add(items, "error", "duplicate-evidence-id", f"Duplicate evidence IDs: {', '.join(sorted(duplicates))}", evidence_path)
    return ids


def validate_day(day_dir: Path, items: list[dict[str, Any]]) -> None:
    report_path = day_dir / "report.md"
    evidence_path = day_dir / "evidence.json"
    run_path = day_dir / "run.json"
    collection_path = day_dir / "collection.json"
    for path in (report_path, evidence_path, run_path):
        if not path.is_file():
            add(items, "error", "missing-artifact", f"Missing required daily artifact {path.name}", path)
    if not report_path.is_file() or not evidence_path.is_file():
        return

    report = report_path.read_text(encoding="utf-8", errors="replace")
    evidence = read_json_object(evidence_path, items, "invalid-evidence-json")
    if evidence is None:
        return
    run = read_json_object(run_path, items, "invalid-run-json") if run_path.is_file() else None
    collection = read_json_object(collection_path, items, "invalid-collection-json") if collection_path.is_file() else None

    ids = validate_evidence_shape(evidence, evidence_path, items)
    cited = set(EVIDENCE_ID_RE.findall(report))
    dangling = sorted(cited - ids)
    if dangling:
        add(items, "error", "dangling-evidence", f"Report cites missing IDs: {', '.join(dangling)}", report_path)

    report_status_match = FRONTMATTER_STATUS_RE.search(report)
    report_status = report_status_match.group(1) if report_status_match else None
    evidence_status = evidence.get("status")
    if report_status not in ALLOWED_STATUS:
        add(items, "error", "invalid-report-status", f"Invalid or missing report status: {report_status}", report_path)
    if evidence_status not in ALLOWED_STATUS:
        add(items, "error", "invalid-evidence-status", f"Invalid or missing evidence status: {evidence_status}", evidence_path)
    if report_status and evidence_status and report_status != evidence_status:
        add(items, "error", "status-mismatch", f"report={report_status}, evidence={evidence_status}", day_dir)

    report_date_match = FRONTMATTER_DATE_RE.search(report)
    report_date = report_date_match.group(1) if report_date_match else None
    expected_date = day_dir.name
    if report_date != expected_date:
        add(items, "error", "report-date-mismatch", f"report={report_date}, directory={expected_date}", report_path)
    evidence_date = evidence.get("report_date")
    if evidence_date != expected_date:
        add(items, "error", "evidence-date-mismatch", f"evidence={evidence_date}, directory={expected_date}", evidence_path)
    if run is not None and run.get("report_date") != expected_date:
        add(items, "error", "run-date-mismatch", f"run={run.get('report_date')}, directory={expected_date}", run_path)
    if collection is not None and collection.get("report_date") != expected_date:
        add(items, "error", "collection-date-mismatch", f"collection={collection.get('report_date')}, directory={expected_date}", collection_path)

    for code, aliases in REQUIRED_REPORT_SECTIONS:
        if not has_heading(report, aliases):
            add(items, "error", "missing-report-section", f"Missing required section: {code}", report_path)

    if evidence_status == "no-activity":
        sources = evidence.get("sources", {})
        incomplete = []
        if isinstance(sources, dict):
            for name, state in sources.items():
                if not source_is_complete(state):
                    incomplete.append(str(name))
        else:
            incomplete.append("sources")
        if collection is not None and collection.get("coverage") != "complete":
            incomplete.append("collection")
        if incomplete:
            add(items, "error", "false-no-activity", f"no-activity with incomplete sources: {', '.join(incomplete)}", evidence_path)

    if collection is not None:
        collection_hint = collection.get("status_hint")
        if evidence_status == "no-activity" and collection_hint not in {"no-activity", None}:
            add(
                items,
                "error",
                "collection-status-conflict",
                f"evidence=no-activity but collector status_hint={collection_hint}",
                collection_path,
            )


def scan_secret_boundary(root: Path, items: list[dict[str, Any]]) -> None:
    """Scan all durable text artifacts, not only the rendered report.

    Provider-native source files and hook events are exactly where credentials can
    accidentally survive, so a report-only scan would provide false confidence.
    Installed runtime source under scripts/ is excluded: it is versioned tool code,
    not accumulated user knowledge, and may legitimately contain detection patterns.
    """
    for path in root.rglob("*"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in SECRET_SCAN_SKIP_PARTS for part in relative.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if ".journal" in relative.parts and "state" in relative.parts and "tmp" in relative.parts:
            continue
        if path.suffix.lower() not in SECRET_SCAN_SUFFIXES:
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            add(items, "error", "secret-scan-unavailable", str(exc), path)
            continue
        if size > MAX_SECRET_SCAN_BYTES:
            add(
                items,
                "error",
                "secret-scan-too-large",
                f"Text artifact exceeds secret-scan limit ({size} bytes)",
                path,
            )
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            add(items, "error", "secret-scan-unavailable", str(exc), path)
            continue
        if b"\x00" in raw[:8192]:
            continue
        text = raw.decode("utf-8", errors="replace")
        hits = secret_hits(text)
        if hits:
            add(items, "error", "secret-pattern", f"Potential secret material: {', '.join(hits)}", path)


def validate(root: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    required = [
        ".journal/config.toml",
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "automation/daily.md",
        "automation/weekly.md",
        "automation/monthly.md",
        "memory/user-profile.md",
        "memory/project-index.yaml",
        "memory/collaboration-patterns.yaml",
        "memory/experiments.yaml",
        "scripts/doctor.py",
        "scripts/capture_event.py",
        "scripts/collect_day.py",
    ]
    for relative in required:
        path = root / relative
        if not path.exists():
            add(items, "error", "missing-required", f"Missing {relative}", path)

    config_path = root / ".journal" / "config.toml"
    if config_path.is_file():
        try:
            config = load_toml(config_path)
            privacy = config.get("privacy", {}).get("level")
            if privacy not in {"Low", "Medium", "High"}:
                add(items, "error", "invalid-privacy", f"Unsupported privacy level: {privacy}", config_path)
        except Exception as exc:
            add(items, "error", "invalid-config", str(exc), config_path)

    journal_root = root / "journal"
    if journal_root.exists():
        for day_dir in journal_root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*"):
            if day_dir.is_dir() and DATE_DIR_RE.match(day_dir.name):
                validate_day(day_dir, items)

    scan_secret_boundary(root, items)

    errors = sum(1 for item in items if item["level"] == "error")
    warnings = sum(1 for item in items if item["level"] == "warning")
    return {
        "root": str(root),
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": items,
    }


def main() -> int:
    args = parse_args()
    selected = args.root or args.root_positional
    root = selected.expanduser().resolve() if selected else find_journal_root()
    result = validate(root)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Journal validation: {'PASS' if result['valid'] else 'FAIL'}")
        for item in result["findings"]:
            suffix = f" ({item.get('path')})" if item.get("path") else ""
            print(f"[{item['level'].upper()}] {item['code']}: {item['message']}{suffix}")
        print(f"errors={result['errors']} warnings={result['warnings']}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
