#!/usr/bin/env python3
"""Shared helpers for the Coding Collaboration Journal skill.

Only Python's standard library is used so generated journals remain portable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python < 3.11
    raise SystemExit("Python 3.11 or newer is required (missing tomllib).") from exc

SECRET_KEY_RE = re.compile(
    r"(?:^|[_.-])(?:password|passwd|passphrase|pin|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"auth(?:orization)?|cookie|private[_-]?key|client[_-]?secret|secret(?:[_-]?key)?|session[_-]?token|token|"
    r"one[_-]?time[_-]?(?:code|password)|otp|recovery[_-]?code|seed[_-]?phrase|"
    r"aws[_-]?secret[_-]?access[_-]?key|database[_-]?url|connection[_-]?string|signing[_-]?key)$",
    re.IGNORECASE,
)
PEM_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]{12,}=*")
BASIC_AUTH_RE = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/]{8,}={0,2}")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
COMMON_TOKEN_RE = re.compile(
    r"(?x)(?:"
    r"sk-[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"glpat-[A-Za-z0-9_-]{20,}|"
    r"npm_[A-Za-z0-9]{20,}|"
    r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{20,}|"
    r"hf_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z_-]{25,}"
    r")"
)
URL_CREDENTIAL_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@")
SECRET_NAME_FRAGMENT = (
    r"(?:password|passwd|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"authorization|client[_-]?secret|secret(?:[_-]?key)?|session[_-]?token|token|private[_-]?key|"
    r"one[_-]?time[_-]?(?:code|password)|otp|recovery[_-]?code|seed[_-]?phrase|"
    r"aws[_-]?secret[_-]?access[_-]?key|database[_-]?url|connection[_-]?string)"
)
QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?im)(?P<prefix>[\"']?[A-Za-z0-9_.-]*{SECRET_NAME_FRAGMENT}[\"']?\s*[:=]\s*)"
    rf"(?P<quote>[\"'])(?P<value>[^\r\n]*?)(?P=quote)"
)
UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?im)(?P<prefix>\b[A-Za-z0-9_.-]*{SECRET_NAME_FRAGMENT}\s*=\s*)"
    rf"(?P<value>[^\s#;]+)"
)
SENSITIVE_HEADER_RE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key)\s*:\s*)"
    r"(?P<value>[^\r\n]+)"
)

MEDIUM_KEY_RE = re.compile(
    r"(?:customer|client|tenant|account|employee|email|phone|hostname|host|ip|endpoint|"
    r"internal[_-]?url|contract|price|revenue|metric|codename)",
    re.IGNORECASE,
)
HIGH_CONTENT_KEYS = {
    # Provider-native container fields. At High privacy, persist only counts/hashes
    # for raw conversation, tool, event, and repository structures.
    "threads",
    "sessions",
    "records",
    "events",
    "repositories",
    "turns",
    "items",
    "messages",
    "message",
    "input",
    "output",
    "arguments",
    "args",
    "results",
    "prompt",
    "content",
    "text",
    "tool_input",
    "tool_response",
    "stdout",
    "stderr",
    "command",
    "diff",
    "patch",
    "file_path",
    "path",
    "cwd",
    "transcript_path",
    "agent_transcript_path",
    "repo",
    "repository",
    "repo_name",
    "repository_name",
    "project",
    "project_name",
    "service",
    "service_name",
    "file",
    "file_name",
    "filename",
    "remote",
    "remote_url",
    "url",
    "uri",
    "branch",
    "commit",
    "commit_sha",
    "sha",
    "issue",
    "issue_id",
    "pull_request",
    "pull_request_id",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def atomic_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = isinstance(content, bytes)
    mode = "wb" if binary else "w"
    kwargs = {} if binary else {"encoding": "utf-8", "newline": "\n"}
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, mode, **kwargs) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def _redact_string(value: str) -> str:
    value = PEM_RE.sub("[REDACTED_PRIVATE_KEY]", value)
    value = BEARER_RE.sub("Bearer [REDACTED]", value)
    value = BASIC_AUTH_RE.sub("Basic [REDACTED]", value)
    value = JWT_RE.sub("[REDACTED_JWT]", value)
    value = COMMON_TOKEN_RE.sub("[REDACTED_TOKEN]", value)
    value = URL_CREDENTIAL_RE.sub(r"\1[REDACTED]@", value)
    value = QUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}{match.group('quote')}[REDACTED_SECRET]{match.group('quote')}",
        value,
    )
    value = UNQUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED_SECRET]",
        value,
    )
    value = SENSITIVE_HEADER_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED_SECRET]",
        value,
    )
    return value


def is_secret_key(key: str) -> bool:
    """Recognize secret-bearing mapping keys, including common camelCase forms."""
    # Provider payloads commonly use apiKey/clientSecret/privateKey. Normalize
    # word boundaries before applying the anchored key rule so these cannot slip
    # through Low privacy simply because they are not snake_case.
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).replace(" ", "_")
    return bool(SECRET_KEY_RE.search(normalized))


def secret_hits(text: str) -> list[str]:
    """Return credential-pattern categories still present in persisted text.

    Redacted assignments still retain their field names so the journal remains
    understandable. Treat those placeholders as safe rather than flagging the
    assignment syntax itself.
    """
    hits: list[str] = []
    direct_checks = (
        ("private-key", PEM_RE),
        ("bearer-token", BEARER_RE),
        ("basic-auth", BASIC_AUTH_RE),
        ("jwt", JWT_RE),
        ("known-token-pattern", COMMON_TOKEN_RE),
        ("url-credentials", URL_CREDENTIAL_RE),
    )
    for name, pattern in direct_checks:
        if pattern.search(text):
            hits.append(name)

    value_checks = (
        ("quoted-secret-assignment", QUOTED_SECRET_ASSIGNMENT_RE),
        ("unquoted-secret-assignment", UNQUOTED_SECRET_ASSIGNMENT_RE),
        ("sensitive-header", SENSITIVE_HEADER_RE),
    )
    for name, pattern in value_checks:
        for match in pattern.finditer(text):
            value = match.groupdict().get("value", "").strip()
            if not value.startswith("[REDACTED"):
                hits.append(name)
                break
    return hits


def sanitize(value: Any, level: str = "Low", custom_terms: Iterable[str] = ()) -> Any:
    """Redact credentials always and apply a conservative privacy-level transform.

    Medium is intentionally conservative: explicit sensitive keys and configured terms
    are replaced while the surrounding technical structure remains. High retains only
    metadata for content-heavy fields.
    """
    normalized = level.capitalize()
    if normalized not in {"Low", "Medium", "High"}:
        raise ValueError(f"Unsupported privacy level: {level}")

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if is_secret_key(key):
                result[key] = "[REDACTED_SECRET]"
                continue
            if normalized == "High" and key.lower() in HIGH_CONTENT_KEYS:
                serialized = json.dumps(raw_value, ensure_ascii=False, sort_keys=True, default=str)
                result[key] = {
                    "abstracted": True,
                    "sha256": sha256_text(serialized),
                    "characters": len(serialized),
                }
                continue
            if normalized == "Medium" and MEDIUM_KEY_RE.search(key):
                serialized = json.dumps(raw_value, ensure_ascii=False, sort_keys=True, default=str)
                result[key] = {
                    "aliased": True,
                    "id": f"sensitive-{sha256_text(serialized)[:12]}",
                }
                continue
            result[key] = sanitize(raw_value, normalized, custom_terms)
        return result

    if isinstance(value, list):
        return [sanitize(item, normalized, custom_terms) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item, normalized, custom_terms) for item in value]
    if isinstance(value, str):
        redacted = _redact_string(value)
        if normalized in {"Medium", "High"}:
            for term in custom_terms:
                if term:
                    redacted = re.sub(re.escape(term), "[REDACTED_CUSTOM]", redacted, flags=re.IGNORECASE)
        return redacted
    return value


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
    check: bool = False,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": f"not found: {args[0]}"}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s: {exc.stderr or ''}",
        }
    result = {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed: {args!r}\n{proc.stderr}")
    return result


def find_journal_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".journal" / "config.toml").is_file():
            return candidate
    raise FileNotFoundError("Could not find .journal/config.toml in this directory or its parents")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, payload: Any) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
