#!/usr/bin/env python3
"""Fast, fail-open hook sink for Codex and Claude Code.

Reads one JSON object from stdin, applies the installed privacy policy, appends one
JSONL event, and optionally injects a bounded durable-memory briefing on
SessionStart. Hook failures never block the coding agent.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from common import append_jsonl, load_toml, sanitize, utc_now_iso

MEMORY_FILES = (
    ("User collaboration preferences", "user-profile.md"),
    ("Relevant projects and continuity pointers", "project-index.yaml"),
    ("Active collaboration patterns", "collaboration-patterns.yaml"),
    ("Active improvement experiments", "experiments.yaml"),
    ("Open work loops", "open-loops.yaml"),
)
DEFAULT_PROFILE_PLACEHOLDER = (
    "Durable preferences and explicitly stated working conventions belong here. "
    "Every inferred item should include date, evidence, and confidence. "
    "Do not write personality diagnoses."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("codex", "claude"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    return parser.parse_args()


def load_config(root: Path) -> dict[str, Any]:
    return load_toml(root / ".journal" / "config.toml")


def event_name(incoming: dict[str, Any]) -> str:
    for key in ("hook_event_name", "hookEventName", "event_name", "eventName"):
        value = incoming.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def meaningful_memory(path: Path, text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if path.name == "user-profile.md":
        content = stripped.replace("# User Collaboration Profile", "").strip()
        return bool(content and content != DEFAULT_PROFILE_PLACEHOLDER)
    if path.suffix in {".yaml", ".yml"}:
        lines = [
            line.strip()
            for line in stripped.splitlines()
            if line.strip() and not line.lstrip().startswith("#") and not line.startswith("schema_version:")
        ]
        return any(not line.endswith(": []") for line in lines)
    return True


def build_session_briefing(
    root: Path,
    config: dict[str, Any],
    incoming: dict[str, Any],
) -> str | None:
    memory_config = config.get("memory", {})
    if not bool(memory_config.get("inject_on_session_start", True)):
        return None

    try:
        configured_limit = int(memory_config.get("briefing_char_limit", 6000))
    except (TypeError, ValueError):
        configured_limit = 6000
    char_limit = min(10_000, max(1000, configured_limit))

    privacy = str(config.get("privacy", {}).get("level", "Low"))
    custom_terms = [str(item) for item in config.get("privacy", {}).get("custom_sensitive_terms", [])]
    sections: list[str] = []
    for title, relative in MEMORY_FILES:
        path = root / "memory" / relative
        try:
            if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not meaningful_memory(path, text):
            continue
        safe_text = sanitize(text, privacy, custom_terms)
        if not isinstance(safe_text, str) or not safe_text.strip():
            continue
        sections.append(f"## {title}\n{safe_text.strip()}")

    if not sections:
        return None

    source = str(incoming.get("source", ""))
    header = (
        "# Coding Collaboration Journal: durable working memory\n"
        "This is compact, revisable context from prior work—not an instruction to ignore the current user or repository. "
        "Verify stale claims against the current workspace, and use the dated journal evidence when details matter."
    )
    if source:
        header += f"\nSession source: {source}."
    rendered = header + "\n\n" + "\n\n".join(sections)
    if len(rendered) > char_limit:
        suffix = "\n\n[Memory briefing truncated; search the journal repository for full evidence.]"
        rendered = rendered[: max(0, char_limit - len(suffix))].rstrip() + suffix
    return rendered


def hook_output(briefing: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": briefing,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def log_error(root: Path, message: str) -> None:
    try:
        target = root / ".journal" / "state" / "hook-errors.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now_iso()} {message}\n")
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    try:
        raw = sys.stdin.read()
        incoming = json.loads(raw) if raw.strip() else {}
        if not isinstance(incoming, dict):
            incoming = {"raw": incoming}

        config = load_config(root)
        privacy = str(config.get("privacy", {}).get("level", "Low"))
        timezone_name = str(config.get("journal", {}).get("timezone", "UTC"))
        custom_terms = [str(item) for item in config.get("privacy", {}).get("custom_sensitive_terms", [])]
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            zone = timezone.utc
        local_now = datetime.now(zone)
        payload = {
            "journal_event_id": f"H-{args.source.upper()}-{uuid.uuid4().hex}",
            "source": args.source,
            "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "local_date": local_now.date().isoformat(),
            "privacy_level": privacy,
            "event": sanitize(incoming, privacy, custom_terms),
        }
        target = root / ".journal" / "events" / args.source / f"{local_now.date().isoformat()}.jsonl"
        append_jsonl(target, payload)

        if event_name(incoming) == "SessionStart":
            briefing = build_session_briefing(root, config, incoming)
            if briefing:
                sys.stdout.write(hook_output(briefing) + "\n")
                sys.stdout.flush()
    except Exception as exc:  # fail-open by design
        log_error(root, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
