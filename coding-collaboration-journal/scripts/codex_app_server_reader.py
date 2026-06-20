#!/usr/bin/env python3
"""Read Codex conversation history through the documented App Server protocol."""
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from common import sanitize, utc_now_iso, write_json

ALL_SOURCE_KINDS = [
    "cli",
    "vscode",
    "exec",
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
    "unknown",
]
TIMESTAMP_KEYS = {
    "timestamp",
    "createdat",
    "updatedat",
    "recencyat",
    "startedat",
    "completedat",
    "starttime",
    "endtime",
    "time",
    "ts",
}


def parse_instant(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def epoch_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return numeric
    if isinstance(value, str) and value:
        try:
            return parse_instant(value).timestamp()
        except ValueError:
            return None
    return None


def epoch_hint(thread: dict[str, Any]) -> float:
    values = [epoch_value(thread.get(key)) for key in ("recencyAt", "updatedAt", "createdAt")]
    return max((value for value in values if value is not None), default=0.0)


def epoch_in_window(value: Any, start_epoch: float, end_epoch: float) -> bool:
    parsed = epoch_value(value)
    return parsed is not None and start_epoch <= parsed < end_epoch


def walk_timestamps(value: Any, parent_key: str = "") -> Iterable[float]:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).replace("_", "").replace("-", "").lower()
            if key in TIMESTAMP_KEYS or key.endswith("timestamp") or key.endswith("time"):
                parsed = epoch_value(child)
                if parsed is not None:
                    yield parsed
            yield from walk_timestamps(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from walk_timestamps(child, parent_key)


def activity_basis(
    summary: dict[str, Any],
    turns: Any,
    start_epoch: float,
    end_epoch: float,
) -> tuple[bool, str, int]:
    timestamps = list(walk_timestamps(turns))
    if any(start_epoch <= stamp < end_epoch for stamp in timestamps):
        return True, "turn-or-item-timestamps", len(timestamps)
    for key in ("recencyAt", "updatedAt", "createdAt"):
        if epoch_in_window(summary.get(key), start_epoch, end_epoch):
            return True, f"summary-{key}", len(timestamps)
    return False, "outside-window-or-ambiguous", len(timestamps)


class RpcClient:
    def __init__(self, command: list[str], timeout: float) -> None:
        self.timeout = timeout
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        assert self.process.stdin and self.process.stdout and self.process.stderr
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr_lines: list[str] = []
        self._pending: dict[Any, dict[str, Any]] = {}
        self._write_lock = threading.Lock()
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name="codex-app-server-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="codex-app-server-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout
        for raw in self.process.stdout:
            raw = raw.strip()
            if not raw:
                continue
            try:
                self.messages.put(json.loads(raw))
            except json.JSONDecodeError:
                self.messages.put({"_unparsed_stdout": raw})

    def _read_stderr(self) -> None:
        assert self.process.stderr
        for raw in self.process.stderr:
            if len(self.stderr_lines) < 2000:
                self.stderr_lines.append(raw.rstrip())

    def send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._write_lock:
            self.process.stdin.write(line)
            self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None, request_id: int) -> dict[str, Any]:
        payload: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            payload["params"] = params
        self.send(payload)
        deadline = time.monotonic() + self.timeout
        if request_id in self._pending:
            return self._pending.pop(request_id)
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                break
            message_id = message.get("id")
            if message_id == request_id:
                return message
            if message_id is not None:
                self._pending[message_id] = message
        raise TimeoutError(f"Timed out waiting for App Server response to {method}")

    def close(self) -> None:
        # Close stdin first so stdio-based App Servers can exit normally.  Merely
        # terminating the child while daemon reader threads still own buffered
        # streams can intermittently hang Python during interpreter shutdown.
        stdin = self.process.stdin
        if stdin is not None and not stdin.closed:
            try:
                stdin.close()
            except OSError:
                pass

        if self.process.poll() is None:
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass

        # The child exit closes its pipe writers, allowing both readers to see
        # EOF. Join them before closing the local stream objects.
        self._stdout_thread.join(timeout=2)
        self._stderr_thread.join(timeout=2)
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except OSError:
                    pass


def read_full_turns(
    client: RpcClient,
    thread_id: str,
    request_id: int,
    page_size: int,
    max_pages: int,
) -> tuple[list[dict[str, Any]] | None, int, list[dict[str, Any]]]:
    """Page the documented full-turn interface and return chronological turns."""
    cursor: str | None = None
    seen_cursors: set[str] = set()
    newest_first: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for page_number in range(1, max_pages + 1):
        response = client.request(
            "thread/turns/list",
            {
                "threadId": thread_id,
                "cursor": cursor,
                "limit": page_size,
                "sortDirection": "desc",
                "itemsView": "full",
            },
            request_id,
        )
        request_id += 1
        if "error" in response:
            errors.append(
                {
                    "stage": "thread/turns/list",
                    "thread_id": thread_id,
                    "page": page_number,
                    "error": response["error"],
                }
            )
            return None, request_id, errors
        result = response.get("result", {})
        page = result.get("data", [])
        if not isinstance(page, list):
            errors.append(
                {
                    "stage": "thread/turns/list",
                    "thread_id": thread_id,
                    "page": page_number,
                    "error": "result.data was not a list",
                }
            )
            return None, request_id, errors
        newest_first.extend(item for item in page if isinstance(item, dict))
        next_cursor = result.get("nextCursor")
        if not next_cursor:
            return list(reversed(newest_first)), request_id, errors
        if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
            errors.append(
                {
                    "stage": "thread/turns/list",
                    "thread_id": thread_id,
                    "page": page_number,
                    "error": "repeated or invalid pagination cursor",
                }
            )
            return None, request_id, errors
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    errors.append(
        {
            "stage": "thread/turns/list",
            "thread_id": thread_id,
            "error": f"maximum turn pages reached ({max_pages})",
        }
    )
    # Do not replace thread/read(includeTurns=true) with a known-partial page set.
    return None, request_id, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Inclusive ISO-8601 instant")
    parser.add_argument("--end", required=True, help="Exclusive ISO-8601 instant")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex", default="codex", help="Codex executable")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-thread-pages", type=int, default=1000)
    parser.add_argument("--turn-page-size", type=int, default=100)
    parser.add_argument("--max-turn-pages", type=int, default=1000)
    parser.add_argument("--privacy", choices=("Low", "Medium", "High"), default="Low")
    parser.add_argument("--custom-sensitive-term", action="append", default=[])
    parser.add_argument(
        "--include-archived",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Read both active and archived threads (default: true)",
    )
    return parser.parse_args()


def collect(args: argparse.Namespace) -> dict[str, Any]:
    start = parse_instant(args.start)
    end = parse_instant(args.end)
    start_epoch = start.timestamp()
    end_epoch = end.timestamp()
    if end <= start:
        raise ValueError("--end must be later than --start")

    command = [args.codex, "app-server", "--listen", "stdio://"]
    client = RpcClient(command, args.timeout)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    threads: list[dict[str, Any]] = []
    context_candidates: list[dict[str, Any]] = []
    listed: list[dict[str, Any]] = []
    listed_ids: set[str] = set()
    selected_ids: set[str] = set()
    request_id = 1
    source_filter_mode = "all-explicit"
    scope_partial = False
    try:
        init = client.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "coding_collaboration_journal",
                    "title": "Coding Collaboration Journal",
                    "version": "installed-runtime",
                },
                "capabilities": {
                    # Current Codex documents thread/turns/list on the stable
                    # surface. Keep the capability enabled for compatibility with
                    # older builds that gated the same method; the reader still
                    # uses only documented methods and falls back to thread/read.
                    "experimentalApi": True,
                    "optOutNotificationMethods": [
                        "item/agentMessage/delta",
                        "item/reasoning/summaryTextDelta",
                    ],
                },
            },
            request_id,
        )
        request_id += 1
        if "error" in init:
            raise RuntimeError(f"App Server initialize failed: {init['error']}")
        client.send({"method": "initialized", "params": {}})

        archived_modes = [False, True] if args.include_archived else [False]
        for archived in archived_modes:
            cursor: str | None = None
            seen_cursors: set[str] = set()
            for page_number in range(1, args.max_thread_pages + 1):
                list_params: dict[str, Any] = {
                    "cursor": cursor,
                    "limit": args.page_size,
                    "sortKey": "recency_at",
                    "sortDirection": "desc",
                    "archived": archived,
                }
                if source_filter_mode == "all-explicit":
                    list_params["sourceKinds"] = ALL_SOURCE_KINDS
                response = client.request("thread/list", list_params, request_id)
                request_id += 1
                if "error" in response and source_filter_mode == "all-explicit":
                    # A Codex build can reject a newer/older source enum even when
                    # the rest of thread/list works. Retry without sourceKinds so
                    # interactive cli/vscode history is still collected, but mark
                    # scope partial because non-interactive sources may be absent.
                    warnings.append(
                        {
                            "stage": "thread/list",
                            "archived": archived,
                            "message": "Explicit all-source thread listing failed; retried with the server's interactive-source default",
                            "error": response["error"],
                        }
                    )
                    source_filter_mode = "interactive-fallback"
                    scope_partial = True
                    list_params.pop("sourceKinds", None)
                    response = client.request("thread/list", list_params, request_id)
                    request_id += 1
                if "error" in response:
                    errors.append({"stage": "thread/list", "archived": archived, "error": response["error"]})
                    break
                result = response.get("result", {})
                page = result.get("data", [])
                if not isinstance(page, list):
                    errors.append({"stage": "thread/list", "archived": archived, "error": "result.data was not a list"})
                    break

                page_hints = [epoch_hint(item) for item in page if isinstance(item, dict)]
                for summary in page:
                    if not isinstance(summary, dict):
                        continue
                    thread_id = summary.get("id")
                    if isinstance(thread_id, str) and thread_id and thread_id not in listed_ids:
                        listed.append(summary)
                        listed_ids.add(thread_id)
                    if not isinstance(thread_id, str) or not thread_id or thread_id in selected_ids:
                        continue

                    created_epoch = epoch_value(summary.get("createdAt")) or 0.0
                    recent = epoch_hint(summary)
                    # Read long-lived threads whose metadata overlaps or follows the
                    # window; exact turn/item timestamps are checked after reading.
                    qualifies_for_read = created_epoch < end_epoch and recent >= start_epoch
                    if not qualifies_for_read:
                        continue

                    read_response = client.request(
                        "thread/read",
                        {"threadId": thread_id, "includeTurns": True},
                        request_id,
                    )
                    request_id += 1
                    if "error" in read_response:
                        errors.append({"stage": "thread/read", "thread_id": thread_id, "error": read_response["error"]})
                        continue
                    native = read_response.get("result", {}).get("thread")
                    if not isinstance(native, dict):
                        errors.append({"stage": "thread/read", "thread_id": thread_id, "error": "result.thread was not an object"})
                        continue

                    full_turns, request_id, turn_errors = read_full_turns(
                        client,
                        thread_id,
                        request_id,
                        args.turn_page_size,
                        args.max_turn_pages,
                    )
                    if full_turns is not None:
                        errors.extend(turn_errors)
                        native["turns"] = full_turns
                        turns_interface = "thread/turns/list:full"
                    else:
                        fallback_turns = native.get("turns")
                        if isinstance(fallback_turns, list):
                            warnings.extend(turn_errors)
                        else:
                            errors.extend(turn_errors)
                        turns_interface = "thread/read:includeTurns-fallback"

                    active, basis, timestamp_count = activity_basis(
                        summary,
                        native.get("turns", []),
                        start_epoch,
                        end_epoch,
                    )
                    if active:
                        selected_ids.add(thread_id)
                        threads.append(
                            {
                                "summary": summary,
                                "thread": native,
                                "turns_interface": turns_interface,
                                "activity_basis": basis,
                                "timestamp_count": timestamp_count,
                                "archived": archived,
                            }
                        )
                    else:
                        context_candidates.append(
                            {
                                "summary": summary,
                                "reason": basis,
                                "timestamp_count": timestamp_count,
                                "archived": archived,
                            }
                        )
                        warnings.append(
                            {
                                "stage": "window-filter",
                                "thread_id": thread_id,
                                "message": "Thread metadata reached beyond the window, but no in-window turn/item timestamp was found",
                            }
                        )

                next_cursor = result.get("nextCursor")
                if not next_cursor:
                    break
                if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
                    errors.append(
                        {
                            "stage": "thread/list",
                            "archived": archived,
                            "page": page_number,
                            "error": "repeated or invalid pagination cursor",
                        }
                    )
                    break
                seen_cursors.add(next_cursor)
                cursor = next_cursor
                # Results are newest first. Once every recency hint on this page is
                # older than the window, subsequent pages cannot qualify.
                if page_hints and max(page_hints) < start_epoch:
                    break
            else:
                errors.append(
                    {
                        "stage": "thread/list",
                        "archived": archived,
                        "error": f"maximum thread pages reached ({args.max_thread_pages})",
                    }
                )
    finally:
        client.close()

    payload = {
        "schema_version": 1,
        "adapter": "codex-app-server",
        "collected_at": utc_now_iso(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "command": command,
        "include_archived": args.include_archived,
        "source_filter_mode": source_filter_mode,
        "listed_thread_count": len(listed),
        "selected_thread_count": len(threads),
        "context_candidate_count": len(context_candidates),
        "threads": threads,
        "context_candidates": context_candidates,
        "errors": errors,
        "warnings": warnings,
        "stderr_tail": client.stderr_lines[-100:],
        "coverage": "complete" if not errors and not scope_partial else "partial",
    }
    return sanitize(payload, args.privacy, args.custom_sensitive_term)


def main() -> int:
    args = parse_args()
    try:
        payload = collect(args)
        write_json(args.output, payload)
        return 0 if payload.get("coverage") == "complete" else 2
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "adapter": "codex-app-server",
            "collected_at": utc_now_iso(),
            "window": {"start": args.start, "end": args.end},
            "coverage": "unavailable",
            "errors": [{"stage": "fatal", "type": type(exc).__name__, "message": str(exc)}],
        }
        write_json(args.output, sanitize(failure, args.privacy, args.custom_sensitive_term))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
