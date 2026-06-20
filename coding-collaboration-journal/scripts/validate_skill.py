#!/usr/bin/env python3
"""Validate the coding-collaboration-journal skill package without third-party deps."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
FIELD_RE = re.compile(r"(?m)^([A-Za-z0-9_-]+):\s*(.+?)\s*$")
TEMPLATE_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")
ALLOWED_TEMPLATE_VARS = {
    "JOURNAL_NAME",
    "DAILY_TIME",
    "TIMEZONE",
    "SOURCES",
    "PRIVACY",
    "SCHEDULER",
    "AUTO_SYNC",
    "RADAR",
    "SCHEDULER_NOTE",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def finding(items: list[dict[str, str]], level: str, code: str, message: str, path: Path | None = None) -> None:
    item = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = str(path)
    items.append(item)


def validate(root: Path) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    required = [
        "SKILL.md",
        "README.md",
        "manifest.json",
        "agents/interface.yaml",
        "agents/openai.yaml",
        "skill-ir/skill.json",
        "scripts/bootstrap.py",
        "scripts/validate_skill.py",
        "scripts/validate_journal.py",
        "scripts/collect_day.py",
        "references/onboarding.md",
        "references/source-adapters.md",
        "references/scheduler.md",
        "assets/prompts/daily.md",
        "assets/prompts/weekly.md",
        "assets/prompts/monthly.md",
        "evals/trigger-cases.jsonl",
        "evals/output-contract.json",
        "reports/output_quality_scorecard.md",
    ]
    for relative in required:
        path = root / relative
        if not path.is_file():
            finding(items, "error", "missing-required", f"Missing {relative}", path)

    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        text = skill_path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            finding(items, "error", "frontmatter", "SKILL.md must start with YAML frontmatter", skill_path)
        else:
            fields = dict(FIELD_RE.findall(match.group("body")))
            if fields.get("name") != "coding-collaboration-journal":
                finding(items, "error", "skill-name", f"Unexpected skill name: {fields.get('name')}", skill_path)
            description = fields.get("description", "")
            if len(description) < 80:
                finding(items, "warning", "description-short", "Description may not expose enough trigger phrases", skill_path)
        for raw_link in LINK_RE.findall(text):
            if raw_link.startswith(("http://", "https://", "#")):
                continue
            target = raw_link.split("#", 1)[0]
            if target and not (root / target).exists():
                finding(items, "error", "broken-link", f"Broken local link: {raw_link}", skill_path)

    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("name") != "coding-collaboration-journal":
                finding(items, "error", "manifest-name", "manifest name does not match skill", manifest_path)
        except json.JSONDecodeError as exc:
            finding(items, "error", "manifest-json", str(exc), manifest_path)

    ir_path = root / "skill-ir" / "skill.json"
    if ir_path.is_file():
        try:
            ir = json.loads(ir_path.read_text(encoding="utf-8"))
            if ir.get("id") != "coding-collaboration-journal":
                finding(items, "error", "ir-id", "Skill IR id mismatch", ir_path)
        except json.JSONDecodeError as exc:
            finding(items, "error", "ir-json", str(exc), ir_path)

    for script in sorted((root / "scripts").glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except (SyntaxError, UnicodeDecodeError) as exc:
            finding(items, "error", "python-syntax", str(exc), script)

    eval_jsonl = root / "evals" / "trigger-cases.jsonl"
    if eval_jsonl.is_file():
        case_ids: set[str] = set()
        positive = negative = 0
        for number, line in enumerate(eval_jsonl.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                finding(items, "error", "eval-jsonl", f"line {number}: {exc}", eval_jsonl)
                continue
            case_id = item.get("id")
            if not isinstance(case_id, str) or not case_id:
                finding(items, "error", "eval-id", f"line {number}: missing id", eval_jsonl)
            elif case_id in case_ids:
                finding(items, "error", "eval-duplicate", f"Duplicate id: {case_id}", eval_jsonl)
            else:
                case_ids.add(case_id)
            expected = item.get("expected")
            positive += expected == "trigger"
            negative += expected == "no-trigger"
        if positive < 5 or negative < 3:
            finding(items, "warning", "eval-balance", f"Trigger cases are sparse: {positive} positive, {negative} negative", eval_jsonl)

    output_contract = root / "evals" / "output-contract.json"
    if output_contract.is_file():
        try:
            contract = json.loads(output_contract.read_text(encoding="utf-8"))
            assertions = contract.get("assertions", [])
            if not isinstance(assertions, list) or len(assertions) < 8:
                finding(items, "warning", "output-assertions", "Expected at least 8 output assertions", output_contract)
        except json.JSONDecodeError as exc:
            finding(items, "error", "output-contract-json", str(exc), output_contract)

    for template in sorted((root / "assets" / "scaffold").rglob("*.tpl")):
        unknown = sorted(set(TEMPLATE_VAR_RE.findall(template.read_text(encoding="utf-8"))) - ALLOWED_TEMPLATE_VARS)
        if unknown:
            finding(items, "error", "template-var", f"Unknown template vars: {', '.join(unknown)}", template)

    errors = sum(item["level"] == "error" for item in items)
    warnings = sum(item["level"] == "warning" for item in items)
    return {
        "root": str(root),
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": items,
    }


def main() -> int:
    args = parse_args()
    result = validate(args.root.expanduser().resolve())
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Skill validation: {'PASS' if result['valid'] else 'FAIL'}")
        for item in result["findings"]:
            suffix = f" ({item.get('path')})" if item.get("path") else ""
            print(f"[{item['level'].upper()}] {item['code']}: {item['message']}{suffix}")
        print(f"errors={result['errors']} warnings={result['warnings']}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
